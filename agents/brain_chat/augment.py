"""Live-retrieval phase for plain chat.

Before KIA streams a chat answer, this runs a short tool-calling loop with the
native web tools (web_search / web_fetch). The planner model decides whether the
latest user turn needs live data; if so it calls the tools and we return a text
block of what was retrieved, which the chat endpoint injects into the prompt so
the streamed answer is grounded in real, current information. If nothing is
needed (or no planner/tooling is available), it returns None and chat proceeds
exactly as before.
"""

from __future__ import annotations

import json
from typing import Any

import litellm

from brain_chat import web_tools
from brain_core.config import settings
from brain_core.llm import LLMRouter

_PLANNER_SYS = (
    "You are KIA's retrieval planner. Decide whether answering the user's latest "
    "message needs live or external information (current events, prices, docs, "
    "anything past training data, or a specific URL the user gave). If it does, call "
    "web_search and/or web_fetch to gather what's needed (a few calls at most). If the "
    "question can be answered from general knowledge or the existing conversation, do "
    "NOT call any tool — just reply with a single word: SKIP. Never write a full answer "
    "here; only gather data or say SKIP."
)


def _planner() -> tuple[str, dict[str, Any]]:
    """Pick the tool-calling model and litellm kwargs (cloud planner if configured)."""
    kwargs: dict[str, Any] = {}
    if settings.connector_planner_model:
        model = settings.connector_planner_model
        if settings.connector_planner_base_url:
            bare = model.split("/", 1)[-1]
            model = f"openai/{bare}"
            kwargs["api_base"] = settings.connector_planner_base_url
            kwargs["api_key"] = settings.connector_planner_api_key or "sk-dummy"
        return model, kwargs
    model = f"{settings.default_oss_provider}/{settings.default_oss_model}"
    cfg = LLMRouter()._get_oss_config(model)
    if cfg:
        kwargs["api_base"] = cfg["api_base"]
        kwargs["api_key"] = "sk-dummy"
    return model, kwargs


_WEB_NAMES = {"web_search", "web_fetch"}


async def _maybe_connect_connectors() -> Any:
    """Get the shared connector pool if configured; else None. Never closes it —
    the pool is process-wide and owned by its own task (see brain_connectors.pool)."""
    if not settings.chat_connectors_enabled:
        return None
    try:
        from brain_connectors.pool import get_pool

        return await get_pool()
    except Exception:
        return None


async def gather_live_context(
    messages: list[dict[str, str]], max_steps: int | None = None
) -> str | None:
    """Run the retrieval loop; return retrieved text, or None if nothing was gathered."""
    if not settings.chat_tools_enabled:
        return None
    steps = max_steps or settings.chat_tools_max_steps
    model, kwargs = _planner()

    # Web tools are always available; merge in MCP connector tools when configured.
    # Ambient chat gets READ-ONLY connector tools only — writes (files, repos,
    # memory mutations) require the explicit /connectors or /agent surfaces.
    manager = await _maybe_connect_connectors()
    tools = list(web_tools.TOOLS)
    if manager is not None:
        from brain_connectors.client import readonly_subset

        tools += readonly_subset(manager.tools)

    convo: list[dict[str, Any]] = [{"role": "system", "content": _PLANNER_SYS}]
    for m in messages:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            convo.append({"role": m["role"], "content": m["content"]})

    # Note: the pool manager is shared and long-lived — never close it here.
    transcript: list[str] = []
    for _ in range(steps):
        resp = await litellm.acompletion(
            model=model, messages=convo, tools=tools, tool_choice="auto", **kwargs
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            break
        convo.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            }
        )
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name in _WEB_NAMES:
                result = await web_tools.dispatch(name, args)
            elif manager is not None:
                # Enforce the read-only gate at dispatch too: the model may
                # name a mutating tool it was never offered.
                from brain_connectors.client import is_readonly_tool

                if is_readonly_tool(name):
                    result = await manager.call_tool(name, args)
                else:
                    result = f"[error: '{name}' is not available in chat — use /connectors]"
            else:
                result = f"[error: unknown tool '{name}']"
            transcript.append(f"### {name}({json.dumps(args, ensure_ascii=False)})\n{result}")
            convo.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    if not transcript:
        return None
    return "\n\n".join(transcript)
