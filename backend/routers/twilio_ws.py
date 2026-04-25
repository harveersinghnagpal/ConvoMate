"""
twilio_ws.py - Handles Twilio Media Stream WebSocket and orchestrates the full pipeline:
               Twilio audio -> Deepgram STT -> Groq analysis -> frontend broadcast
"""
import asyncio
import json
import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import MIN_TRANSCRIPT_LENGTH
from backend.routers.frontend_ws import broadcast
from backend.services import groq
from backend.services.context import ContextBuffer
from backend.services.deepgram import DeepgramStreamer

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize_track(track: str) -> str:
    value = (track or "").strip().lower()
    if value in {"inbound", "inbound_track", "caller", "customer"}:
        return "inbound"
    if value in {"outbound", "outbound_track", "agent"}:
        return "outbound"
    return "unknown"


def _speaker_for_track(track: str) -> str:
    if track == "inbound":
        return "caller"
    if track == "outbound":
        return "agent"
    return "unknown"


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    """
    Twilio Media Stream WebSocket endpoint.

    Twilio connects here and sends JSON-encoded audio chunks for the inbound
    caller and outbound agent tracks. Each track is transcribed independently so
    the frontend can render both sides of the call in order.
    """
    await websocket.accept()
    logger.info("Twilio Media Stream connected")

    context = ContextBuffer()
    stream_sid = ""
    call_sid = ""
    analysis_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=1)
    analysis_task: asyncio.Task | None = None

    async def enqueue_analysis(text: str, context_snapshot: str) -> None:
        while not analysis_queue.empty():
            with suppress(asyncio.QueueEmpty):
                analysis_queue.get_nowait()
                analysis_queue.task_done()
        await analysis_queue.put((text, context_snapshot))

    async def analysis_worker() -> None:
        while True:
            text, context_snapshot = await analysis_queue.get()
            try:
                result = await groq.analyze(text, context_snapshot)
                if result:
                    await broadcast({
                        "type": "analysis",
                        "transcript": text,
                        "sentiment": result["sentiment"],
                        "escalation": result["escalation"],
                        "suggestion": result["suggestion"],
                    })
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Analysis worker error: %s", exc)
            finally:
                analysis_queue.task_done()

    async def on_transcript(track: str, text: str, is_final: bool) -> None:
        if not text:
            return

        speaker = _speaker_for_track(track)

        if is_final:
            context.add_final(text, speaker=speaker)
        else:
            context.add_partial(text, speaker=speaker)

        await broadcast({
            "type": "transcript",
            "text": text,
            "is_final": is_final,
            "speaker": speaker,
            "track": track,
        })

        if is_final and speaker == "caller" and len(text.strip()) >= MIN_TRANSCRIPT_LENGTH:
            await enqueue_analysis(text, context.get_context())

    streamers = {
        "inbound": DeepgramStreamer(
            on_transcript=lambda text, is_final: on_transcript("inbound", text, is_final)
        ),
        "outbound": DeepgramStreamer(
            on_transcript=lambda text, is_final: on_transcript("outbound", text, is_final)
        ),
    }

    start_results = await asyncio.gather(*(streamer.start() for streamer in streamers.values()))
    if not all(start_results):
        logger.error("Ending stream early because Deepgram is unavailable")
        await broadcast({
            "type": "call_error",
            "message": "Deepgram connection failed. Check DEEPGRAM_API_KEY and outbound network access.",
        })
        await websocket.close(code=1011, reason="Deepgram unavailable")
        await asyncio.gather(*(streamer.stop() for streamer in streamers.values()), return_exceptions=True)
        return

    analysis_task = asyncio.create_task(analysis_worker())

    try:
        async for raw_message in websocket.iter_text():
            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            event = msg.get("event", "")

            if event == "connected":
                logger.info("Twilio stream connected: %s", msg)

            elif event == "start":
                start_payload = msg.get("start", {})
                stream_sid = start_payload.get("streamSid", msg.get("streamSid", ""))
                call_sid = start_payload.get("callSid", "")
                logger.info("Twilio stream started: call_sid=%s stream_sid=%s", call_sid, stream_sid)
                context.clear()
                await broadcast({"type": "call_start", "stream_sid": stream_sid})

            elif event == "media":
                print("MEDIA EVENT RECEIVED")
                media = msg.get("media", {})
                payload = media.get("payload", "")
                track = _normalize_track(media.get("track", "unknown"))

                if payload and track in streamers:
                    await streamers[track].send_audio_b64(payload)

            elif event == "stop":
                logger.info("Twilio stream stopped: sid=%s", stream_sid)
                await broadcast({"type": "call_end", "stream_sid": stream_sid})
                break

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    except Exception as exc:
        logger.error("Twilio stream error: %s", exc)
    finally:
        if stream_sid:
            await broadcast({"type": "call_end", "stream_sid": stream_sid})
        if analysis_task:
            analysis_task.cancel()
            with suppress(asyncio.CancelledError):
                await analysis_task
        await asyncio.gather(*(streamer.stop() for streamer in streamers.values()), return_exceptions=True)
        logger.info("Twilio media stream handler cleaned up")
