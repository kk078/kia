"""Lightweight Redis-backed response cache (provider-free, single-user scope).

Caches expensive results (e.g. RAG answers) keyed by a hash of the input so repeat
queries return instantly instead of re-running retrieval + local generation.
Best-effort: any Redis error degrades to a cache miss, never breaks the request.
"""

from __future__ import annotations

import hashlib

import redis.asyncio as redis

from brain_core.config import settings


def cache_key(namespace: str, *parts: str) -> str:
    """Build a stable cache key from a namespace and arbitrary string parts."""
    raw = "\x1f".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"kia:cache:{namespace}:{digest}"


class ResponseCache:
    """Async Redis cache for precomputed responses."""

    def __init__(self) -> None:
        """Initialize the cache with a Redis connection."""
        self._redis: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        """Return a cached value, or None on miss/error."""
        if not settings.cache_enabled:
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
        try:
            await self._redis.set(key, value, ex=ttl or settings.cache_ttl_seconds)
        except Exception:
            return

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            await self._redis.aclose()
        except Exception:
            return
