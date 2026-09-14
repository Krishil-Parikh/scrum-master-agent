"""Agent communication layer: the Event Bus (PRD §19) and the WebSocket
fan-out that lets the frontend watch the pod work in real time."""

from app.communication.event_bus import EventBus, get_event_bus
from app.communication.websocket_manager import ConnectionManager, get_connection_manager

__all__ = ["EventBus", "get_event_bus", "ConnectionManager", "get_connection_manager"]
