#!/usr/bin/env python3
"""Build a KIA fine-tuning dataset (OpenAI 'messages' JSONL) from multiple sources.

Sources:
  1. Captured chats     -- data/kia_train.jsonl (from the live capture loop)
  2. Repo-derived Q&A   -- walk a code tree and ask a TEACHER to answer questions
                           about each file (only if --teacher-url is given)

The teacher is any OpenAI-compatible endpoint, so it works with:
  - Ollama Cloud:   --teacher-url https://ollama.com/v1  --teacher-model gpt-oss:120b  --teacher-key <key>
  - A frontier API: --teacher-url https://api.openai.com/v1 (etc.)
  - Local KIA:      --teacher-url http://localhost:8000/v1 --teacher-model kia-brain

Output: data/kia_dataset.jsonl  (deduped, ready for training/kia_finetune.py)

Standard library only. Usage:
  python scripts/build_dataset.py                         # just merge captured chats
  python scripts/build_dataset.py --repo C:\\dev\\agents \\
      --teacher-url https://ollama.com/v1 --teacher-model gpt-oss:120b --teacher-key $OLLAMA_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "out",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    "bin",
    "obj",
    "data",
}
EXTS = {".py", ".js", ".ts", ".tsx", ".vue", ".cs", ".go", ".rs", ".java", ".sql"}
MAX_BYTES = 120_000


def teacher_answer(url: str, model: str, key: str, prompt: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    ).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def load_captured(path: str) -> list[dict]:
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("messages"):
                        out.append({"messages": rec["messages"]})
                except json.JSONDecodeError:
                    continue
    return out


QUESTION_TEMPLATES = [
    "In this codebase, what does the file `{rel}` do? Explain its responsibilities and key functions.",
    "How do I use the main class or function defined in `{rel}`? Give a short, correct example.",
    "What are the important implementation details, edge cases, or gotchas in `{rel}`?",
    "Write a concise unit test for a key function in `{rel}`.",
]


def repo_pairs(root: str, url: str, model: str, key: str, per_file: int = 3) -> list[dict]:
    pairs = []
    templates = QUESTION_TEMPLATES[: max(1, min(per_file, len(QUESTION_TEMPLATES)))]
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in EXTS:
                continue
            full = os.path.join(dp, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    continue
                with open(full, encoding="utf-8") as f:
                    code = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if not code.strip():
                continue
            for tmpl in templates:
                q = tmpl.format(rel=rel)
                ctx = (
                    f"You are studying Kiran's codebase. Answer using only this file.\n\n"
                    f"File: {rel}\n```\n{code[:MAX_BYTES]}\n```\n\nQuestion: {q}"
                )
                try:
                    ans = teacher_answer(url, model, key, ctx)
                except Exception as e:
                    print(f"  !! teacher failed on {rel} ({q[:40]}...): {e}")
                    continue
                pairs.append(
                    {
                        "messages": [
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": ans},
                        ]
                    }
                )
            print(f"  + {rel}  ({len(templates)} q)")
    return pairs


def dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in records:
        msgs = r.get("messages", [])
        key = json.dumps(msgs, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captured", default="data/kia_train.jsonl")
    ap.add_argument("--out", default="data/kia_dataset.jsonl")
    ap.add_argument("--repo", default="")
    ap.add_argument("--teacher-url", default="")
    ap.add_argument("--teacher-model", default="")
    ap.add_argument("--teacher-key", default=os.getenv("TEACHER_KEY", ""))
    ap.add_argument("--per-file", type=int, default=3, help="questions per file (1-4)")
    args = ap.parse_args()

    records = load_captured(args.captured)
    print(f"Loaded {len(records)} captured pairs from {args.captured}")

    if args.repo:
        if not args.teacher_url or not args.teacher_model:
            print("--repo needs --teacher-url and --teacher-model; skipping repo pairs.")
        else:
            print(f"Generating repo Q&A from {args.repo} via teacher {args.teacher_model}...")
            records += repo_pairs(
                args.repo, args.teacher_url, args.teacher_model, args.teacher_key, args.per_file
            )

    records = dedupe(records)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(records)} unique pairs -> {args.out}")


if __name__ == "__main__":
    main()
