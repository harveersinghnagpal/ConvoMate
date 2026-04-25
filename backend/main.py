"""
main.py — ConvoMate FastAPI application entrypoint.
"""
import logging
from pathlib import Path
import re

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.config import AGENT_PHONE_NUMBER, HOST, PORT, PUBLIC_URL
from backend.routers import twilio_ws, frontend_ws, analyze

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _normalize_phone_number(phone_number: str) -> str:
    """Normalize env-provided phone numbers to a Twilio-friendly E.164-like value."""
    phone_number = (phone_number or "").strip()
    if not phone_number:
        return phone_number
    if phone_number.startswith("+"):
        return "+" + re.sub(r"\D", "", phone_number[1:])
    return re.sub(r"\D", "", phone_number)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ConvoMate",
    description="Real-Time Call Monitoring & Agent Assist System",
    version="1.0.0",
)

# Allow frontend (any origin for dev; tighten for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(twilio_ws.router)
app.include_router(frontend_ws.router)
app.include_router(analyze.router)

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="dashboard")


# ── TwiML webhook ─────────────────────────────────────────────────────────────
@app.post("/twiml", response_class=PlainTextResponse)
async def twiml_webhook(request: Request) -> str:
    """
    Twilio calls this endpoint when a call comes in.
    We return TwiML that starts audio streaming and then dials the agent.
    """
    ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://")
    agent_phone_number = _normalize_phone_number(AGENT_PHONE_NUMBER)
    logger.info("Customer connected, dialing agent at %s", agent_phone_number)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Start>
    <Stream url="{ws_url}/media-stream" track="both_tracks">
      <Parameter name="app" value="ConvoMate"/>
    </Stream>
  </Start>
  <Dial callerId="+12294102824">
    <Number>{agent_phone_number}</Number>
  </Dial>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health() -> dict:
    return {"status": "ok", "app": "ConvoMate", "version": "1.0.0"}


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "message": "ConvoMate API is running",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
        "twiml_webhook": "/twiml",
        "frontend_ws": "/ws",
        "media_stream_ws": "/media-stream",
    }


@app.get("/dashboard-app.js", include_in_schema=False)
async def dashboard_app_js() -> FileResponse:
    return FileResponse(
        frontend_dir / "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/dashboard-style.css", include_in_schema=False)
async def dashboard_style_css() -> FileResponse:
    return FileResponse(
        frontend_dir / "style.css",
        media_type="text/css",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
