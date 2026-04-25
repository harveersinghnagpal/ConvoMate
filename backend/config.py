import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# ── Deepgram ──────────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")

# ── Google Gemini ─────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Twilio ────────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")

# ── App ───────────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
PUBLIC_URL: str = os.getenv("PUBLIC_URL", "http://localhost:8000")

# Context buffer: how many transcript segments to keep for LLM context
CONTEXT_BUFFER_SIZE: int = int(os.getenv("CONTEXT_BUFFER_SIZE", "8"))

# Minimum characters in a transcript segment before calling LLM (debounce)
MIN_TRANSCRIPT_LENGTH: int = int(os.getenv("MIN_TRANSCRIPT_LENGTH", "10"))
