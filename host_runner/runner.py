"""KIA Host Command Runner — runs APPROVED shell commands on this machine.

⚠️  SECURITY: this process executes shell commands sent to it. It is the ONLY
component that can touch your real OS (KIA's backend runs in Docker and cannot).
Protect it:
  * It binds 0.0.0.0 by default so KIA's container can reach it via
    host.docker.internal (a loopback-only bind is NOT reachable from Docker).
    Because of that it IS reachable from your LAN — so the shared token is the
    gate. Use a long random token, and ideally firewall the port to localhost +
    the Docker subnet. Set RUNNER_HOST=127.0.0.1 if you don't run KIA in Docker.
  * Every request must carry the shared secret in the `X-Runner-Token` header.
  * KIA's backend ONLY sends commands you explicitly approved in the chat UI.
  * Every command is logged to host_runner.log.

Run it ON the host (NOT in Docker), in a terminal you control:

    Windows (PowerShell):
        $env:RUNNER_TOKEN = "choose-a-long-random-secret"
        python host_runner\\runner.py

    macOS/Linux:
        RUNNER_TOKEN="choose-a-long-random-secret" python3 host_runner/runner.py

Then set the same token + URL in KIA's .env (see host_runner/README.md):
    EXEC_ENABLED=true
    HOST_RUNNER_URL=http://host.docker.internal:8765
    HOST_RUNNER_TOKEN=choose-a-long-random-secret

Stop it (Ctrl+C) when you're done. Treat the token like a password.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = int(os.environ.get("RUNNER_PORT", "8765"))
HOST = os.environ.get("RUNNER_HOST", "0.0.0.0")
TOKEN = os.environ.get("RUNNER_TOKEN", "")
MAX_TIMEOUT = 900  # seconds, hard cap per command
IS_WINDOWS = platform.system() == "Windows"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "host_runner.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("kia-runner")


def _shell_argv(command: str) -> list[str]:
    """Build the argv to run a command string in the platform's shell."""
    if IS_WINDOWS:
        # PowerShell so installers / winget / choco work as expected.
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    return ["/bin/bash", "-lc", command]


def _run_command(command: str, timeout: int) -> dict[str, Any]:
    """Execute one command, capturing output. Never raises for the caller."""
    timeout = max(1, min(timeout, MAX_TIMEOUT))
    start = time.monotonic()
    try:
        proc = subprocess.run(
            _shell_argv(command),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
            "duration_ms": round((time.monotonic() - start) * 1000, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"command timed out after {timeout}s",
            "duration_ms": round((time.monotonic() - start) * 1000, 1),
        }
    except Exception as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
            "duration_ms": round((time.monotonic() - start) * 1000, 1),
        }


class Handler(BaseHTTPRequestHandler):
    """Minimal request handler: GET /health, POST /run."""

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default noisy logging
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok", "platform": platform.system()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/run":
            self._send(404, {"error": "not found"})
            return
        if not TOKEN:
            self._send(500, {"error": "RUNNER_TOKEN not set on the runner"})
            return
        if self.headers.get("X-Runner-Token") != TOKEN:
            log.warning("REJECTED request with bad/missing token from %s", self.client_address[0])
            self._send(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON"})
            return
        command = str(data.get("command", "")).strip()
        if not command:
            self._send(400, {"error": "empty command"})
            return
        timeout = int(data.get("timeout", 300))
        log.info("RUN: %s", command)
        result = _run_command(command, timeout)
        log.info("  -> exit=%s ok=%s (%sms)", result["exit_code"], result["ok"], result["duration_ms"])
        self._send(200, result)


def main() -> None:
    """Start the runner with a loud, honest banner."""
    if not TOKEN:
        print("!! RUNNER_TOKEN is not set. Set it before starting (see the file header).")
        sys.exit(1)
    print("=" * 70)
    print(" KIA Host Command Runner")
    print(f"   listening on http://{HOST}:{PORT}   platform={platform.system()}")
    print("   It will run APPROVED shell commands on THIS machine.")
    print("   Keep this terminal in view. Ctrl+C to stop. Token required per request.")
    if HOST == "0.0.0.0":
        print("   NOTE: bound to all interfaces so Docker can reach it — the token is")
        print("         the only guard. Use a long secret and firewall the port.")
    print("=" * 70)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
