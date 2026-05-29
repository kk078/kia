"""Capture user-facing interactions as fine-tuning data (JSONL of chat pairs).

Each successful chat/generation is appended as one JSON line in the OpenAI
"messages" format, ready for LoRA fine-tuning (Unsloth/TRL). Best-effort and
non-blocking: capture failures never affect the API response. This is the
Phase 3 engine that lets KIA "adapt over time" from real usage.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from brain_core.config import settings


def capture(
    prompt: str,
    response: str,
    *,
    source: str = "chat",
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one (user, assistant) pair to the training dataset (best-effort)."""
    if not settings.training_capture_enabled:
        return
    if not prompt.strip() or not response.strip():
        return
    record: dict[str, Any] = {
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ],
        "meta": {
            "source": source,
            "model": model or "",
            "ts": datetime.now(UTC).isoformat(),
            **(metadata or {}),
        },
    }
    try:
        path = settings.training_capture_path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Never let capture break a request.
        return


def stats() -> dict[str, Any]:
    """Return basic stats about the captured dataset (count of pairs)."""
    path = settings.training_capture_path
    if not os.path.exists(path):
        return {"path": path, "pairs": 0, "exists": False}
    count = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception:
        pass
    return {"path": path, "pairs": count, "exists": True}
