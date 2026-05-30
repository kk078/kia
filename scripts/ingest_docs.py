#!/usr/bin/env python3
"""Teach KIA from documents: PDFs, abstracts, text, markdown.

Two outputs (use either or both):
  --to-rag    push document chunks into KIA's knowledge base -> grounded recall via kia-brain
              (RECOMMENDED for facts; immediate, no training, no hallucination)
  --to-train  ask a teacher to turn each document into Q&A training pairs appended to the
              dataset -> baked into weights at the next fine-tune (style/skill, not exact facts)

Setup:  pip install pypdf
Usage (PowerShell):
  python scripts/ingest_docs.py C:\\papers --to-rag
  python scripts/ingest_docs.py C:\\papers --to-train ^
     --teacher-url https://ollama.com/v1 --teacher-model gpt-oss:120b --teacher-key $env:TEACHER_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request

API = "http://localhost:8000"
TEXT_EXT = {".txt", ".md", ".abstract", ".text"}


def read_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("Install the PDF reader first:  pip install pypdf")
    reader = PdfReader(path)
    return "\n".join((pg.extract_text() or "") for pg in reader.pages)


def load_doc(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return read_pdf(path)
    if ext in TEXT_EXT:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""


def chunk(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text)
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return [c for c in out if c.strip()]


def post_rag(api: str, content: str, source: str) -> None:
    body = json.dumps({"content": content, "source": source}).encode()
    req = urllib.request.Request(api.rstrip("/") + "/api/v1/knowledge/ingest",
                                 data=body, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        r.read()


def teacher_answer(url: str, model: str, key: str, prompt: str) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.3}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


TRAIN_QS = [
    "Summarize the key points of this document in a few clear sentences.",
    "What problem does this document address, and what does it conclude?",
    "List the main findings, methods, or claims in this document.",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--api", default=API)
    ap.add_argument("--to-rag", action="store_true")
    ap.add_argument("--to-train", action="store_true")
    ap.add_argument("--out", default="data/kia_dataset.jsonl")
    ap.add_argument("--teacher-url", default="https://ollama.com/v1")
    ap.add_argument("--teacher-model", default="gpt-oss:120b")
    ap.add_argument("--teacher-key", default=os.getenv("TEACHER_KEY", ""))
    args = ap.parse_args()
    if not (args.to_rag or args.to_train):
        args.to_rag = True  # default: ground via RAG

    files = []
    for dp, _, names in os.walk(args.folder):
        for n in names:
            if os.path.splitext(n)[1].lower() in TEXT_EXT or n.lower().endswith(".pdf"):
                files.append(os.path.join(dp, n))
    print(f"Found {len(files)} documents under {args.folder}")

    train_pairs, rag_chunks = 0, 0
    for full in files:
        rel = os.path.relpath(full, args.folder).replace("\\", "/")
        try:
            text = load_doc(full)
        except SystemExit:
            raise
        except Exception as e:
            print(f"  !! {rel}: {e}")
            continue
        if not text.strip():
            print(f"  (empty/unreadable) {rel}")
            continue

        if args.to_rag:
            for c in chunk(text):
                try:
                    post_rag(args.api, c, f"doc:{rel}")
                    rag_chunks += 1
                except Exception as e:
                    print(f"  !! rag {rel}: {e}")
            print(f"  [rag] {rel}")

        if args.to_train:
            excerpt = text[:6000]
            for q in TRAIN_QS:
                try:
                    ans = teacher_answer(args.teacher_url, args.teacher_model,
                                         args.teacher_key, f"{q}\n\nDocument ({rel}):\n{excerpt}")
                except Exception as e:
                    print(f"  !! teach {rel}: {e}")
                    continue
                with open(args.out, "a", encoding="utf-8") as f:
                    rec = {"messages": [{"role": "user", "content": f"{q} (re: {rel})"},
                                        {"role": "assistant", "content": ans}],
                           "meta": {"domain": "documents", "source": rel}}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                train_pairs += 1
            print(f"  [train] {rel}")

    print(f"\nDone. rag_chunks={rag_chunks} train_pairs={train_pairs}")
    if args.to_train:
        print("Tip: run  python scripts/distill_multiteacher.py --dedupe-only  to clean dups.")


if __name__ == "__main__":
    main()
