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

    def add_final(self, text: str) -> None:
        """Add a finalized transcript segment."""
        text = text.strip()
        if text:
            self._buffer.append(text)
            self._last_partial = ""

    def add_partial(self, text: str) -> None:
        """Track the latest partial result (not stored in buffer)."""
        self._last_partial = text.strip()

    def get_context(self) -> str:
        """Return recent conversation context as a single string."""
        parts: List[str] = list(self._buffer)
        if self._last_partial:
            parts.append(f"[partial] {self._last_partial}")
        return " | ".join(parts)

    def get_latest(self) -> str:
        """Return only the most recent finalized segment."""
        if self._buffer:
            return self._buffer[-1]
        return self._last_partial

    def clear(self) -> None:
        self._buffer.clear()
        self._last_partial = ""

    def __len__(self) -> int:
        return len(self._buffer)


# ── Module-level singleton (one buffer per call session) ──────────────────────
context_buffer = ContextBuffer()
