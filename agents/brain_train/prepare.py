"""Build the SFT dataset from KIA's captured build traces.

Reads data/kia_build_traces.jsonl (one record per successful build, each holding the
full message transcript), converts each into a chat SFT example ({"messages": [...]}),
deduplicates, splits train/val, and writes them under data/sft/. Stdlib-only.

Run:  python -m brain_train.prepare
"""

from __future__ import annotations

import json
import os
import random
from typing import Any

from brain_core.config import settings


def _data_dir() -> str:
    base = settings.training_capture_path or ""
    return os.path.dirname(base) if base else "."


def _traces_path() -> str:
    return os.path.join(_data_dir(), "kia_build_traces.jsonl")


def load_traces(path: str) -> list[dict[str, Any]]:
    """Load JSONL build-trace records (skips blank/corrupt lines)."""
    recs: list[dict[str, Any]] = []
    if not os.path.isfile(path):
        return recs
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                recs.append(obj)
    return recs


def to_example(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one trace into a chat SFT example, or None if unusable."""
    raw = rec.get("messages")
    if not isinstance(raw, list):
        return None
    msgs: list[dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", ""))
        content = str(m.get("content", ""))
        if role in ("system", "user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    if not any(m["role"] == "assistant" for m in msgs):
        return None
    return {"messages": msgs}


def main() -> int:
    """Build train/val JSONL from the trace corpus; print stats."""
    src = _traces_path()
    recs = load_traces(src)

    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in recs:
        ex = to_example(rec)
        if ex is None:
            continue
        key = json.dumps(ex, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        examples.append(ex)

    out = os.path.join(_data_dir(), "sft")
    os.makedirs(out, exist_ok=True)
    random.seed(0)
    random.shuffle(examples)
    n = len(examples)
    n_val = max(1, n // 10) if n >= 10 else 0
    val, train = examples[:n_val], examples[n_val:]

    with open(os.path.join(out, "train.jsonl"), "w", encoding="utf-8") as f:
        for ex in train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(os.path.join(out, "val.jsonl"), "w", encoding="utf-8") as f:
        for ex in val:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"traces read:  {len(recs)}  (from {src})")
    print(f"SFT examples: {n}  (train={len(train)} val={len(val)})  -> {out}")
    if n < 100:
        print(
            f"NOTE: only {n} unique examples; a few hundred is recommended before fine-tuning "
            "has a real effect. Keep running builds/evals to grow the corpus."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
