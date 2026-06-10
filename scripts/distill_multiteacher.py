#!/usr/bin/env python3
"""Multi-teacher distillation for KIA (with question-level dedupe + domain routing).

Each domain is answered by ONE best teacher (no 39 models re-answering the same
prompt). Results merge into data/kia_dataset.jsonl, deduped BY QUESTION so the same
question never appears twice.

Usage (PowerShell):
  $env:TEACHER_KEY="<ollama key>"
  python scripts/distill_multiteacher.py               # curated teachers.json
  python scripts/distill_multiteacher.py --auto        # pick ONE best model per domain
  python scripts/distill_multiteacher.py --dedupe-only # just clean the existing dataset
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request

DEFAULT_URL = "https://ollama.com/v1"

# substring -> domain (for --auto). Order = preference when picking one per domain.
SPECIALITY_MAP = [
    ("qwen3-coder", "coding"),
    ("devstral", "coding"),
    ("coder", "coding"),
    ("code", "coding"),
    ("deepseek-v4-pro", "reasoning"),
    ("deepseek", "reasoning"),
    ("kimi", "reasoning"),
    ("nemotron", "reasoning"),
    ("minimax", "reasoning"),
    ("cogito", "reasoning"),
    ("gpt-oss:120b", "general"),
    ("glm-5", "general"),
    ("gemma", "general"),
    ("mistral", "general"),
    ("gpt-oss", "general"),
    ("glm", "general"),
]
DEFAULT_PROMPTS = {
    "coding": "training/prompts/coding.txt",
    "reasoning": "training/prompts/reasoning.txt",
    "math": "training/prompts/math.txt",
    "general": "training/prompts/general.txt",
}


def teacher_answer(url: str, model: str, key: str, prompt: str) -> str:
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    ).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def list_models(url: str, key: str) -> list[str]:
    req = urllib.request.Request(
        url.rstrip("/") + "/models", headers={"Authorization": "Bearer " + key}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return [m["id"] for m in json.loads(r.read().decode()).get("data", [])]


def norm_q(text: str) -> str:
    """Normalize a question for dedupe: lowercase, collapse whitespace, strip punctuation."""
    if isinstance(text, list):
        text = " ".join(str(p) for p in text)
    return re.sub(r"\s+", " ", str(text).lower()).strip(" .?!:\n\t")


def first_user(rec: dict) -> str:
    for m in rec.get("messages", []):
        if m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def dedupe_by_question(records: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in records:
        k = norm_q(first_user(r))
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def load_jsonl(path: str) -> list[dict]:
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
    return out


def load_prompts(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def domain_for(model: str) -> str:
    low = model.lower()
    for sub, dom in SPECIALITY_MAP:
        if sub in low:
            return dom
    return "general"


def write_out(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="training/teachers.json")
    ap.add_argument("--out", default="data/kia_dataset.jsonl")
    ap.add_argument("--key", default=os.getenv("TEACHER_KEY", ""))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--auto", action="store_true")
    ap.add_argument(
        "--dedupe-only",
        action="store_true",
        help="collapse duplicate questions in --out and exit (no teacher calls)",
    )
    args = ap.parse_args()

    if args.dedupe_only:
        recs = load_jsonl(args.out)
        before = len(recs)
        recs = dedupe_by_question(recs)
        write_out(args.out, recs)
        print(f"Deduped {args.out}: {before} -> {len(recs)} unique-question pairs")
        return

    cfg = json.load(open(args.config, encoding="utf-8")) if os.path.exists(args.config) else {}
    url = cfg.get("teacher_url", DEFAULT_URL)
    teachers = cfg.get("teachers", [])

    if args.auto:
        print("--auto: picking ONE best model per domain (avoids duplicate questions).")
        models = list_models(url, args.key)
        best: dict[str, str] = {}
        for sub, dom in SPECIALITY_MAP:  # SPECIALITY_MAP order = preference
            if dom in best:
                continue
            for m in models:
                if sub in m.lower():
                    best[dom] = m
                    break
        teachers = [
            {"model": m, "domain": d, "prompts": DEFAULT_PROMPTS.get(d, "")}
            for d, m in best.items()
        ]
        print("Chosen:", ", ".join(f"{t['domain']}={t['model']}" for t in teachers))

    # one teacher per domain even from a hand-written config (dedupe domains, keep first)
    seen_dom, routed = set(), []
    for t in teachers:
        d = t.get("domain", "general")
        if d in seen_dom:
            print(f"  (skipping extra {d} teacher {t['model']} - one per domain)")
            continue
        seen_dom.add(d)
        routed.append(t)

    records = load_jsonl(args.out)
    print(f"Starting from {len(records)} existing pairs in {args.out}")

    for t in routed:
        model, domain = t["model"], t.get("domain", "general")
        prompts = load_prompts(t.get("prompts", "")) or load_prompts(
            DEFAULT_PROMPTS.get(domain, "")
        )
        if args.limit:
            prompts = prompts[: args.limit]
        if not prompts:
            print(f"  (no prompts for {model}/{domain}, skipping)")
            continue
        print(f"\n== {model}  domain={domain}  prompts={len(prompts)} ==")
        ok = 0
        for p in prompts:
            try:
                ans = teacher_answer(url, model, args.key, p)
            except Exception as e:
                print(f"  !! {model}: {e}")
                continue
            records.append(
                {
                    "messages": [
                        {"role": "user", "content": p},
                        {"role": "assistant", "content": ans},
                    ],
                    "meta": {"domain": domain, "teacher": model},
                }
            )
            ok += 1
            print(f"  + [{ok}/{len(prompts)}] {p[:60]}")

    before = len(records)
    records = dedupe_by_question(records)
    write_out(args.out, records)
    print(f"\nDone. {before} -> {len(records)} unique-question pairs -> {args.out}")


if __name__ == "__main__":
    main()
