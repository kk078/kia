"""Short-lived store for pending command plans.

A plan is saved when KIA proposes commands; ``/exec/run`` looks the command up by
(plan_id, index) so the backend only ever runs a command that was part of a plan the
user reviewed — not an arbitrary string. Plans expire after an hour.

Backend follows ``settings.storage_backend``: Redis (server) or an in-process dict
(native deployment — plan + run happen in the same running API process, so process
memory is sufficient).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from brain_core.config import settings

_TTL = 3600
# plan_id -> (expiry_epoch, {"task":..., "commands":[...]}) for the in-process backend.
_MEM: dict[str, tuple[float, dict[str, Any]]] = {}


class ExecPlanStore:
    """Persists proposed command plans for later approval + execution."""

    def __init__(self) -> None:
        """Pick the backend; only connect to Redis when that backend is selected."""
        self._mem = (settings.storage_backend or "redis").lower() != "redis"
        self._redis: Any = None
        if not self._mem:
            import redis.asyncio as redis

            self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def save(self, task: str, commands: list[dict[str, str]]) -> str:
        """Store a plan; returns its id."""
        plan_id = uuid.uuid4().hex
        if self._mem:
            _MEM[plan_id] = (time.time() + _TTL, {"task": task, "commands": commands})
            return plan_id
        payload = json.dumps({"task": task, "commands": commands, "ts": time.time()})
        try:
            await self._redis.set(f"kia:execplan:{plan_id}", payload, ex=_TTL)
        except Exception:
            pass
        return plan_id

    async def command_at(self, plan_id: str, index: int) -> str | None:
        """Return the command at ``index`` of a stored plan, or None if invalid."""
        if self._mem:
            hit = _MEM.get(plan_id)
            if not hit or hit[0] < time.time():
                _MEM.pop(plan_id, None)
                return None
            data = hit[1]
        else:
            try:
                raw = await self._redis.get(f"kia:execplan:{plan_id}")
            except Exception:
                return None
            if not raw:
                return None
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        try:
            commands = data.get("commands", [])
            if 0 <= index < len(commands):
                cmd = commands[index].get("command")
                return str(cmd) if cmd else None
        except (AttributeError, TypeError):
            return None
        return None

    async def close(self) -> None:
        """Close the Redis connection (no-op in native mode)."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                return
