"""Short, sortable, prefixed IDs -- e.g. "evt_1a2b3c4d". Every schema that
needs an id uses this instead of a bare uuid4, so ids stay greppable and
self-describing in logs, Markdown files, and API payloads."""

from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
