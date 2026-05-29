"""OpenAI-compatible API surface for KIA (Kiran's Intelligence Architecture).

Exposes /v1/models and /v1/chat/completions so any OpenAI-compatible client
(IDE assistants like Continue.dev, Cursor, Zed; the OpenAI SDK) can use KIA as
a model. Behind the 'kia' model name sits the local Secondary Brain stack (a
local Ollama model + the KIA persona); 'kia-brain' additionally runs the
self-consistency verification loop.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import litellm
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from brain_core.config import settings
from brain_core.llm import LLMRouter

router = APIRouter()

KIA_PERSONA = (
    "You are KIA (Kiran's Intelligence Architecture), a personal AI assistant and "
    "coding companion that runs fully locally on Kiran's machine with no external "
    "providers. Be precise, direct, and practical. When asked for code, return "
    "correct, runnable code with minimal prose."
)


class ChatMessage(BaseModel):
    """A single OpenAI chat message (content may be a string or content parts)."""

    role: str
    content: Any = ""


class ChatRequest(BaseModel):
    """Subset of the OpenAI chat-completions request we care about (extras allowed)."""

    model: str = "kia"
    messages: list[ChatMessage] = []
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None

    model_config = {"extra": "allow"}


def _content_to_text(content: Any) -> str:
    """Coerce OpenAI message content (str or list of parts) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                t = p.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(p, str):
                parts.append(p)
        return "\n".join(parts)
    return str(content)


def _prepare_messages(req: ChatRequest) -> list[dict[str, str]]:
    """Normalize messages and ensure a KIA system prompt is present."""
    msgs: list[dict[str, str]] = [
        {"role": m.role, "content": _content_to_text(m.content)} for m in req.messages
    ]
    if not any(m["role"] == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": KIA_PERSONA})
    return msgs


def _resolve_model(requested: str) -> tuple[str, str]:
    """Map a KIA model id to (litellm_model_string, mode).

    mode is 'brain' (full pipeline + verification) or 'direct' (single local call).
    """
    base = f"{settings.default_oss_provider}/{settings.default_oss_model}"
    m = (requested or "kia").lower()
    if m in ("kia-brain", "kia-reasoning", "kia-verified"):
        return base, "brain"
    coder = os.getenv("KIA_CODER_MODEL", "").strip()
    if m in ("kia-coder", "kia-code") and coder:
        return coder, "direct"
    return base, "direct"


def _oss_kwargs(model: str) -> dict[str, Any]:
    """api_base/api_key for local OpenAI-compatible providers (Ollama etc.)."""
    cfg = LLMRouter()._get_oss_config(model)
    if cfg:
        return {"api_base": cfg["api_base"], "api_key": "sk-dummy"}
    return {}


def _sse(cid: str, created: int, model: str, delta: dict[str, Any], finish: str | None) -> str:
    chunk = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return "data: " + json.dumps(chunk) + "\n\n"


async def _stream_direct(
    model: str, messages: list[dict[str, str]], gen_kwargs: dict[str, Any], requested: str
) -> AsyncGenerator[str, None]:
    """Stream a single local completion as OpenAI chat.completion.chunk SSE events."""
    cid = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())
    yield _sse(cid, created, requested, {"role": "assistant"}, None)
    try:
        resp = await litellm.acompletion(model=model, messages=messages, stream=True, **gen_kwargs)
        async for chunk in resp:
            piece: str | None = None
            try:
                piece = chunk.choices[0].delta.content
            except Exception:
                piece = None
            if piece:
                yield _sse(cid, created, requested, {"content": piece}, None)
    except Exception as e:  # surface mid-stream errors as text, never a hard 500
        err = f"[KIA error: {type(e).__name__}: {e}]"
        yield _sse(cid, created, requested, {"content": err}, None)
    yield _sse(cid, created, requested, {}, "stop")
    yield "data: [DONE]\n\n"


async def _stream_text(text: str, requested: str) -> AsyncGenerator[str, None]:
    """Emit a precomputed answer (e.g. verified brain output) as a one-shot SSE stream."""
    cid = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())
    yield _sse(cid, created, requested, {"role": "assistant"}, None)
    yield _sse(cid, created, requested, {"content": text}, None)
    yield _sse(cid, created, requested, {}, "stop")
    yield "data: [DONE]\n\n"


def _completion(
    text: str, requested: str, prompt_tokens: int = 0, completion_tokens: int = 0
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": requested,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@router.get("/v1/models")
async def list_models() -> dict[str, Any]:
    """List the KIA model ids an OpenAI-compatible client can select."""
    now = int(time.time())
    ids = ["kia", "kia-coder", "kia-brain"]
    return {
        "object": "list",
        "data": [{"id": i, "object": "model", "created": now, "owned_by": "kia"} for i in ids],
    }


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest) -> Any:
    """OpenAI-compatible chat completions backed by the local KIA brain."""
    model, mode = _resolve_model(req.model)
    messages = _prepare_messages(req)

    gen_kwargs: dict[str, Any] = _oss_kwargs(model)
    if req.temperature is not None:
        gen_kwargs["temperature"] = req.temperature
    if req.max_tokens is not None:
        gen_kwargs["max_tokens"] = req.max_tokens

    router_ = LLMRouter()

    if mode == "brain":
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        text = await router_.generate_verified(convo, task_type="research", model=model)
        if req.stream:
            return StreamingResponse(
                _stream_text(text, req.model), media_type="text/event-stream"
            )
        return _completion(text, req.model)

    if req.stream:
        return StreamingResponse(
            _stream_direct(model, messages, gen_kwargs, req.model),
            media_type="text/event-stream",
        )
    resp = await router_.complete(model, messages, **gen_kwargs)
    text = resp.choices[0].message.content
    usage = getattr(resp, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    return _completion(text, req.model, pt, ct)
