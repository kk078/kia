"""Process-wide persistent MCP connector pool.

Without this, every chat message and /connectors call launched ALL configured
MCP servers (npx/uvx subprocesses) and killed them again — multi-second
overhead per request. The pool keeps one connected MCPConnectorManager alive
for the process and reconnects only when the config file changes.

Lifecycle is owned by a dedicated asyncio task: anyio cancel scopes inside the
MCP stdio client must be entered and exited by the SAME task, so requests never
open/close the manager themselves — they signal the owner task instead.
"""

from __future__ import annotations

import asyncio
import os

from brain_connectors.client import MCPConnectorManager
from brain_core.config import settings

_manager: MCPConnectorManager | None = None
_owner: asyncio.Task[None] | None = None
_stop: asyncio.Event | None = None
_mtime: float | None = None
_lock = asyncio.Lock()


def _config_path() -> str | None:
    path = os.getenv("KIA_CONNECTORS_CONFIG") or settings.connectors_config
    return path if path and os.path.exists(path) else None


async def _run_owner(path: str, ready: asyncio.Event, stop: asyncio.Event) -> None:
    """Own the manager's whole lifecycle in one task (connect ... wait ... close)."""
    global _manager
    manager = MCPConnectorManager(path)
    try:
        try:
            await manager.connect()
        finally:
            _manager = manager if manager.tools else None
            ready.set()
        if _manager is None:
            await manager.close()
            return
        await stop.wait()
    finally:
        _manager = None
        await manager.close()


async def get_pool() -> MCPConnectorManager | None:
    """Connected manager with >=1 tool, or None. Reconnects if the config changed."""
    global _owner, _stop, _mtime
    path = _config_path()
    if path is None:
        return None
    mtime = os.path.getmtime(path)
    async with _lock:
        if _owner is not None and not _owner.done() and _mtime == mtime:
            return _manager
        await _shutdown_owner()
        ready = asyncio.Event()
        _stop = asyncio.Event()
        _owner = asyncio.create_task(_run_owner(path, ready, _stop))
        _mtime = mtime
        await ready.wait()
        return _manager


async def _shutdown_owner() -> None:
    """Stop the current owner task and wait for it to close the manager."""
    global _owner, _stop
    if _owner is not None and _stop is not None:
        _stop.set()
        try:
            await _owner
        except Exception:
            pass
    _owner = None
    _stop = None


async def close_pool() -> None:
    """Shut the pool down (app shutdown hook)."""
    global _mtime
    async with _lock:
        await _shutdown_owner()
        _mtime = None
