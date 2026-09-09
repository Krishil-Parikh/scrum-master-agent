"""Build a LangChain chat model from :class:`aamt.config.Settings`.

Keeping this behind one function means the rest of the codebase never imports a
provider SDK directly, so switching OpenRouter -> Anthropic -> OpenAI -> local
Ollama is a config change, not a code change.

The default provider is **OpenRouter** (OpenAI-compatible) with a pool of API
keys rotated round-robin; a key that returns 429/402 is put on a short cooldown
so it steps aside automatically. No network call or key check happens until a
model is actually invoked.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from ..config import Settings, get_settings


class LLMConfigError(RuntimeError):
    """Raised when a provider is selected but its credentials are missing."""


_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
}


def _require_key(provider: str) -> None:
    env = _KEY_ENV.get(provider)
    if env and not os.environ.get(env):
        raise LLMConfigError(
            f"provider '{provider}' needs {env} to be set. "
            f"Set it in your environment or .env, or switch AAMT_LLM_PROVIDER."
        )


# --------------------------------------------------------------------------
# Key rotation
# --------------------------------------------------------------------------
class KeyRotator:
    """Thread-safe round-robin over a pool of API keys with per-key cooldown."""

    def __init__(self, keys: list[str], *, cooldown_s: float = 45.0):
        if not keys:
            raise LLMConfigError(
                "no OpenRouter API keys found. Set AAMT_OPENROUTER_API_KEYS "
                "(comma-separated) or OPENROUTER_API_KEY_1..N in your environment/.env."
            )
        self._keys = list(keys)
        self._cooldown_s = cooldown_s
        self._i = 0
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._keys)

    def current(self) -> str:
        with self._lock:
            return self._keys[self._i % len(self._keys)]

    def advance(self) -> str:
        with self._lock:
            self._i = (self._i + 1) % len(self._keys)
            return self._keys[self._i]

    def penalize(self, key: str) -> None:
        with self._lock:
            self._blocked_until[key] = time.time() + self._cooldown_s

    def next_available(self) -> str:
        """Advance to the next key that is not on cooldown (or the least-blocked)."""
        with self._lock:
            n = len(self._keys)
            now = time.time()
            for step in range(1, n + 1):
                cand = self._keys[(self._i + step) % n]
                if self._blocked_until.get(cand, 0) <= now:
                    self._i = (self._i + step) % n
                    return cand
            # all on cooldown -> pick the one that frees up soonest
            soonest = min(self._keys, key=lambda k: self._blocked_until.get(k, 0))
            self._i = self._keys.index(soonest)
            return soonest


_ROTATOR_CACHE: dict[tuple[str, ...], KeyRotator] = {}
_ROTATOR_LOCK = threading.Lock()
_KEY_PAID: dict[str, bool] = {}   # key -> True if it has real credit (not free-tier)


def _key_is_paid(key: str) -> bool:
    """Probe OpenRouter once per key. Optimistic on any failure."""
    if key in _KEY_PAID:
        return _KEY_PAID[key]
    paid = True
    try:
        import httpx

        r = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            rem = data.get("limit_remaining")
            paid = (data.get("is_free_tier") is False) or (rem is not None and rem > 0)
    except Exception:  # noqa: BLE001 - network/other: assume usable
        paid = True
    _KEY_PAID[key] = paid
    return paid


def get_rotator(settings: Settings, *, free: bool = False) -> KeyRotator:
    """Return a rotator over the right key subset.

    Free-tier OpenRouter keys can only call ``:free`` models, and paid models
    routed onto them just 402. So paid models rotate over paid keys, and
    ``:free`` models rotate over free-tier keys.
    """
    from ..bootstrap import load_env

    load_env()
    all_keys = settings.resolved_openrouter_keys()

    if settings.openrouter_probe_keys and all_keys:
        paid = [k for k in all_keys if _key_is_paid(k)]
        free_keys = [k for k in all_keys if not _key_is_paid(k)]
    else:
        paid = free_keys = list(all_keys)

    pool = (free_keys if free else paid) or list(all_keys)
    cache_key = tuple(pool)
    with _ROTATOR_LOCK:
        rot = _ROTATOR_CACHE.get(cache_key)
        if rot is None:
            rot = KeyRotator(list(pool), cooldown_s=settings.openrouter_key_cooldown_s)
            _ROTATOR_CACHE[cache_key] = rot
        return rot


# --------------------------------------------------------------------------
# Rotating chat model
# --------------------------------------------------------------------------
def _build_rotating_openrouter(
    *, model: str, settings: Settings, temperature: float, max_tokens: int
) -> BaseChatModel:
    import openai
    from langchain_openai import ChatOpenAI

    rotator = get_rotator(settings, free=model.endswith(":free"))
    base_url = settings.openrouter_base_url
    headers = {
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_title,
    }
    # Soft provider routing: keep fallbacks on, but skip a backend that has been
    # flaky for tool-calling in practice (DeepInfra returned 502 on a
    # hallucinated tool name mid-ReAct). `require_parameters` is too strict —
    # it 404s for every cheap model — so we don't use it.
    extra_body: dict = {"provider": {"allow_fallbacks": True}}
    if settings.openrouter_ignore_providers.strip():
        extra_body["provider"]["ignore"] = [
            p.strip() for p in settings.openrouter_ignore_providers.split(",") if p.strip()
        ]
    # OpenRouter model-level failover: try these in order on 429/5xx/unavailable.
    fallbacks = [
        m.strip() for m in settings.openrouter_fallback_models.split(",")
        if m.strip() and m.strip() != model and not model.endswith(":free")
    ]
    if fallbacks:
        extra_body["models"] = [model, *fallbacks]

    class _HardTimeout(RuntimeError):
        """Our own deadline fired — the HTTP client's own timeout didn't.

        Observed in practice: a streaming completion whose connection resets
        its idle-read timer on every keep-alive byte never trips httpx's
        per-read timeout, so a call can block for the life of the process even
        with ``timeout=`` set on the client. We can't cancel a blocked sync
        call, but we can stop *waiting* on it and let a fresh attempt (new
        thread, new key) proceed — the orchestrator must never hang forever
        on one LLM call.
        """

    _RETRYABLE = (
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.InternalServerError,
        _HardTimeout,
    )

    import concurrent.futures

    _executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=8, thread_name_prefix="aamt-llm-call"
    )

    class RotatingChatOpenAI(ChatOpenAI):
        """ChatOpenAI that swaps to the next key on 429/402/5xx and retries."""

        def _point_at(self, key: str) -> None:
            self.root_client = openai.OpenAI(
                api_key=key, base_url=base_url, default_headers=headers, max_retries=0,
                timeout=settings.llm_request_timeout_s,
            )
            self.root_async_client = openai.AsyncOpenAI(
                api_key=key, base_url=base_url, default_headers=headers, max_retries=0,
                timeout=settings.llm_request_timeout_s,
            )
            self.client = self.root_client.chat.completions
            self.async_client = self.root_async_client.chat.completions

        def _attempts(self) -> int:
            return max(len(rotator) * 2, 4)

        def _classify(self, exc: Exception) -> bool:
            if isinstance(exc, _RETRYABLE):
                return True
            status = getattr(exc, "status_code", None)
            return status in (402, 408, 409, 429, 500, 502, 503, 504)

        def _retry_after(self, exc: Exception, attempt: int) -> float:
            hdrs = getattr(getattr(exc, "response", None), "headers", None) or {}
            try:
                ra = float(hdrs.get("retry-after") or hdrs.get("Retry-After") or 0)
            except (TypeError, ValueError):
                ra = 0.0
            return max(ra, min(4.0 * (attempt + 1), 30.0))

        def _generate(self, *args: Any, **kwargs: Any):  # type: ignore[override]
            last: Exception | None = None
            hard_timeouts = 0
            for attempt in range(self._attempts()):
                key = rotator.current() if attempt == 0 else rotator.next_available()
                self._point_at(key)
                try:
                    # Belt-and-suspenders: the client's own `timeout=` should
                    # catch a stalled call, but a hard wall-clock deadline in
                    # our own process is what actually guarantees we move on
                    # — see _HardTimeout.
                    future = _executor.submit(super()._generate, *args, **kwargs)
                    try:
                        return future.result(timeout=settings.llm_request_timeout_s + 10)
                    except concurrent.futures.TimeoutError as exc:
                        raise _HardTimeout(
                            f"LLM call exceeded {settings.llm_request_timeout_s + 10}s"
                        ) from exc
                except Exception as exc:  # noqa: BLE001 - re-raised below
                    if not self._classify(exc):
                        raise
                    if isinstance(exc, _HardTimeout):
                        hard_timeouts += 1
                        # each one already burned llm_request_timeout_s+10 —
                        # don't compound that across the full retry budget.
                        if hard_timeouts >= 2:
                            raise
                    rotator.penalize(key)
                    last = exc
                    time.sleep(self._retry_after(exc, attempt))
            assert last is not None
            raise last

        async def _agenerate(self, *args: Any, **kwargs: Any):  # type: ignore[override]
            import asyncio

            last: Exception | None = None
            hard_timeouts = 0
            for attempt in range(self._attempts()):
                key = rotator.current() if attempt == 0 else rotator.next_available()
                self._point_at(key)
                try:
                    try:
                        return await asyncio.wait_for(
                            super()._agenerate(*args, **kwargs),
                            timeout=settings.llm_request_timeout_s + 10,
                        )
                    except asyncio.TimeoutError as exc:
                        raise _HardTimeout(
                            f"LLM call exceeded {settings.llm_request_timeout_s + 10}s"
                        ) from exc
                except Exception as exc:  # noqa: BLE001
                    if not self._classify(exc):
                        raise
                    if isinstance(exc, _HardTimeout):
                        hard_timeouts += 1
                        if hard_timeouts >= 2:
                            raise
                    rotator.penalize(key)
                    last = exc
                    await asyncio.sleep(self._retry_after(exc, attempt))
            assert last is not None
            raise last

    llm = RotatingChatOpenAI(
        model=model,
        api_key=rotator.current(),
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers=headers,
        extra_body=extra_body,
        max_retries=0,
        timeout=settings.llm_request_timeout_s,
    )
    return llm


# --------------------------------------------------------------------------
# Public factory
# --------------------------------------------------------------------------
def build_chat_model(
    *,
    model: str | None = None,
    settings: Settings | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Return a ready-to-invoke chat model for the configured provider."""
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    model = model or settings.developer_model
    temperature = settings.llm_temperature if temperature is None else temperature
    max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens

    if provider == "openrouter":
        return _build_rotating_openrouter(
            model=model, settings=settings, temperature=temperature, max_tokens=max_tokens
        )

    if provider == "anthropic":
        _require_key(provider)
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=temperature, max_tokens=max_tokens)

    if provider in {"openai", "azure_openai"}:
        _require_key(provider)
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=model, temperature=temperature, max_tokens=max_tokens
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMConfigError(
                "provider 'ollama' requires 'langchain-ollama': uv add langchain-ollama"
            ) from exc

        return ChatOllama(
            model=model, temperature=temperature, base_url=settings.ollama_base_url
        )

    raise LLMConfigError(
        f"unknown AAMT_LLM_PROVIDER '{settings.llm_provider}'. "
        f"Expected one of: openrouter, anthropic, openai, azure_openai, ollama."
    )
