"""Client for the host command runner (``host_runner/runner.py``).

Sends an approved command to the runner over HTTP with the shared token and returns
its result. Best-effort: an unreachable/misconfigured runner returns a clean error
dict rather than raising, so the UI always shows something actionable.
"""

from __future__ import annotations

from typing import Any

import httpx

from brain_core.config import settings


class HostRunnerClient:
    """Talks to the host-side command runner."""

    def __init__(self) -> None:
        """Read the runner URL + token from settings."""
        self.url = settings.host_runner_url.rstrip("/")
        self.token = settings.host_runner_token

    def _err(self, msg: str) -> dict[str, Any]:
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": msg, "duration_ms": 0.0}

    async def health(self) -> dict[str, Any]:
        """Check whether the runner is reachable."""
        if not self.url:
            return {"ok": False, "error": "HOST_RUNNER_URL not set"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.url}/health")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return {"ok": True, **data}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    async def run(self, command: str, timeout: int | None = None) -> dict[str, Any]:
        """Execute one approved command on the host; returns the runner's result dict."""
        if not self.url:
            return self._err("Host runner not configured (set HOST_RUNNER_URL).")
        if not self.token:
            return self._err("Host runner token not set (HOST_RUNNER_TOKEN).")
        t = timeout or settings.exec_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=float(t) + 10.0) as client:
                resp = await client.post(
                    f"{self.url}/run",
                    headers={"X-Runner-Token": self.token},
                    json={"command": command, "timeout": t},
                )
                if resp.status_code == 401:
                    return self._err("Host runner rejected the token (401).")
                resp.raise_for_status()
                result: dict[str, Any] = resp.json()
                return result
        except httpx.ConnectError:
            return self._err(
                "Host runner not reachable. Is host_runner/runner.py running on the host?"
            )
        except Exception as e:
            return self._err(f"{type(e).__name__}: {e}")
