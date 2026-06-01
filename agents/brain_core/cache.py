"""Lightweight Redis-backed response cache (provider-free, single-user scope).

Caches expensive results (e.g. RAG answers) keyed by a hash of the input so repeat
queries return instantly instead of re-running retrieval + local generation.
Best-effort: any Redis error degrades to a cache miss, never breaks the request.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from brain_core.config import settings

# Process-local cache used when storage_backend != "redis" (native deployment).
# Maps key -> (expiry_epoch, value). Single-process scope, which is exactly the
# native deployment, so this fully replaces Redis for caching.
_MEM: dict[str, tuple[float, str]] = {}


def cache_key(namespace: str, *parts: str) -> str:
    """Build a stable cache key from a namespace and arbitrary string parts."""
    raw = "\x1f".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"kia:cache:{namespace}:{digest}"


class ResponseCache:
    """Async response cache (Redis server, or in-process dict in native mode)."""

    def __init__(self) -> None:
        """Pick the backend; only connect to Redis when that backend is selected."""
        self._mem = (settings.storage_backend or "redis").lower() != "redis"
        self._redis: Any = None
        if not self._mem:
            import redis.asyncio as redis

            self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        """Return a cached value, or None on miss/error."""
        if not settings.cache_enabled:
            return None
        if self._mem:
            hit = _MEM.get(key)
            if hit and hit[0] > time.time():
                return hit[1]
            _MEM.pop(key, None)
            return None
        try:
            val = await self._redis.get(key)
            return val if isinstance(val, str) else None
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Store a value with a TTL (seconds); best-effort."""
        if not settings.cache_enabled:
            return
        if self._mem:
            _MEM[key] = (time.time() + float(ttl or settings.cache_ttl_seconds), value)
            return
        try:
            await self._redis.set(key, value, ex=ttl or settings.cache_ttl_seconds)
        except Exception:
            return

    async def close(self) -> None:
        """Close the Redis connection (no-op in native mode)."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                return
