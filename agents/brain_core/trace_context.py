"""Request-scoped trace context for Langfuse (session + user attribution).

A FastAPI middleware sets these per request; the LLM router reads them when
building Langfuse generation metadata, so every LLM call made while handling a
request is automatically attributed to the right session and user — no need to
thread parameters through every function.
"""

import contextvars
from typing import Any

_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "lf_session_id", default=None
)
_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("lf_user_id", default=None)


def set_trace_context(session_id: str | None = None, user_id: str | None = None) -> None:
    """Set the current request's session/user for tracing."""
    if session_id:
        _session_id.set(session_id)
    if user_id:
        _user_id.set(user_id)


def get_trace_context() -> dict[str, Any]:
    """Return the current trace context as Langfuse-compatible metadata keys."""
    ctx: dict[str, Any] = {}
    sid = _session_id.get()
    uid = _user_id.get()
    if sid:
        ctx["session_id"] = sid
    if uid:
        ctx["trace_user_id"] = uid
    return ctx
