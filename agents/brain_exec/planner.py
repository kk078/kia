"""Command planner — turns a natural-language task into reviewable shell commands.

Plans only; it never executes. Uses the (cloud) connector planner model when configured
(small local models pick commands unreliably), else the local default. Output is a strict
JSON array of {command, explanation, danger} so the UI can show each step for approval.
"""

from __future__ import annotations

import json
from typing import Any

from brain_core.config import settings
from brain_core.llm import LLMRouter

_SYS = """You are KIA's command planner for a {os} machine.
Given a task, output the exact shell commands to accomplish it — nothing else.

Rules:
- Output ONLY a JSON array, no prose, no code fences.
- Each element is an object with keys: "command" (one shell command),
  "explanation" (short why), and "danger" ("low", "medium", or "high").
- One command per element; order them as they should run.
- Prefer official, idiomatic install methods for the OS
  (Windows: winget/choco/official installer; macOS: brew; Linux: native package manager).
- Mark anything that deletes data, needs admin, changes system config, or
  downloads+runs a script as "high".
- If the task is unclear or unsafe, return an empty array [].
Return between 1 and 12 commands."""


class CommandPlanner:
    """Plans shell commands for a task using the configured planner model."""

    def _planner_model(self) -> tuple[str, dict[str, Any]]:
        """Resolve (model_string, extra_kwargs) for the planner LLM call."""
        configured = settings.connector_planner_model
        base_url = settings.connector_planner_base_url
        if configured and base_url:
            # litellm only honors api_base on the openai/ path.
            name = configured.split("/", 1)[-1]
            return f"openai/{name}", {
                "api_base": base_url,
                "api_key": settings.connector_planner_api_key or "sk-dummy",
            }
        if configured:
            return configured, {}
        return f"{settings.default_oss_provider}/{settings.default_oss_model}", {}

    @staticmethod
    def _parse(text: str) -> list[dict[str, str]]:
        """Extract a JSON array of commands from the model output, robustly."""
        s = text.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if "```" in s[3:] else s.strip("`")
            s = s.removeprefix("json").strip()
        start, end = s.find("["), s.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        try:
            raw = json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return []
        out: list[dict[str, str]] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            cmd = str(item.get("command", "")).strip()
            if not cmd:
                continue
            danger = str(item.get("danger", "medium")).lower()
            if danger not in ("low", "medium", "high"):
                danger = "medium"
            out.append(
                {
                    "command": cmd,
                    "explanation": str(item.get("explanation", "")).strip(),
                    "danger": danger,
                }
            )
        return out[:12]

    async def plan(self, task: str, os_name: str = "Windows") -> list[dict[str, str]]:
        """Return a reviewable list of commands for ``task`` (empty if unclear/unsafe)."""
        model, kwargs = self._planner_model()
        messages = [
            {"role": "system", "content": _SYS.format(os=os_name)},
            {"role": "user", "content": task},
        ]
        resp = await LLMRouter().complete(model, messages, **kwargs)
        text: str = resp.choices[0].message.content or ""
        return self._parse(text)

    async def summarize(self, task: str, results: list[dict[str, Any]]) -> str:
        """Summarize execution results in plain language."""
        model, kwargs = self._planner_model()
        transcript = "\n".join(
            f"$ {r.get('command', '')}\nexit={r.get('exit_code')} {r.get('stderr', '')[:300]}"
            for r in results
        )
        messages = [
            {
                "role": "system",
                "content": "Summarize whether the task succeeded based on these command "
                "results. Be concise and call out any failures + next step.",
            },
            {"role": "user", "content": f"Task: {task}\n\nResults:\n{transcript}"},
        ]
        resp = await LLMRouter().complete(model, messages, **kwargs)
        return str(resp.choices[0].message.content or "")
