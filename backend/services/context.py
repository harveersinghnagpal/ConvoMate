from collections import deque
from typing import List
from backend.config import CONTEXT_BUFFER_SIZE


class ContextBuffer:
    """
    Rolling buffer of the last N transcript segments.
    Handles deduplication of partial vs final Deepgram results.
    """

    def __init__(self, maxlen: int = CONTEXT_BUFFER_SIZE):
        self._buffer: deque[str] = deque(maxlen=maxlen)
        self._last_partial: str = ""
        self._last_partial_speaker: str = "caller"

    def add_final(self, text: str, speaker: str = "caller") -> None:
        """Add a finalized transcript segment."""
        text = text.strip()
        if text:
            self._buffer.append(self._format_line(text, speaker))
            self._last_partial = ""
            self._last_partial_speaker = "caller"

    def add_partial(self, text: str, speaker: str = "caller") -> None:
        """Track the latest partial result (not stored in buffer)."""
        self._last_partial = text.strip()
        self._last_partial_speaker = speaker.strip() or "caller"

    def get_context(self) -> str:
        """Return recent conversation context as a single string."""
        parts: List[str] = list(self._buffer)
        if self._last_partial:
            parts.append(f"[partial] {self._format_line(self._last_partial, self._last_partial_speaker)}")
        return " | ".join(parts)

    def get_latest(self) -> str:
        """Return only the most recent finalized segment."""
        if self._buffer:
            return self._buffer[-1]
        return self._last_partial

    def clear(self) -> None:
        self._buffer.clear()
        self._last_partial = ""
        self._last_partial_speaker = "caller"

    def __len__(self) -> int:
        return len(self._buffer)

    @staticmethod
    def _format_line(text: str, speaker: str) -> str:
        normalized_speaker = (speaker or "caller").strip().capitalize()
        return f"{normalized_speaker}: {text}"


# ── Module-level singleton (one buffer per call session) ──────────────────────
context_buffer = ContextBuffer()
