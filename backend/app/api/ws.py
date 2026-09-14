"""Live WebSocket feed -- every Event published on the bus is forwarded
here as JSON. The frontend renders the dashboard/conversation/terminal
panels from this stream after loading the initial snapshot from
GET /api/bootstrap."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.communication.websocket_manager import get_connection_manager

logger = logging.getLogger("ai_dev_pod.api.ws")
router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    manager = get_connection_manager()
    await manager.connect(websocket)
    try:
        while True:
            # The client doesn't need to send anything meaningful; this
            # just keeps the connection open and lets us notice a clean
            # disconnect. A stray message is ignored rather than rejected.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket connection error")
    finally:
        manager.disconnect(websocket)
