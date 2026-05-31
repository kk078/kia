"""Durable async job queue backed by Redis Streams.

Unlike fire-and-forget pub/sub, Streams persist jobs and support consumer groups
with explicit acknowledgement, so a job survives a worker crash and can be retried.
Single-user scope, but this is the durable-async building block for background work
(ingestion, distillation, long generations).
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from brain_core.config import settings


class JobQueue:
    """A durable job queue over a Redis Stream + consumer group."""

    def __init__(self, stream: str = "kia:jobs", group: str = "kia:workers") -> None:
        """Initialize the queue.

        Args:
            stream: Redis stream key.
            group: Consumer group name.
        """
        self.stream = stream
        self.group = group
        # Typed as Any: redis-py stream signatures are very strict and the nested
        # xreadgroup return type fights mypy; shapes are validated at runtime.
        self._redis: Any = redis.from_url(settings.redis_url, decode_responses=True)

    async def ensure_group(self) -> None:
        """Create the consumer group if it does not exist (idempotent)."""
        try:
            await self._redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception:
            # BUSYGROUP: group already exists -> fine.
            return

    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        """Add a job to the queue; returns the Redis stream entry id."""
        entry = {"type": job_type, "payload": json.dumps(payload)}
        msg_id: str = await self._redis.xadd(self.stream, entry)
        return msg_id

    async def dequeue(
        self, consumer: str, block_ms: int = 5000
    ) -> tuple[str, dict[str, Any]] | None:
        """Claim the next pending job for ``consumer``; None if none arrive in time."""
        await self.ensure_group()
        resp = await self._redis.xreadgroup(
            self.group, consumer, {self.stream: ">"}, count=1, block=block_ms
        )
        if not resp:
            return None
        entries = resp[0][1]
        if not entries:
            return None
        msg_id, fields = entries[0]
        payload = json.loads(fields.get("payload", "{}"))
        return str(msg_id), {"type": fields.get("type", ""), "payload": payload}

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a completed job so it is not redelivered."""
        await self._redis.xack(self.stream, self.group, msg_id)

    async def depth(self) -> int:
        """Return the number of entries currently in the stream."""
        n: int = await self._redis.xlen(self.stream)
        return n

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            await self._redis.aclose()
        except Exception:
            return
