"""Tools the build agent can call, all confined to a single working directory.

File operations run in-process (KIA's native backend shares the host filesystem),
so writes are exact (no shell-quoting hazards). Shell commands go through the
token-gated host runner, executed with the working directory as CWD. A danger
rating on every action lets the loop auto-run safe steps and gate risky ones.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any

import httpx

from brain_exec.runner_client import HostRunnerClient

# Per-call output caps so a noisy command/file can't blow up the LLM context.
_MAX_READ = 60_000
_MAX_LIST = 400
_MAX_FETCH = 40_000

# Command patterns that must always be approved (destructive / system / network-install).
_HIGH_PATTERNS = [
    r"\brm\b",
    r"\brmdir\b",
    r"\bdel\b",
    r"Remove-Item",
    r"\bRemove-",
    r"\bformat\b",
    r"\bmkfs\b",
    r"\bdd\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bReset-",
    r"\bStop-Computer",
    r"\bwinget\b",
    r"\bchoco\b",
    r"\bscoop\b",
    r"\bnpm\s+(i|install)\s+-g",
    r"\bpip\s+install\b",
    r"\bapt(-get)?\s+install",
    r"\bbrew\s+install",
    r"\breg\b\s+(add|delete)",
    r"\bsc\b\s+(create|delete|config)",
    r"\bnetsh\b",
    r"\bgit\s+push\b.*--force",
    r"\bgit\s+push\s+-f\b",
    r"\bSet-ExecutionPolicy",
    r"\bNew-Service",
    r"\bcurl\b.*\|\s*(sh|bash|iex)",
    r"Invoke-WebRequest.*\|\s*iex",
    r"\biex\b",
]
# Patterns that are clearly read-only / safe.
_LOW_PATTERNS = [
    r"^\s*(ls|dir|cat|type|Get-Content|Get-ChildItem|pwd|echo|where|which)\b",
    r"^\s*git\s+(status|log|diff|branch|show)\b",
    r"^\s*(node|python|py)\s+--version",
    r"^\s*(npm|pip)\s+(--version|list)\b",
]


def classify_command(command: str) -> str:
    """Rate a shell command 'low' | 'medium' | 'high' for the approval gate."""
    for pat in _HIGH_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            return "high"
    for pat in _LOW_PATTERNS:
        if re.search(pat, command):
            return "low"
    return "medium"


class BuildToolError(Exception):
    """Raised on a disallowed/invalid tool call (e.g. path escaping the workdir)."""


class BuildTools:
    """File + shell + fetch tools jailed to ``root`` (an absolute working directory)."""

    def __init__(self, root: str) -> None:
        """Pin the agent to ``root``; all file paths must resolve inside it."""
        self.root = os.path.abspath(root)
        self._runner = HostRunnerClient()

    # -- path safety --------------------------------------------------------
    def _resolve(self, path: str) -> str:
        """Resolve ``path`` (relative to root or absolute) and ensure it stays inside root."""
        p = path if os.path.isabs(path) else os.path.join(self.root, path)
        full = os.path.abspath(p)
        if full != self.root and not full.startswith(self.root + os.sep):
            raise BuildToolError(f"path '{path}' is outside the working directory")
        return full

    def _rel(self, full: str) -> str:
        return os.path.relpath(full, self.root)

    # -- file tools ---------------------------------------------------------
    def read_file(self, path: str) -> str:
        """Return the file's text (truncated), or a clear error string."""
        full = self._resolve(path)
        if not os.path.isfile(full):
            return f"ERROR: no such file: {self._rel(full)}"
        with open(full, encoding="utf-8", errors="replace") as f:
            data = f.read(_MAX_READ + 1)
        if len(data) > _MAX_READ:
            return data[:_MAX_READ] + "\n…[truncated]"
        return data

    def write_file(self, path: str, content: str) -> str:
        """Create/overwrite a file with exact content; makes parent dirs as needed."""
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return f"wrote {len(content)} bytes to {self._rel(full)}"

    def edit_file(self, path: str, old: str, new: str) -> str:
        """Replace the first exact occurrence of ``old`` with ``new`` (must be unique)."""
        full = self._resolve(path)
        if not os.path.isfile(full):
            return f"ERROR: no such file: {self._rel(full)}"
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
        count = text.count(old)
        if count == 0:
            return "ERROR: old string not found (it must match exactly, incl. whitespace)"
        if count > 1:
            return f"ERROR: old string is not unique ({count} matches) — include more context"
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace(old, new, 1))
        return f"edited {self._rel(full)} (1 replacement)"

    def list_dir(self, path: str = ".") -> str:
        """List a directory's entries (dirs marked with a trailing slash)."""
        full = self._resolve(path)
        if not os.path.isdir(full):
            return f"ERROR: not a directory: {self._rel(full)}"
        entries: list[str] = []
        for name in sorted(os.listdir(full)):
            if name in (".git", "node_modules", "__pycache__", ".venv"):
                entries.append(name + "/  [skipped]")
                continue
            entries.append(name + ("/" if os.path.isdir(os.path.join(full, name)) else ""))
        listing = "\n".join(entries[:_MAX_LIST])
        if len(entries) > _MAX_LIST:
            listing += f"\n…[{len(entries) - _MAX_LIST} more]"
        return listing or "(empty)"

    def search(self, query: str, glob: str = "") -> str:
        """Grep for a regex/text across files under the workdir; returns file:line matches."""
        try:
            pat = re.compile(query)
        except re.error as e:
            return f"ERROR: bad regex: {e}"
        skip = {".git", "node_modules", "__pycache__", ".venv", "dist", ".mypy_cache"}
        hits: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                if glob and not fnmatch.fnmatch(fn, glob):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    with open(full, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if pat.search(line):
                                hits.append(f"{self._rel(full)}:{i}: {line.strip()[:200]}")
                                if len(hits) >= 200:
                                    return "\n".join(hits) + "\n…[truncated]"
                except OSError:
                    continue
        return "\n".join(hits) if hits else "(no matches)"

    # -- shell + web --------------------------------------------------------
    async def run_command(self, command: str, timeout: int | None = None) -> dict[str, Any]:
        """Run a shell command on the host with the working directory as CWD."""
        # cd into the workdir first so relative paths in the command resolve there.
        wrapped = f"Set-Location -LiteralPath '{self.root}'; {command}"
        return await self._runner.run(wrapped, timeout=timeout)

    async def fetch_url(self, url: str) -> str:
        """GET a URL and return text (truncated). For docs/reference during a build."""
        if not url.lower().startswith(("http://", "https://")):
            return "ERROR: only http(s) URLs are allowed"
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url)
                text = resp.text
            return text[:_MAX_FETCH] + ("\n…[truncated]" if len(text) > _MAX_FETCH else "")
        except Exception as e:  # noqa: BLE001 - report fetch failures to the loop as text
            return f"ERROR fetching {url}: {type(e).__name__}: {e}"
