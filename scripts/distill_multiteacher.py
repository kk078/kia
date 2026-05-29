#!/usr/bin/env python3
"""Multi-teacher distillation for KIA.

Each Ollama model generates training data in its area of strength; the results are
merged + deduped into one dataset that you then fine-tune on (training/kia_finetune.py).

Config: training/teachers.json  -> { teacher_url, teachers:[{model, domain, prompts}] }

Usage (PowerShell):
  $env:TEACHER_KEY="<your ollama key>"
  python scripts/distill_multiteacher.py                       # curated teachers.json
  python scripts/distill_multiteacher.py --auto                # discover ALL /v1/models (warns)
  python scripts/distill_multiteacher.py --out data/kia_dataset.jsonl --limit 15

Honest note: a small student cannot absorb every model. Curate. More teachers != better.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

DEFAULT_URL = "https://ollama.com/v1"

# Substring -> domain, used only by --auto to guess a model's speciality.
SPECIALITY_MAP = [
    ("coder", "coding"), ("code", "coding"), ("devstral", "coding"),
    ("deepseek", "reasoning"), ("kimi", "reasoning"), ("nemotron", "reasoning"),
    ("minimax", "reasoning"), ("qwen3", "reasoning"),
    ("glm", "general"), ("gemma", "general"), ("gpt-oss", "general"),
    ("mistral", "general"), ("ministral", "general"), ("cogito", "reasoning"),
]
DEFAULT_PROMPTS = {"coding": "training/prompts/coding.txt",
                   "reasoning": "training/prompts/reasoning.txt",
                   "general": "training/prompts/general.txt"}


def teacher_answer(url: str, model: str, key: str, prompt: str) -> str:
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.3}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def list_models(url: str, key: str) -> list[str]:
    req = urllib.request.Request(url.rstrip("/") + "/models",
                                 headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [m["id"] for m in json.loads(r.read().decode()).get("data", [])]


def domain_for(model: str) -> str:
    low = model.lower()
    for sub, dom in SPECIALITY_MAP:
        if sub in low:
            return dom
    return "general"


def load_prompts(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def dedupe(records: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in records:
        k = json.dumps(r.get("messages", []), sort_keys=True, ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="training/teachers.json")
    ap.add_argument("--out", default="data/kia_dataset.jsonl")
    ap.add_argument("--key", default=os.getenv("TEACHER_KEY", ""))
    ap.add_argument("--limit", type=int, default=0, help="max prompts per teacher (0=all)")
    ap.add_argument("--auto", action="store_true", help="distill from ALL /v1/models")
    args = ap.parse_args()

    cfg = {}
    if os.path.exists(args.config):
        cfg = json.load(open(args.config, encoding="utf-8"))
    url = cfg.get("teacher_url", DEFAULT_URL)
    teachers = cfg.get("teachers", [])

    if args.auto:
        print("WARNING: --auto distills from EVERY available model. A small student "
              "cannot absorb all specialities; this is token-heavy and hits diminishing "
              "returns. Curating teachers.json is recommended.")
        models = list_models(url, args.key)
        teachers = [{"model": m, "domain": domain_for(m),
                     "prompts": DEFAULT_PROMPTS.get(domain_for(m), DEFAULT_PROMPTS["general"])}
                    for m in models]
        print(f"Discovered {len(teachers)} models.")

    # merge any existing dataset so runs accumulate
    records: list[dict] = []
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        records.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
    print(f"Starting from {len(records)} existing pairs in {args.out}")

    for t in teachers:
        model, domain = t["model"], t.get("domain", "general")
        prompts = load_prompts(t.get("prompts", "")) or load_prompts(
            DEFAULT_PROMPTS.get(domain, ""))
        if args.limit:
            prompts = prompts[: args.limit]
        if not prompts:
            print(f"  (no prompts for {model}/{domain}, skipping)")
            continue
        print(f"\n== Teacher {model}  domain={domain}  prompts={len(prompts)} ==")
        ok = 0
        for p in prompts:
            try:
                ans = teacher_answer(url, model, args.key, p)
            except Exception as e:
                print(f"  !! {model}: {e}")
                continue
            records.append({"messages": [{"role": "user", "content": p},
                                         {"role": "assistant", "content": ans}],
                            "meta": {"domain": domain, "teacher": model}})
            ok += 1
            print(f"  + [{ok}/{len(prompts)}] {p[:60]}")
        print(f"  {model}: {ok} pairs")

    records = dedupe(records)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nDone. Total unique pairs -> {args.out}: {len(records)}")


if __name__ == "__main__":
    main()
