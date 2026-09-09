"""Short, human-readable, sortable identifiers for domain entities.

IDs look like ``T-a1b2c3`` (task), ``S-a1b2c3`` (sprint), etc. The prefix makes
log lines and reports readable; the random suffix keeps them unique without a
central counter (which would be a coordination bottleneck for parallel agents).
"""

from __future__ import annotations

import secrets
import time

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _rand(n: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def new_id(prefix: str) -> str:
    """Return a new id such as ``T-a1b2c3``."""
    return f"{prefix}-{_rand()}"


# Convenience constructors — one per entity kind.
def project_id() -> str: return new_id("P")
def agent_id() -> str: return new_id("A")
def task_id() -> str: return new_id("T")
def sprint_id() -> str: return new_id("S")
def event_id() -> str: return new_id("E")
def decision_id() -> str: return new_id("D")
def message_id() -> str: return new_id("M")


def now_ts() -> float:
    """Wall-clock seconds since the epoch (UTC). Single source of 'now'."""
    return time.time()
