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

    async def run(self, prompt: str, max_steps: int = 8) -> str:
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
                    "a task needs several steps; for multi-step or ambiguous tasks, use "
                    "the sequentialthinking tool first to plan before acting.\n\n"
                    "Execution standards:\n"
                    "- VERIFY before you claim: after a mutating action (writing a file, "
                    "creating an issue), read it back or check the tool result before "
                    "saying it succeeded.\n"
                    "- If a tool returns an error, adapt (different args, different tool) "
                    "rather than repeating the same call; report honestly if it cannot "
                    "be done.\n"
                    "- Final answer: lead with the outcome (what is now true), then the "
                    "evidence (which tools you used and what they returned). State "
                    "plainly anything you did not do or could not verify. Never invent "
                    "tool output."
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
        # Out of steps -> synthesize from the FULL transcript (truncated), not just
        # the tail — otherwise early tool results (and parts of the task) get lost.
        transcript = json.dumps(messages[1:], default=str)
        if len(transcript) > 24000:
            transcript = transcript[:12000] + "\n...[truncated]...\n" + transcript[-12000:]
        return await self.router.generate(
            f"The user asked: {prompt}\n\n"
            f"Tool calls made and their results:\n{transcript}\n\n"
            "Write the final reply to the user. Lead with the outcome (answer every "
            "part of their request that the results cover), then brief evidence. "
            "State plainly any part that was NOT completed. Speak as KIA in first "
            "person; never refer to 'the assistant'.",
            task_type="synthesis",
        )
