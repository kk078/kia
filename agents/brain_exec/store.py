"""Short-lived store for pending command plans (Redis).

A plan is saved when KIA proposes commands; ``/exec/run`` looks the command up by
(plan_id, index) so the backend only ever runs a command that was part of a plan the
user reviewed — not an arbitrary string. Plans expire after an hour.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as redis

from brain_core.config import settings

_TTL = 3600


class ExecPlanStore:
    """Persists proposed command plans for later approval + execution."""

    def __init__(self) -> None:
        """Initialize with a Redis connection."""
        self._redis: Any = redis.from_url(settings.redis_url, decode_responses=True)

    async def save(self, task: str, commands: list[dict[str, str]]) -> str:
        """Store a plan; returns its id."""
        plan_id = uuid.uuid4().hex
        payload = json.dumps({"task": task, "commands": commands, "ts": time.time()})
        try:
            await self._redis.set(f"kia:execplan:{plan_id}", payload, ex=_TTL)
        except Exception:
            pass
        return plan_id

    async def command_at(self, plan_id: str, index: int) -> str | None:
        """Return the command at ``index`` of a stored plan, or None if invalid."""
        try:
            raw = await self._redis.get(f"kia:execplan:{plan_id}")
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            commands = data.get("commands", [])
            if 0 <= index < len(commands):
                cmd = commands[index].get("command")
                return str(cmd) if cmd else None
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None
        return None

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            await self._redis.aclose()
        except Exception:
            return
