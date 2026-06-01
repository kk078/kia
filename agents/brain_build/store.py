"""In-memory store for active build sessions (pause/resume on gated steps).

A build can stop mid-loop to ask for approval of a high-risk action; the session
(its message history + the pending action) lives here until the user approves or
rejects, then the loop resumes. Single-process/native deployment, so a dict is
sufficient; sessions are short-lived and dropped when finished or cancelled.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

_SESSIONS: dict[str, dict[str, Any]] = {}
_MAX_AGE = 3600.0  # drop sessions untouched for an hour


def _gc() -> None:
    now = time.time()
    for sid in [s for s, v in _SESSIONS.items() if now - v.get("touched", 0) > _MAX_AGE]:
        _SESSIONS.pop(sid, None)


def create(goal: str, root: str, messages: list[dict[str, str]]) -> str:
    """Register a new session and return its id."""
    _gc()
    sid = uuid.uuid4().hex
    _SESSIONS[sid] = {
        "goal": goal,
        "root": root,
        "messages": messages,
        "step": 0,
        "pending": None,
        "status": "running",
        "touched": time.time(),
    }
    return sid


def get(sid: str) -> dict[str, Any] | None:
    """Return the session dict or None."""
    return _SESSIONS.get(sid)


def save(sid: str, **fields: Any) -> None:
    """Merge fields into a session and bump its touched time."""
    s = _SESSIONS.get(sid)
    if s is None:
        return
    s.update(fields)
    s["touched"] = time.time()


def delete(sid: str) -> None:
    """Drop a session."""
    _SESSIONS.pop(sid, None)
