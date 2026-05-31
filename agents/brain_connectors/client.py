"""MCP client manager — connects KIA to external MCP servers (connectors).

This is the inverse of ``mcp/server.py`` (which exposes KIA AS a server). Here KIA
acts as an MCP CLIENT: it launches/connects configured MCP servers over stdio,
discovers their tools, and executes tool calls on behalf of the model.

Config is a JSON file (see ``connectors.example.json``) mirroring the shape of
Claude's MCP config: a ``mcpServers`` map of name -> {command, args, env}.
"""

from __future__ import annotations

import json
import os
from contextlib import AsyncExitStack
from typing import Any

# The MCP SDK is imported lazily inside methods so importing this module never
# fails when the optional dependency or a server is unavailable (keeps CI/build green).


class MCPConnectorManager:
    """Launches configured MCP servers and proxies tool discovery + calls."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the manager.

        Args:
            config_path: Path to the connectors JSON config. Defaults to
                ``$KIA_CONNECTORS_CONFIG`` or ``/app/data/connectors.json``.
        """
        env_path = os.getenv("KIA_CONNECTORS_CONFIG") or "/app/data/connectors.json"
        self.config_path: str = config_path or env_path
        self._stack: AsyncExitStack | None = None
        # server name -> ClientSession
        self._sessions: dict[str, Any] = {}
        # tool name -> server name (tools are namespaced "server.tool")
        self._tool_index: dict[str, str] = {}
        self._tools: list[dict[str, Any]] = []

    def _load_config(self) -> dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
            servers = data.get("mcpServers", {})
            return servers if isinstance(servers, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    async def connect(self) -> list[dict[str, Any]]:
        """Launch + connect all configured servers; return discovered tools (OpenAI fmt)."""
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        servers = self._load_config()
        if not servers:
            return []
        self._stack = AsyncExitStack()
        for name, cfg in servers.items():
            try:
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=cfg.get("args", []),
                    env={**os.environ, **cfg.get("env", {})},
                )
                read, write = await self._stack.enter_async_context(stdio_client(params))
                session = await self._stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self._sessions[name] = session
                listed = await session.list_tools()
                for tool in listed.tools:
                    qualified = f"{name}.{tool.name}"
                    self._tool_index[qualified] = name
                    self._tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": qualified,
                                "description": tool.description or "",
                                "parameters": tool.inputSchema or {"type": "object"},
                            },
                        }
                    )
            except Exception:
                # A broken connector must not take down the whole manager.
                continue
        return self._tools

    @property
    def tools(self) -> list[dict[str, Any]]:
        """OpenAI-format tool schemas for all connected servers."""
        return self._tools

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> str:
        """Execute ``server.tool`` with arguments; return the text result."""
        server = self._tool_index.get(qualified_name)
        if server is None or server not in self._sessions:
            return f"[error: unknown tool '{qualified_name}']"
        tool_name = qualified_name.split(".", 1)[1]
        try:
            result = await self._sessions[server].call_tool(tool_name, arguments)
        except Exception as e:  # noqa: BLE001
            return f"[error calling {qualified_name}: {e}]"
        parts: list[str] = []
        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts) if parts else "[no text content]"

    async def close(self) -> None:
        """Shut down all server connections."""
        if self._stack is not None:
            try:
                await self._stack.aclose()
            except Exception:
                pass
            self._stack = None
        self._sessions.clear()
