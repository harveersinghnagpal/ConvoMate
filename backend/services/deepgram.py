import asyncio
import base64
import json
import logging
from typing import Callable, Awaitable

import websockets

from backend.config import DEEPGRAM_API_KEY

logger = logging.getLogger(__name__)
DEEPGRAM_WS_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=mulaw"
    "&sample_rate=8000"
    "&channels=1"
    "&model=nova-2"
    "&interim_results=true"
    "&smart_format=true"
)

print("DEEPGRAM KEY:", DEEPGRAM_API_KEY[:10])

TranscriptCallback = Callable[[str, bool], Awaitable[None]]


class DeepgramStreamer:
    """
    Opens a single WebSocket to Deepgram and forwards raw mulaw audio frames.
    Calls `on_transcript(text, is_final)` for each result.
    """

    def __init__(self, on_transcript: TranscriptCallback):
        self._on_transcript = on_transcript
        self._ws = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and self._ws is not None

    async def start(self) -> bool:
        """Connect to Deepgram and start the receive loop."""
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        try:
            self._ws = await websockets.connect(
                DEEPGRAM_WS_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=30,
            )
            self._running = True
            logger.info("Deepgram WebSocket connected")
            asyncio.ensure_future(self._receive_loop())
            return True
        except Exception as exc:
            logger.error("Failed to connect to Deepgram: %s", exc)
            self._running = False
            self._ws = None
            return False

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Forward raw audio bytes to Deepgram."""
        if self._ws and self._running:
            try:
                await self._ws.send(audio_bytes)
            except Exception as exc:
                logger.warning("Deepgram send error: %s", exc)
                self._running = False

    async def send_audio_b64(self, b64_str: str) -> None:
        """Decode base64 audio (from Twilio) and forward to Deepgram."""
        try:
            raw = base64.b64decode(b64_str)
            await self.send_audio(raw)
            print("Sending audio to Deepgram")
        except Exception as exc:
            logger.warning("Base64 decode error: %s", exc)

    async def stop(self) -> None:
        """Send close frame and disconnect."""
        self._running = False
        if self._ws:
            try:
                # Send KeepAlive close signal
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("Deepgram WebSocket disconnected")

    async def _receive_loop(self) -> None:
        """Process incoming Deepgram transcript messages."""
        try:
            async for message in self._ws:
                if not self._running:
                    break
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.info("Deepgram connection closed")
        except Exception as exc:
            logger.error("Deepgram receive error: %s", exc)
        finally:
            self._running = False

    async def _handle_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            print("DEEPGRAM MESSAGE:", data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "Results":
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [{}])
            transcript = alternatives[0].get("transcript", "").strip()
            is_final = data.get("is_final", False) or data.get("speech_final", False)

            if transcript:
                await self._on_transcript(transcript, is_final)

        elif msg_type == "UtteranceEnd":
            # Signal end of an utterance — useful for flushing context
            logger.debug("Deepgram UtteranceEnd received")
        elif msg_type == "Error":
            logger.error("Deepgram error message: %s", data)
