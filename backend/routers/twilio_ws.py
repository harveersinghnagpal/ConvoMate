"""
twilio_ws.py — Handles Twilio Media Stream WebSocket and orchestrates the full pipeline:
               Twilio audio → Deepgram STT → Gemini analysis → frontend broadcast
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.context import ContextBuffer
from backend.services.deepgram import DeepgramStreamer
from backend.services import gemini
from backend.routers.frontend_ws import broadcast
from backend.config import MIN_TRANSCRIPT_LENGTH

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    """
    Twilio Media Stream WebSocket endpoint.

    Twilio connects here and sends JSON-encoded audio chunks.
    We decode and forward to Deepgram, then process transcripts through Gemini.
    """
    await websocket.accept()
    logger.info("Twilio Media Stream connected")

    # Per-call state
    context = ContextBuffer()
    stream_sid: str = ""
    analysis_lock = asyncio.Lock()

    async def on_transcript(text: str, is_final: bool) -> None:
        """Callback fired by Deepgram for each transcript result."""
        nonlocal stream_sid

        if not text or len(text) < MIN_TRANSCRIPT_LENGTH:
            return

        if is_final:
            context.add_final(text)
        else:
            context.add_partial(text)

        # Broadcast the raw transcript to frontend immediately
        await broadcast({
            "type": "transcript",
            "text": text,
            "is_final": is_final,
        })

        # Only call LLM on final (debounced) results to avoid over-calling
        if is_final:
            async with analysis_lock:
                result = await gemini.analyze(text, context.get_context())
                if result:
                    await broadcast({
                        "type": "analysis",
                        "transcript": text,
                        "sentiment": result["sentiment"],
                        "escalation": result["escalation"],
                        "suggestion": result["suggestion"],
                    })

    # Start Deepgram connection
    dg = DeepgramStreamer(on_transcript=on_transcript)
    deepgram_ready = await dg.start()
    if not deepgram_ready:
        logger.error("Ending stream early because Deepgram is unavailable")
        await broadcast({
            "type": "call_error",
            "message": "Deepgram connection failed. Check DEEPGRAM_API_KEY and outbound network access.",
        })
        await websocket.close(code=1011, reason="Deepgram unavailable")
        return

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
                stream_sid = msg.get("streamSid", "")
                logger.info("Twilio stream started: sid=%s", stream_sid)
                context.clear()
                await broadcast({"type": "call_start", "stream_sid": stream_sid})

            elif event == "media":
                # Forward audio payload to Deepgram
                payload = msg.get("media", {}).get("payload", "")
                if payload:
                    await dg.send_audio_b64(payload)

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
        await dg.stop()
        logger.info("Twilio media stream handler cleaned up")
