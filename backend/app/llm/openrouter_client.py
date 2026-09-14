"""
OpenRouter chat-completion client with API-key pool rotation.

Every agent in the pod talks to the LLM exclusively through this module --
nothing else should import `httpx` and call OpenRouter directly. That keeps
key rotation, retry/backoff, and usage accounting in exactly one place.

Key pool: any environment variable matching OPENROUTER_API_KEY or
OPENROUTER_API_KEY_<N> is collected into a pool. Requests round-robin across
the pool; a key that fails with an auth/rate-limit/server error is skipped
for the rest of that call's retry attempts (not removed permanently -- a
429 now doesn't mean the key is dead a minute from now).
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("ai_dev_pod.llm")

_KEY_ENV_PATTERN = re.compile(r"^OPENROUTER_API_KEY(_\d+)?$")


def _discover_api_keys() -> list[str]:
    """Collect every configured OpenRouter key, in a stable order (numbered
    keys ascending, then the legacy unnumbered var if set), de-duplicated."""
    found: dict[str, str] = {}
    for name, value in os.environ.items():
        if _KEY_ENV_PATTERN.match(name) and value and value.strip():
            found[name] = value.strip()

    def sort_key(name: str) -> tuple[int, int]:
        if name == "OPENROUTER_API_KEY":
            return (1, 0)
        suffix = name.rsplit("_", 1)[-1]
        return (0, int(suffix)) if suffix.isdigit() else (2, 0)

    ordered_names = sorted(found, key=sort_key)
    keys = [found[n] for n in ordered_names]
    # de-dupe while preserving order (two env var names could hold the same key)
    seen: set[str] = set()
    unique = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


@dataclass
class UsageStats:
    """Cheap running total for the observability endpoint (PRD §35)."""

    requests: int = 0
    failures: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    by_key_suffix: dict[str, int] = field(default_factory=dict)

    def record(self, key: str, usage: dict[str, Any] | None) -> None:
        self.requests += 1
        suffix = key[-4:]
        self.by_key_suffix[suffix] = self.by_key_suffix.get(suffix, 0) + 1
        if usage:
            self.prompt_tokens += usage.get("prompt_tokens", 0) or 0
            self.completion_tokens += usage.get("completion_tokens", 0) or 0


class OpenRouterError(RuntimeError):
    """Raised when every key in the pool has been exhausted for a call."""


class OpenRouterClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._keys = _discover_api_keys()
        if not self._keys:
            logger.warning(
                "No OPENROUTER_API_KEY_* found in the environment. "
                "LLM calls will fail until backend/.env is configured."
            )
        self._cycle = itertools.cycle(self._keys) if self._keys else None
        self.usage = UsageStats()

    @property
    def configured(self) -> bool:
        return bool(self._keys)

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Optional but recommended by OpenRouter for attribution/rankings.
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        response_format_json: bool = False,
    ) -> str:
        """Run one chat completion, rotating through the key pool on
        transient failures. Returns the assistant message content as text."""
        if not self._keys:
            raise OpenRouterError(
                "No OpenRouter API keys configured (set OPENROUTER_API_KEY_1 "
                "in backend/.env)."
            )

        payload: dict[str, Any] = {
            "model": model or self.settings.openrouter_model,
            "messages": messages,
            "temperature": (
                self.settings.llm_temperature if temperature is None else temperature
            ),
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        # At least one full lap of the key pool, plus a couple of spare
        # attempts in case a transient 429/5xx overlaps with an exhausted
        # key during the same lap.
        attempts = max(self.settings.llm_max_retries_per_call, len(self._keys) + 2)
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
            for attempt in range(attempts):
                api_key = next(self._cycle)  # type: ignore[arg-type]
                try:
                    resp = await client.post(
                        f"{self.settings.openrouter_base_url}/chat/completions",
                        headers=self._headers(api_key),
                        json=payload,
                    )
                    if resp.status_code == 429 or resp.status_code >= 500:
                        # Rate-limited or the provider had a bad moment --
                        # try the next key in the pool rather than failing.
                        last_error = OpenRouterError(
                            f"OpenRouter {resp.status_code} on attempt {attempt + 1}: {resp.text[:300]}"
                        )
                        logger.warning(str(last_error))
                        continue
                    if resp.status_code in (401, 402, 403):
                        # 401/403 = bad/unauthorized key, 402 = this key's
                        # account is out of credit. All three are a problem
                        # with *this specific key*, not the request -- skip
                        # to the next key in the pool rather than aborting
                        # the whole call (that's the entire point of having
                        # a multi-key pool: one exhausted key shouldn't take
                        # the pod down).
                        last_error = OpenRouterError(
                            f"OpenRouter {resp.status_code} for a key ending "
                            f"...{api_key[-4:]} -- skipping it for this call. {resp.text[:200]}"
                        )
                        logger.warning(str(last_error))
                        self.usage.failures += 1
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    self.usage.record(api_key, data.get("usage"))
                    choice = data["choices"][0]["message"]["content"]
                    return choice or ""
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = exc
                    self.usage.failures += 1
                    logger.warning("OpenRouter network error on attempt %s: %s", attempt + 1, exc)
                    continue

        raise OpenRouterError(
            f"All {attempts} attempts across {len(self._keys)} key(s) failed. Last error: {last_error}"
        )

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Chat completion where the response is expected to be JSON. Tries
        native JSON mode first; if the model still wraps it in prose or code
        fences (small/cheap models do this often), fall back to extracting
        the first well-formed JSON object/array from the text."""
        text = await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format_json=True,
        )
        return _parse_json_loose(text)


def _parse_json_loose(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise OpenRouterError(f"Could not parse JSON from model output: {text[:300]!r}")


_client: OpenRouterClient | None = None


def get_llm_client() -> OpenRouterClient:
    """Process-wide singleton so the key-rotation cycle and usage stats are
    shared across every agent instead of resetting per-agent."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
