#!/usr/bin/env python3
"""Index a code tree into KIA's knowledge base via the local /knowledge/ingest API.

Usage:
    python scripts/index_codebase.py [ROOT] [--api http://localhost:8000]

Walks ROOT (default: current directory), sending each eligible source file to KIA
so it can retrieve from your code. Skips junk dirs, lock files, and oversized or
binary files. Standard library only (no pip installs needed).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API = "http://localhost:8000"
MAX_BYTES = 400_000

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "dist", "build", "out",
    ".next", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "target", "bin", "obj", ".idea", ".vscode", "coverage", ".turbo", ".cache",
    "site-packages", ".gradle", "vendor",
}
SKIP_FILES = {
    "uv.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
}
EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".cs", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".cc", ".h", ".hpp", ".sql", ".sh", ".ps1",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".json",
}
EXTRA_NAMES = {"Dockerfile", "Makefile"}


def eligible(name: str) -> bool:
    if name in SKIP_FILES:
        return False
    if name.endswith((".min.js", ".min.css", ".map")):
        return False
    _, ext = os.path.splitext(name)
    return ext.lower() in EXTS or name in EXTRA_NAMES


def clear_index(api: str) -> None:
    req = urllib.request.Request(
        api.rstrip("/") + "/api/v1/knowledge/clear", data=b"", method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        r.read()


def post(api: str, content: str, source: str) -> int:
    data = json.dumps({"content": content, "source": source}).encode()
    req = urllib.request.Request(
        api.rstrip("/") + "/api/v1/knowledge/ingest",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        body = json.loads(r.read().decode())
    return len(body.get("chunk_ids", []))


def main() -> None:
    args = list(sys.argv[1:])
    api = API
    root = "."
    reindex = False
    i = 0
    while i < len(args):
        if args[i] == "--api" and i + 1 < len(args):
            api = args[i + 1]
            i += 2
        elif args[i] == "--reindex":
            reindex = True
            i += 1
        else:
            root = args[i]
            i += 1
    root = os.path.abspath(root)
    print(f"Indexing {root} -> {api}")
    if reindex:
        print("Clearing existing index (--reindex)...")
        try:
            clear_index(api)
            print("  cleared.")
        except Exception as e:
            print(f"  clear failed: {e}")
    ok = skipped = failed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not eligible(name):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    skipped += 1
                    continue
                with open(full, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                skipped += 1
                continue
            if not content.strip():
                skipped += 1
                continue
            try:
                n = post(api, content, rel)
                ok += 1
                print(f"  [{ok}] {rel}  ({n} chunks)")
            except Exception as e:
                failed += 1
                print(f"  !! {rel}: {e}")
    print(f"\nDone. indexed={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
