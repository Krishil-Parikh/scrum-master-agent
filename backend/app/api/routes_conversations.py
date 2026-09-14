"""Conversation feed -- read history and let a human (playing the Business
SME / Product Owner, per the dashboard's top-right user) post into the
team channel (PRD §12, §18)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.communication.event_bus import get_event_bus
from app.memory.project_memory import get_current_project_id, get_project_memory
from app.schemas.communication import Message, MessageChannel
from app.schemas.event import EventType

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_messages(channel: str | None = None, limit: int = 300) -> list[Message]:
    if not get_current_project_id():
        return []
    memory = get_project_memory()
    channel_enum = MessageChannel(channel) if channel and channel != "all" else None
    return memory.read_messages(channel_enum, limit=limit)


class SendMessageBody(BaseModel):
    channel: str = "sme"
    text: str
    sender_name: str = "Business SME"


@router.post("")
async def send_message(body: SendMessageBody) -> Message:
    if not get_current_project_id():
        raise HTTPException(400, "No active project.")
    try:
        channel = MessageChannel(body.channel)
    except ValueError:
        raise HTTPException(400, f"Unknown channel '{body.channel}'.")

    message = Message(
        channel=channel,
        sender_id="human",
        sender_name=body.sender_name,
        sender_role="SME",
        text=body.text,
    )
    memory = get_project_memory()
    memory.append_message(message)
    bus = get_event_bus()
    await bus.emit(
        EventType.MESSAGE_POSTED,
        actor_id="human",
        channel=channel.value,
        text=body.text,
        message_id=message.message_id,
        sender_name=body.sender_name,
        sender_role="SME",
        color="#1c7ed6",
        avatar_initials="SM" if body.sender_name == "Business SME" else body.sender_name[:2].upper(),
    )
    return message
