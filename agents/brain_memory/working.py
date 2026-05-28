"""Working memory (session-scoped, Redis-backed)."""

from typing import Any

import redis.asyncio as redis

from brain_core.config import settings


class WorkingMemory:
    """Short-term, session-scoped memory stored in Redis."""

    def __init__(self) -> None:
        """Initialize working memory with Redis connection."""
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def set(self, session_id: str, key: str, value: Any, ttl: int = 3600) -> None:
        """Set a value in working memory."""
        redis_key = f"working:{session_id}:{key}"
        await self.redis.set(redis_key, str(value), ex=ttl)

    async def get(self, session_id: str, key: str) -> Any:
        """Get a value from working memory."""
        redis_key = f"working:{session_id}:{key}"
        return await self.redis.get(redis_key)

    async def delete(self, session_id: str, key: str) -> None:
        """Delete a value from working memory."""
        redis_key = f"working:{session_id}:{key}"
        await self.redis.delete(redis_key)

    async def clear_session(self, session_id: str) -> None:
        """Clear all working memory for a session."""
        pattern = f"working:{session_id}:*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.redis.aclose()
