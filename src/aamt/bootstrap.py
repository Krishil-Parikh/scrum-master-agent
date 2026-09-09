"""Environment bootstrap — load ``.env`` before settings are read.

pydantic-settings only pulls ``AAMT_``-prefixed keys from ``.env``; the
``OPENROUTER_API_KEY_*`` pool is plain env, so we load the dotenv file into the
process environment explicitly. Safe to call repeatedly.
"""

from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def load_env(path: str | Path | None = None) -> None:
    global _LOADED
    if _LOADED and path is None:
        return
    try:
        from dotenv import load_dotenv
    except Exception:  # pragma: no cover
        return

    if path is not None:
        load_dotenv(path, override=False)
    else:
        # walk up from CWD looking for a .env
        here = Path.cwd()
        for parent in [here, *here.parents]:
            candidate = parent / ".env"
            if candidate.is_file():
                load_dotenv(candidate, override=False)
                break
        _LOADED = True

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
