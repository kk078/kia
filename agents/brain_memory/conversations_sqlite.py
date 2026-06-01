"""Conversation history backed by SQLite (embedded, zero-dependency).

The native deployment uses this instead of Redis: a single file at
``settings.sqlite_path`` holds all conversations, so there is no server to run.
Same async API + return shapes as the Redis ``ConversationStore`` so the API
layer is backend-agnostic. Blocking sqlite3 calls run in a worker thread.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import time
import uuid
from typing import Any

from brain_core.config import settings

_MAX_MESSAGES = 2000
_DEFAULT_TITLE = "New chat"


def _now() -> float:
    return time.time()


def _derive_title(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return _DEFAULT_TITLE
    return clean[:60] + ("…" if len(clean) > 60 else "")


def _connect() -> sqlite3.Connection:
    path = settings.sqlite_path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS conversations ("
        "id TEXT PRIMARY KEY, title TEXT, user_id TEXT, "
        "created_at REAL, updated_at REAL, message_count INTEGER DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "conv_id TEXT, seq INTEGER, role TEXT, content TEXT, ts REAL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conv_id, seq)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at)")
    return conn


def _meta_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "user_id": row[2],
        "created_at": float(row[3] or 0),
        "updated_at": float(row[4] or 0),
        "message_count": int(row[5] or 0),
    }


class SqliteConversationStore:
    """SQLite-backed store with the same interface as the Redis ConversationStore."""

    def __init__(self) -> None:
        """No persistent connection; each op opens one (cheap, thread-safe)."""

    async def create(self, user_id: str, title: str | None = None) -> dict[str, Any]:
        """Create a conversation; returns its metadata dict."""

        def _do() -> dict[str, Any]:
            conv_id = uuid.uuid4().hex
            now = _now()
            with _connect() as c:
                c.execute(
                    "INSERT INTO conversations VALUES (?,?,?,?,?,0)",
                    (conv_id, title or _DEFAULT_TITLE, user_id, now, now),
                )
            return {
                "id": conv_id,
                "title": title or _DEFAULT_TITLE,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
            }

        return await asyncio.to_thread(_do)

    async def append(self, conv_id: str, role: str, content: str) -> bool:
        """Append a message; auto-titles from the first user message. Best-effort."""

        def _do() -> bool:
            now = _now()
            with _connect() as c:
                row = c.execute(
                    "SELECT title, message_count, user_id FROM conversations WHERE id=?",
                    (conv_id,),
                ).fetchone()
                if row is None:
                    c.execute(
                        "INSERT INTO conversations VALUES (?,?,?,?,?,0)",
                        (conv_id, _DEFAULT_TITLE, "default", now, now),
                    )
                    title, count = _DEFAULT_TITLE, 0
                else:
                    title, count = row[0], int(row[1] or 0)
                seq = count + 1
                c.execute(
                    "INSERT INTO messages VALUES (?,?,?,?,?)", (conv_id, seq, role, content, now)
                )
                new_title = title
                if role == "user" and title in (None, "", _DEFAULT_TITLE):
                    new_title = _derive_title(content)
                c.execute(
                    "UPDATE conversations SET message_count=?, updated_at=?, title=? WHERE id=?",
                    (seq, now, new_title, conv_id),
                )
                c.execute(
                    "DELETE FROM messages WHERE conv_id=? AND seq<=?",
                    (conv_id, seq - _MAX_MESSAGES),
                )
            return True

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return False

    async def messages(self, conv_id: str) -> list[dict[str, Any]]:
        """Ordered messages for a conversation."""

        def _do() -> list[dict[str, Any]]:
            with _connect() as c:
                rows = c.execute(
                    "SELECT role, content, ts FROM messages WHERE conv_id=? ORDER BY seq",
                    (conv_id,),
                ).fetchall()
            return [{"role": r[0], "content": r[1], "ts": r[2]} for r in rows]

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return []

    async def get_meta(self, conv_id: str) -> dict[str, Any] | None:
        """Conversation metadata or None."""

        def _do() -> dict[str, Any] | None:
            with _connect() as c:
                row = c.execute(
                    "SELECT id,title,user_id,created_at,updated_at,message_count "
                    "FROM conversations WHERE id=?",
                    (conv_id,),
                ).fetchone()
            return _meta_row(row) if row else None

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return None

    async def list(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """A user's conversations, most-recently-updated first."""

        def _do() -> list[dict[str, Any]]:
            with _connect() as c:
                rows = c.execute(
                    "SELECT id,title,user_id,created_at,updated_at,message_count "
                    "FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [_meta_row(r) for r in rows]

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return []

    async def rename(self, conv_id: str, title: str) -> bool:
        """Rename a conversation."""

        def _do() -> bool:
            new_title = title.strip()[:120] or _DEFAULT_TITLE
            with _connect() as c:
                cur = c.execute("UPDATE conversations SET title=? WHERE id=?", (new_title, conv_id))
                return cur.rowcount > 0

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return False

    async def delete(self, conv_id: str) -> bool:
        """Delete a conversation and its messages."""

        def _do() -> bool:
            with _connect() as c:
                c.execute("DELETE FROM messages WHERE conv_id=?", (conv_id,))
                c.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            return True

        try:
            return await asyncio.to_thread(_do)
        except Exception:
            return False

    async def close(self) -> None:
        """No persistent connection to close."""
        return
