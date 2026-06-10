"""Verify every configured MCP connector launches and lists tools.

Usage: python scripts/verify_connectors.py [config_path]
Connects to each server INDIVIDUALLY (so one broken server can't hide behind
the manager's skip-on-failure behavior) and prints its tool count + names.
"""

import asyncio
import json
import os
import sys


async def probe(name: str, cfg: dict) -> tuple[str, int, list[str], str]:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg.get("args", []),
        env={**os.environ, **cfg.get("env", {})},
    )
    try:
        async with asyncio.timeout(120):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    names = [t.name for t in listed.tools]
                    return name, len(names), names, "ok"
    except Exception as e:  # noqa: BLE001
        return name, 0, [], f"FAILED: {type(e).__name__}: {e}"


async def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\dev\data\connectors.json"
    with open(path, encoding="utf-8") as f:
        servers = json.load(f)["mcpServers"]
    total = 0
    failures = 0
    for name, cfg in servers.items():
        sname, count, names, status = await probe(name, cfg)
        total += count
        if status != "ok":
            failures += 1
        shown = ", ".join(names[:8]) + (" ..." if len(names) > 8 else "")
        print(f"{sname:20s} {status:8s} {count:3d} tools  {shown}")
    print(f"\nTOTAL: {total} tools, {failures} failed server(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
