"""
frontend_ws.py — Manages connected frontend WebSocket clients and broadcasts insights.
"""
import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Global client registry ────────────────────────────────────────────────────
_clients: Set[WebSocket] = set()


async def broadcast(payload: dict) -> None:
    """Push a JSON payload to all connected frontend clients."""
    if not _clients:
        return
    message = json.dumps(payload)
    dead: Set[WebSocket] = set()
    for ws in list(_clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _clients.discard(ws)


@router.websocket("/ws")
async def frontend_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint that frontend dashboards connect to."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info("Frontend client connected. Total: %d", len(_clients))
    try:
        # Keep connection alive; frontend only receives, doesn't send
        while True:
            await asyncio.sleep(10)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Frontend WS closed: %s", exc)
    finally:
        _clients.discard(websocket)
        logger.info("Frontend client disconnected. Total: %d", len(_clients))
