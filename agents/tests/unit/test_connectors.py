"""Tests for the connector read-only gate and the persistent pool."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from brain_connectors import pool
from brain_connectors.client import is_readonly_tool, readonly_subset


class TestReadonlyGate:
    """Classification of tools into ambient-safe (read-only) vs gated."""

    @pytest.mark.parametrize(
        "name",
        [
            "filesystem.read_file",
            "filesystem.read_multiple_files",
            "filesystem.list_directory",
            "filesystem.directory_tree",
            "filesystem.search_files",
            "filesystem.get_file_info",
            "fetch.fetch",
            "web-search.search",
            "web-search.fetch_content",
            "memory.read_graph",
            "memory.search_nodes",
            "memory.open_nodes",
            "sequential-thinking.sequentialthinking",
            "time.get_current_time",
            "time.convert_time",
            "github.get_file_contents",
            "github.search_repositories",
            "github.list_issues",
        ],
    )
    def test_readonly_tools_allowed(self, name: str) -> None:
        assert is_readonly_tool(name), name

    @pytest.mark.parametrize(
        "name",
        [
            "filesystem.write_file",
            "filesystem.edit_file",
            "filesystem.create_directory",
            "filesystem.move_file",
            "memory.create_entities",
            "memory.add_observations",
            "memory.delete_entities",
            "github.create_or_update_file",
            "github.push_files",
            "github.create_issue",
            "github.merge_pull_request",
            "github.fork_repository",
            "anything.execute_command",
            "anything.run_script",
        ],
    )
    def test_mutating_tools_blocked(self, name: str) -> None:
        assert not is_readonly_tool(name), name

    def test_readonly_subset_filters_schemas(self) -> None:
        tools = [
            {"type": "function", "function": {"name": "fs.read_file", "parameters": {}}},
            {"type": "function", "function": {"name": "fs.write_file", "parameters": {}}},
        ]
        names = [t["function"]["name"] for t in readonly_subset(tools)]
        assert names == ["fs.read_file"]


class FakeManager:
    """Stands in for MCPConnectorManager in pool tests."""

    instances: list["FakeManager"] = []
    tools_to_serve: list[dict[str, Any]] = [{"function": {"name": "x.read_file"}}]

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path
        self.connected = False
        self.closed = False
        self.tools: list[dict[str, Any]] = []
        FakeManager.instances.append(self)

    async def connect(self) -> list[dict[str, Any]]:
        self.connected = True
        self.tools = list(FakeManager.tools_to_serve)
        return self.tools

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real config file + FakeManager wired into the pool module."""
    cfg = tmp_path / "connectors.json"
    cfg.write_text(json.dumps({"mcpServers": {"x": {"command": "noop"}}}))
    monkeypatch.setenv("KIA_CONNECTORS_CONFIG", str(cfg))
    monkeypatch.setattr(pool, "MCPConnectorManager", FakeManager)
    FakeManager.instances = []
    FakeManager.tools_to_serve = [{"function": {"name": "x.read_file"}}]
    return cfg


class TestConnectorPool:
    """Persistent pool lifecycle: reuse, config reload, shutdown."""

    @pytest.mark.asyncio
    async def test_pool_connects_and_reuses(self, config_file: Path) -> None:
        try:
            m1 = await pool.get_pool()
            m2 = await pool.get_pool()
            assert m1 is not None and m1 is m2
            assert len(FakeManager.instances) == 1
            assert not FakeManager.instances[0].closed
        finally:
            await pool.close_pool()
        assert FakeManager.instances[0].closed

    @pytest.mark.asyncio
    async def test_pool_reconnects_on_config_change(self, config_file: Path) -> None:
        try:
            m1 = await pool.get_pool()
            assert m1 is not None
            # Touch the config with a different mtime.
            await asyncio.sleep(0.02)
            config_file.write_text(json.dumps({"mcpServers": {"y": {"command": "noop"}}}))
            import os

            os.utime(config_file, (1, 1))  # force an mtime change
            m2 = await pool.get_pool()
            assert m2 is not None and m2 is not m1
            assert FakeManager.instances[0].closed  # old one shut down
            assert len(FakeManager.instances) == 2
        finally:
            await pool.close_pool()

    @pytest.mark.asyncio
    async def test_pool_none_when_no_tools(self, config_file: Path) -> None:
        FakeManager.tools_to_serve = []
        try:
            assert await pool.get_pool() is None
            assert FakeManager.instances[0].closed
        finally:
            await pool.close_pool()

    @pytest.mark.asyncio
    async def test_pool_none_when_no_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KIA_CONNECTORS_CONFIG", "C:/does/not/exist.json")
        assert await pool.get_pool() is None
