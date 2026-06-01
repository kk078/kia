"""Durable conversation history backed by Redis.

Persists chat conversations so they survive a page refresh, a new session, and a
backend restart (Redis runs with AOF in production). Single-user scope but keyed by
user so multi-user is a drop-in later.

Redis layout:
    kia:conv:{id}            -> LIST of JSON-encoded messages (RPUSH / LRANGE)
    kia:conv:{id}:meta       -> HASH {id,title,user_id,created_at,updated_at,message_count}
    kia:user:{user_id}:convs -> ZSET member=conv_id score=updated_at(epoch) (recency index)

All methods are best-effort: a Redis outage degrades to "no history" rather than
breaking chat. Reads return empty/None on error; writes return False on error.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis.asyncio as redis

from brain_core.config import settings

_MAX_MESSAGES = 2000  # hard cap per conversation to bound memory
_DEFAULT_TITLE = "New chat"


def _now() -> float:
    return time.time()


def _conv_key(conv_id: str) -> str:
    return f"kia:conv:{conv_id}"


def _meta_key(conv_id: str) -> str:
    return f"kia:conv:{conv_id}:meta"


def _user_key(user_id: str) -> str:
    return f"kia:user:{user_id}:convs"


def _derive_title(text: str) -> str:
    """First user message, trimmed, becomes the conversation title."""
    clean = " ".join(text.strip().split())
    if not clean:
        return _DEFAULT_TITLE
    return clean[:60] + ("…" if len(clean) > 60 else "")


class ConversationStore:
    """Async Redis-backed store for chat conversations."""

    def __init__(self) -> None:
        """Initialize with a Redis connection (decoded strings)."""
        # Typed Any: redis-py async return types are strict and fight mypy; the
        # shapes (str/list/dict) are validated at runtime here.
        self._redis: Any = redis.from_url(settings.redis_url, decode_responses=True)

    async def create(self, user_id: str, title: str | None = None) -> dict[str, Any]:
        """Create a new conversation and return its metadata dict."""
        conv_id = uuid.uuid4().hex
        now = _now()
        meta = {
            "id": conv_id,
            "title": title or _DEFAULT_TITLE,
            "user_id": user_id,
            "created_at": str(now),
            "updated_at": str(now),
            "message_count": "0",
        }
        try:
            await self._redis.hset(_meta_key(conv_id), mapping=meta)
            await self._redis.zadd(_user_key(user_id), {conv_id: now})
        except Exception:
            pass
        return self._public_meta(meta)

    async def append(self, conv_id: str, role: str, content: str) -> bool:
        """Append a message; auto-titles from the first user message. Best-effort."""
        msg = {"role": role, "content": content, "ts": _now()}
        try:
            meta = await self._redis.hgetall(_meta_key(conv_id))
            if not meta:
                # Unknown conversation: lazily create it so a message is never lost.
                user_id = "default"
                await self.create(user_id, _derive_title(content) if role == "user" else None)
                meta = await self._redis.hgetall(_meta_key(conv_id)) or {}

            await self._redis.rpush(_conv_key(conv_id), json.dumps(msg, ensure_ascii=False))
            await self._redis.ltrim(_conv_key(conv_id), -_MAX_MESSAGES, -1)

            now = _now()
            updates: dict[str, str] = {"updated_at": str(now)}
            count = int(meta.get("message_count", "0") or "0") + 1
            updates["message_count"] = str(count)
            # Title from the first user message if still default.
            if role == "user" and (meta.get("title") in (None, "", _DEFAULT_TITLE)):
                updates["title"] = _derive_title(content)
            await self._redis.hset(_meta_key(conv_id), mapping=updates)

            user_id = meta.get("user_id", "default")
            await self._redis.zadd(_user_key(user_id), {conv_id: now})
            return True
        except Exception:
            return False

    async def messages(self, conv_id: str) -> list[dict[str, Any]]:
        """Return the ordered message list for a conversation (empty on miss/error)."""
        try:
            raw = await self._redis.lrange(_conv_key(conv_id), 0, -1)
        except Exception:
            return []
        out: list[dict[str, Any]] = []
        for item in raw or []:
            try:
                out.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    async def get_meta(self, conv_id: str) -> dict[str, Any] | None:
        """Return conversation metadata, or None if it does not exist."""
        try:
            meta = await self._redis.hgetall(_meta_key(conv_id))
        except Exception:
            return None
        return self._public_meta(meta) if meta else None

    async def list(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List a user's conversations, most-recently-updated first."""
        try:
            ids = await self._redis.zrevrange(_user_key(user_id), 0, limit - 1)
        except Exception:
            return []
        out: list[dict[str, Any]] = []
        for cid in ids or []:
            meta = await self.get_meta(cid)
            if meta:
                out.append(meta)
        return out

    async def rename(self, conv_id: str, title: str) -> bool:
        """Rename a conversation. Best-effort."""
        try:
            if not await self._redis.exists(_meta_key(conv_id)):
                return False
            new_title = title.strip()[:120] or _DEFAULT_TITLE
            await self._redis.hset(_meta_key(conv_id), "title", new_title)
            return True
        except Exception:
            return False

    async def delete(self, conv_id: str) -> bool:
        """Delete a conversation and de-index it from its user. Best-effort."""
        try:
            meta = await self._redis.hgetall(_meta_key(conv_id))
            user_id = (meta or {}).get("user_id", "default")
            await self._redis.delete(_conv_key(conv_id), _meta_key(conv_id))
            await self._redis.zrem(_user_key(user_id), conv_id)
            return True
        except Exception:
            return False

    @staticmethod
    def _public_meta(meta: dict[str, Any]) -> dict[str, Any]:
        """Coerce stored string fields into a clean typed dict for the API."""

        def _f(key: str) -> float:
            try:
                return float(meta.get(key, "0") or "0")
            except (TypeError, ValueError):
                return 0.0

        return {
            "id": meta.get("id", ""),
            "title": meta.get("title", _DEFAULT_TITLE),
            "user_id": meta.get("user_id", "default"),
            "created_at": _f("created_at"),
            "updated_at": _f("updated_at"),
            "message_count": int(_f("message_count")),
        }

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            await self._redis.aclose()
        except Exception:
            return


def make_conversation_store() -> Any:
    """Return the conversation store for the configured backend (redis | sqlite)."""
    if (settings.storage_backend or "redis").lower() == "sqlite":
        from brain_memory.conversations_sqlite import SqliteConversationStore

        return SqliteConversationStore()
    return ConversationStore()
