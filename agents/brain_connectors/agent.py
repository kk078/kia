"""Hybrid tool-calling agent: cloud model plans tool calls, executes via MCP.

Small local models pick tools unreliably, so the tool-planning step can be routed
to a stronger model (e.g. Ollama Cloud) while everyday generation stays local.
Set ``connector_planner_model`` in settings (e.g. "openai/gpt-oss:120b" with
``connector_planner_base_url`` pointing at an OpenAI-compatible cloud endpoint) to use a
strong planner; otherwise it falls back to the local model.
"""

from __future__ import annotations

import json
from typing import Any

import litellm

from brain_connectors.client import MCPConnectorManager
from brain_core.config import settings
from brain_core.llm import LLMRouter


class ConnectorAgent:
    """Runs a tool-calling loop over connected MCP servers."""

    def __init__(self, manager: MCPConnectorManager) -> None:
        """Initialize with a connected MCPConnectorManager."""
        self.manager = manager
        self.router = LLMRouter()

    def _planner_model(self) -> str:
        """Model used for the tool-planning step (strong if configured, else local)."""
        if settings.connector_planner_model:
            return settings.connector_planner_model
        return f"{settings.default_oss_provider}/{settings.default_oss_model}"

    async def run(self, prompt: str, max_steps: int = 5) -> str:
        """Answer ``prompt``, calling connector tools as needed (bounded by max_steps)."""
        tools = self.manager.tools
        if not tools:
            # No connectors available -> plain local generation.
            return await self.router.generate(prompt, task_type="research")

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are KIA, an action-oriented agent with the provided tools. "
                    "Be decisive: if the request is clear enough to act on, CALL the "
                    "appropriate tool(s) and carry the task through to completion — do "
                    "NOT reply with a menu of things you 'could' do, and do not ask for "
                    "permission to use a tool you already have. Only if a required detail "
                    "is genuinely missing (e.g. which channel, which repo), ask exactly "
                    "ONE short, specific question and stop. Chain multiple tool calls when "
                    "a task needs several steps. When the task is done, give a brief final "
                    "answer stating what you did and the result."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        model = self._planner_model()
        kwargs: dict[str, Any] = {}
        if settings.connector_planner_model and settings.connector_planner_base_url:
            # Dedicated planner endpoint (e.g. Ollama Cloud) for reliable tool-calling.
            # Force the openai/ provider prefix: litellm only honors api_base on the
            # OpenAI-compatible path; ollama_chat/ would ignore it and hit localhost.
            bare = model.split("/", 1)[-1]
            model = f"openai/{bare}"
            kwargs["api_base"] = settings.connector_planner_base_url
            kwargs["api_key"] = settings.connector_planner_api_key or "sk-dummy"
        else:
            cfg = self.router._get_oss_config(model)
            if cfg:
                kwargs["api_base"] = cfg["api_base"]
                kwargs["api_key"] = "sk-dummy"

        for _ in range(max_steps):
            resp = await litellm.acompletion(model=model, messages=messages, tools=tools, **kwargs)
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                content: str = msg.content or ""
                return content
            # Record the assistant turn that requested tools.
            messages.append(
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
                result = await self.manager.call_tool(name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        # Out of steps -> ask for a final synthesis from what we gathered.
        return await self.router.generate(
            "Summarize the answer based on the tool results above:\n"
            + json.dumps(messages[-4:], default=str),
            task_type="synthesis",
        )
