#!/usr/bin/env python3
"""Benchmark KIA endpoint latency (run on the machine hosting the backend).

Times each endpoint individually and prints a table. Generation endpoints are
slow on local models — that's expected. Usage:
  python scripts/bench.py
  python scripts/bench.py --api http://localhost:8000 --runs 3
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

API = "http://localhost:8000"


def call(method: str, url: str, body: dict | None = None, timeout: int = 600) -> tuple[float, int]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = -1
    return (time.perf_counter() - t0) * 1000.0, code  # ms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=API)
    ap.add_argument("--runs", type=int, default=2, help="runs per endpoint (median reported)")
    args = ap.parse_args()
    A = args.api.rstrip("/")

    q = urllib.parse.quote
    # (label, method, url, body)
    tests = [
        ("health", "GET", f"{A}/health", None),
        ("status", "GET", f"{A}/api/v1/status", None),
        ("llm/route", "GET", f"{A}/api/v1/llm/route?task_type=code", None),
        ("training/stats", "GET", f"{A}/api/v1/training/stats", None),
        ("memory/facts (query)", "GET", f"{A}/api/v1/memory/facts?limit=5", None),
        ("memory/skills (list)", "GET", f"{A}/api/v1/memory/skills", None),
        ("knowledge/retrieve", "GET", f"{A}/api/v1/knowledge/retrieve?query=test&top_k=5", None),
        (
            "llm/generate (kia)",
            "POST",
            f"{A}/api/v1/llm/generate?prompt={q('Say hello in one word')}&task_type=simple",
            None,
        ),
        (
            "v1 chat (kia)",
            "POST",
            f"{A}/v1/chat/completions",
            {"model": "kia", "messages": [{"role": "user", "content": "Say hello in one word"}]},
        ),
        (
            "v1 chat (kia-coder)",
            "POST",
            f"{A}/v1/chat/completions",
            {
                "model": "kia-coder",
                "messages": [{"role": "user", "content": "Write a one-line Python comment"}],
            },
        ),
        (
            "knowledge/rag (/brain)",
            "POST",
            f"{A}/api/v1/knowledge/rag?question={q('Which TPA is in Birmingham, Alabama?')}",
            None,
        ),
        (
            "v1 chat (kia-brain)",
            "POST",
            f"{A}/v1/chat/completions",
            {
                "model": "kia-brain",
                "messages": [{"role": "user", "content": "Which TPA is in Birmingham, Alabama?"}],
            },
        ),
    ]

    print(f"\nBenchmarking {A}  ({args.runs} run(s) each, median ms)\n")
    print(f"{'endpoint':<26}{'median ms':>12}{'status':>9}")
    print("-" * 47)
    for label, method, url, body in tests:
        times = []
        code = 0
        for _ in range(args.runs):
            ms, code = call(method, url, body)
            times.append(ms)
        times.sort()
        med = times[len(times) // 2]
        flag = "" if code in (200,) else f"  <{code}>"
        print(f"{label:<26}{med:>12.0f}{code:>9}{flag}")
    print(
        "\nNote: generation endpoints (llm/generate, v1 chat) run the local model; "
        "kia-brain also does retrieval + verification (slowest). health/status/route "
        "are pure API (should be single-digit to low-double-digit ms)."
    )


if __name__ == "__main__":
    main()
