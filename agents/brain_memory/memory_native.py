"""Native, embedded memory backends (SQLite) for the no-Docker deployment.

Episodic, semantic (facts), and procedural (skills) memory normally live in
Weaviate / FalkorDB / Redis. Those servers don't run in the native deployment, so
these SQLite-backed classes provide the same async API against ``settings.sqlite_path``
(the same file as conversations) — making all of KIA's memory persistent and
provider-free. Factories pick the native backend when STORAGE_BACKEND != "redis".
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Any, Protocol

from brain_core.config import settings
from brain_memory.models import Episode, Fact, Skill


def _native() -> bool:
    """True when running the embedded (no-server) deployment."""
    return (settings.storage_backend or "redis").lower() != "redis"


class EpisodicLike(Protocol):
    """Common episodic-memory interface (server- or SQLite-backed)."""

    async def store_episode(self, episode: Episode) -> str: ...

    async def retrieve_episodes(self, query: str, limit: int = 10) -> list[Episode]: ...

    async def retrieve_recent(self, limit: int = 10) -> list[Episode]: ...

    async def close(self) -> None: ...


class SemanticLike(Protocol):
    """Common semantic-memory (facts) interface."""

    async def store_fact(self, fact: Fact) -> str: ...

    async def query_facts(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        limit: int = 10,
    ) -> list[Fact]: ...

    async def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None: ...

    async def store_entity(
        self, entity_type: str, entity_id: str, data: dict[str, Any]
    ) -> None: ...

    async def get_patterns(self) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


class ProceduralLike(Protocol):
    """Common procedural-memory (skills) interface."""

    async def store_skill(self, skill: Skill) -> str: ...

    async def list_skills(self) -> list[Skill]: ...

    async def close(self) -> None: ...


class WorkingLike(Protocol):
    """Common working-memory interface."""

    async def set(self, session_id: str, key: str, value: Any, ttl: int = 3600) -> None: ...

    async def get(self, session_id: str, key: str) -> Any: ...

    async def delete(self, session_id: str, key: str) -> None: ...

    async def clear_session(self, session_id: str) -> None: ...

    async def close(self) -> None: ...


def _connect() -> sqlite3.Connection:
    """Open the shared SQLite file and ensure the memory tables exist."""
    path = settings.sqlite_path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id TEXT PRIMARY KEY, content TEXT, context TEXT, metadata TEXT, ts REAL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodes(ts)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, predicate TEXT, "
        "object TEXT, confidence REAL, ts REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS skills ("
        "id TEXT PRIMARY KEY, name TEXT, description TEXT, steps TEXT, "
        "success_rate REAL, usage_count INTEGER, created_at REAL, metadata TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entities ("
        "type TEXT, name TEXT, data TEXT, PRIMARY KEY (type, name))"
    )
    return conn


class SqliteEpisodicMemory:
    """Episodic memory in SQLite; keyword (LIKE) + recency retrieval."""

    async def store_episode(self, episode: Episode) -> str:
        """Store an episode; returns its id."""

        def _do() -> str:
            eid = episode.id or uuid.uuid4().hex
            with _connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO episodes VALUES (?,?,?,?,?)",
                    (
                        eid,
                        episode.content,
                        json.dumps(episode.context),
                        json.dumps(episode.metadata),
                        episode.timestamp.timestamp(),
                    ),
                )
            return eid

        return await asyncio.to_thread(_do)

    async def retrieve_episodes(
        self, query: str, limit: int = 10, time_range: tuple[datetime, datetime] | None = None
    ) -> list[Episode]:
        """Retrieve episodes matching ``query`` (substring) most-recent-first."""

        def _do() -> list[Episode]:
            with _connect() as c:
                if query:
                    rows = c.execute(
                        "SELECT id,content,context,metadata,ts FROM episodes "
                        "WHERE content LIKE ? ORDER BY ts DESC LIMIT ?",
                        (f"%{query}%", limit),
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id,content,context,metadata,ts FROM episodes "
                        "ORDER BY ts DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [_row_to_episode(r) for r in rows]

        try:
            return await asyncio.to_thread(_do)
        except Exception:  # noqa: BLE001 - retrieval is best-effort
            return []

    async def retrieve_recent(self, limit: int = 10) -> list[Episode]:
        """Most recent episodes."""
        return await self.retrieve_episodes("", limit=limit)

    async def close(self) -> None:
        """No persistent connection to close."""
        return


class SqliteSemanticMemory:
    """Semantic memory (subject-predicate-object facts) in SQLite."""

    async def store_fact(self, fact: Fact) -> str:
        """Store a fact; returns its row id."""

        def _do() -> str:
            with _connect() as c:
                cur = c.execute(
                    "INSERT INTO facts (subject,predicate,object,confidence,ts) VALUES (?,?,?,?,?)",
                    (fact.subject, fact.predicate, fact.object, fact.confidence, time.time()),
                )
            return str(cur.lastrowid)

        return await asyncio.to_thread(_do)

    async def query_facts(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        limit: int = 10,
    ) -> list[Fact]:
        """Query facts by any combination of subject/predicate/object."""

        def _do() -> list[Fact]:
            clauses: list[str] = []
            params: list[Any] = []
            if subject:
                clauses.append("subject=?")
                params.append(subject)
            if predicate:
                clauses.append("predicate=?")
                params.append(predicate)
            if object:
                clauses.append("object=?")
                params.append(object)
            where = " AND ".join(clauses) if clauses else "1=1"
            params.append(limit)
            sql = (
                "SELECT subject,predicate,object,confidence FROM facts "
                f"WHERE {where} ORDER BY ts DESC LIMIT ?"
            )
            with _connect() as c:
                rows = c.execute(sql, tuple(params)).fetchall()
            return [
                Fact(
                    subject=str(r[0]),
                    predicate=str(r[1]),
                    object=str(r[2]),
                    confidence=float(r[3]),
                )
                for r in rows
            ]

        try:
            return await asyncio.to_thread(_do)
        except Exception:  # noqa: BLE001
            return []

    async def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        """Fetch a stored entity's data dict, or None."""

        def _do() -> dict[str, Any] | None:
            with _connect() as c:
                row = c.execute(
                    "SELECT data FROM entities WHERE type=? AND name=?", (entity_type, entity_id)
                ).fetchone()
            if not row or not row[0]:
                return None
            data: dict[str, Any] = json.loads(row[0])
            return data

        return await asyncio.to_thread(_do)

    async def store_entity(self, entity_type: str, entity_id: str, data: dict[str, Any]) -> None:
        """Create/replace an entity's data dict."""

        def _do() -> None:
            with _connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO entities VALUES (?,?,?)",
                    (entity_type, entity_id, json.dumps(data)),
                )

        await asyncio.to_thread(_do)

    async def get_patterns(self) -> list[dict[str, Any]]:
        """Return entities stored under the 'pattern' type."""

        def _do() -> list[dict[str, Any]]:
            with _connect() as c:
                rows = c.execute(
                    "SELECT data FROM entities WHERE type='pattern' LIMIT 10"
                ).fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]

        try:
            return await asyncio.to_thread(_do)
        except Exception:  # noqa: BLE001
            return []

    async def close(self) -> None:
        """No persistent connection to close."""
        return


class SqliteProceduralMemory:
    """Procedural memory (skills/workflows) in SQLite."""

    async def store_skill(self, skill: Skill) -> str:
        """Store/replace a skill; returns its id."""

        def _do() -> str:
            sid = skill.id or f"skill:{skill.name}"
            with _connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO skills VALUES (?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        skill.name,
                        skill.description,
                        json.dumps(skill.steps),
                        skill.success_rate,
                        skill.usage_count,
                        skill.created_at.timestamp(),
                        json.dumps(skill.metadata),
                    ),
                )
            return sid

        return await asyncio.to_thread(_do)

    async def get_skill(self, skill_id: str) -> Skill | None:
        """Fetch one skill by id, or None."""

        def _do() -> Skill | None:
            with _connect() as c:
                row = c.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
            return _row_to_skill(row) if row else None

        return await asyncio.to_thread(_do)

    async def list_skills(self) -> list[Skill]:
        """All stored skills."""

        def _do() -> list[Skill]:
            with _connect() as c:
                rows = c.execute("SELECT * FROM skills ORDER BY created_at DESC").fetchall()
            return [_row_to_skill(r) for r in rows]

        try:
            return await asyncio.to_thread(_do)
        except Exception:  # noqa: BLE001
            return []

    async def close(self) -> None:
        """No persistent connection to close."""
        return


_WORKING: dict[str, tuple[Any, float]] = {}


class InMemoryWorkingMemory:
    """Session-scoped working memory in-process (native replacement for Redis)."""

    async def set(self, session_id: str, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a value with a TTL (seconds)."""
        _WORKING[f"{session_id}:{key}"] = (value, time.time() + ttl)

    async def get(self, session_id: str, key: str) -> Any:
        """Return a value, or None if missing/expired."""
        entry = _WORKING.get(f"{session_id}:{key}")
        if entry is None:
            return None
        value, expiry = entry
        if expiry < time.time():
            _WORKING.pop(f"{session_id}:{key}", None)
            return None
        return value

    async def delete(self, session_id: str, key: str) -> None:
        """Remove a key."""
        _WORKING.pop(f"{session_id}:{key}", None)

    async def clear_session(self, session_id: str) -> None:
        """Drop all keys for a session."""
        for k in [k for k in _WORKING if k.startswith(f"{session_id}:")]:
            _WORKING.pop(k, None)

    async def close(self) -> None:
        """Nothing to close."""
        return


def _row_to_episode(r: tuple[Any, ...]) -> Episode:
    return Episode(
        id=str(r[0]),
        content=str(r[1]),
        context=json.loads(r[2]) if r[2] else {},
        metadata=json.loads(r[3]) if r[3] else {},
        timestamp=datetime.fromtimestamp(float(r[4] or 0)),
    )


def _row_to_skill(r: tuple[Any, ...]) -> Skill:
    return Skill(
        id=str(r[0]),
        name=str(r[1]),
        description=str(r[2]),
        steps=list(json.loads(r[3])) if r[3] else [],
        success_rate=float(r[4] or 0),
        usage_count=int(r[5] or 0),
        created_at=datetime.fromtimestamp(float(r[6] or 0)),
        metadata=json.loads(r[7]) if r[7] else {},
    )


def make_episodic_memory() -> EpisodicLike:
    """Episodic memory: SQLite when native, else Weaviate-backed."""
    if _native():
        return SqliteEpisodicMemory()
    from brain_memory.episodic import EpisodicMemory

    return EpisodicMemory()


def make_semantic_memory() -> SemanticLike:
    """Semantic (facts) memory: SQLite when native, else FalkorDB-backed."""
    if _native():
        return SqliteSemanticMemory()
    from brain_memory.semantic import SemanticMemory

    return SemanticMemory()


def make_procedural_memory() -> ProceduralLike:
    """Procedural (skills) memory: SQLite when native, else Redis-backed."""
    if _native():
        return SqliteProceduralMemory()
    from brain_memory.procedural import ProceduralMemory

    return ProceduralMemory()


def make_working_memory() -> WorkingLike:
    """Working memory: in-process when native, else Redis-backed."""
    if _native():
        return InMemoryWorkingMemory()
    from brain_memory.working import WorkingMemory

    return WorkingMemory()
