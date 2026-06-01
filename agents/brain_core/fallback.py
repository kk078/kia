"""LLM fallback chains with circuit breakers — the core of KIA's fault tolerance.

Every user-facing generation tries an ordered chain of models, each guarded by its
own circuit breaker. If the preferred model (e.g. a cloud planner) fails or its
breaker is open, KIA automatically falls back to the local Ollama model. If the
whole chain is unavailable, KIA returns a graceful degraded message instead of a
hard 500. Streaming uses the same chain: it only falls forward to the next model
if nothing has been streamed yet, so the user never sees a half-answer swapped out.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import litellm

from brain_core.circuit_breaker import CircuitBreaker
from brain_core.config import settings

if TYPE_CHECKING:
    from brain_core.llm import LLMRouter

DEGRADED_MESSAGE = (
    "KIA's language models are temporarily unavailable (the local model and any "
    "configured fallback both failed health checks). Your message was saved — please "
    "retry shortly. If this persists, check that Ollama is running and a model is pulled."
)


class LLMUnavailableError(RuntimeError):
    """Raised when every model in the fallback chain is unavailable."""


# One breaker per model string, shared process-wide so state survives across requests.
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    """Return the (lazily created) circuit breaker for a named dependency."""
    br = _breakers.get(name)
    if br is None:
        br = CircuitBreaker(
            name,
            threshold=settings.breaker_threshold,
            cooldown=settings.breaker_cooldown_seconds,
        )
        _breakers[name] = br
    return br


def breaker_states() -> dict[str, str]:
    """Snapshot of all known breaker states (for the health endpoint)."""
    return {name: br.state for name, br in _breakers.items()}


def llm_chain(router: LLMRouter, task_type: str, model: str | None = None) -> list[str]:
    """Build the ordered fallback chain of model strings (preferred → local)."""
    chain: list[str] = []
    primary = model or router.route(task_type)
    chain.append(primary)
    local = f"{settings.default_oss_provider}/{settings.default_oss_model}"
    if local not in chain:
        chain.append(local)
    return chain


def _oss_kwargs(router: LLMRouter, model: str, base: dict[str, Any]) -> dict[str, Any]:
    """Merge api_base/api_key for local OpenAI-compatible providers into kwargs."""
    kw = dict(base)
    cfg = router._get_oss_config(model)
    if cfg:
        kw["api_base"] = cfg["api_base"]
        kw.setdefault("api_key", "sk-dummy")
    return kw


async def resilient_complete(
    router: LLMRouter,
    messages: list[dict[str, str]],
    task_type: str = "simple",
    model: str | None = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """Run a completion through the fallback chain. Returns (text, model_used).

    Raises LLMUnavailableError only if every model in the chain fails.
    """
    chain = llm_chain(router, task_type, model)
    last_err: Exception | None = None
    for m in chain:
        breaker = get_breaker(f"llm:{m}")
        try:

            async def _do(m: str = m) -> Any:
                return await router.complete(m, messages, **kwargs)

            resp = await breaker.call(_do)
            text: str = resp.choices[0].message.content
            return text, m
        except Exception as e:  # breaker-open or provider error → try next model
            last_err = e
            continue
    raise LLMUnavailableError(str(last_err) if last_err else "no models configured")


async def resilient_generate(
    router: LLMRouter,
    prompt: str,
    task_type: str = "simple",
    model: str | None = None,
    system: str | None = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """Prompt → (text, model_used) through the fallback chain. Never raises for the
    caller: on total failure returns (DEGRADED_MESSAGE, 'degraded')."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        return await resilient_complete(router, messages, task_type, model, **kwargs)
    except LLMUnavailableError:
        return DEGRADED_MESSAGE, "degraded"


async def resilient_stream(
    router: LLMRouter,
    messages: list[dict[str, str]],
    task_type: str = "simple",
    model: str | None = None,
    gen_kwargs: dict[str, Any] | None = None,
) -> AsyncGenerator[tuple[str, str], None]:
    """Stream tokens through the fallback chain.

    Yields (text_piece, model_used). Falls forward to the next model only if the
    current one fails BEFORE emitting any token, so a partial answer is never
    silently replaced. If all models fail, yields the degraded message once.
    """
    base = gen_kwargs or {}
    chain = llm_chain(router, task_type, model)
    for m in chain:
        breaker = get_breaker(f"llm:{m}")
        if breaker.is_open:
            continue
        kw = _oss_kwargs(router, m, base)
        started = False
        try:
            resp = await litellm.acompletion(model=m, messages=messages, stream=True, **kw)
            async for chunk in resp:
                piece: str | None = None
                try:
                    piece = chunk.choices[0].delta.content
                except Exception:
                    piece = None
                if piece:
                    started = True
                    yield piece, m
            breaker.record_success()
            return
        except Exception as e:
            breaker.record_failure()
            if started:
                # Mid-stream failure: surface as text, do not swap models.
                yield f"\n\n[KIA stream error: {type(e).__name__}]", m
                return
            continue  # nothing streamed yet → try the next model in the chain
    yield DEGRADED_MESSAGE, "degraded"
