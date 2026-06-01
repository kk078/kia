"""The agentic build loop (ReAct): KIA thinks, takes ONE tool action, observes the
result, and repeats until the goal is met — driven by the strong cloud planner model.

The loop is resumable: when it proposes a high-risk shell command it pauses, persists
the session, and emits an ``approval`` event; the API resumes it once the user decides.
Low/medium-risk steps (reads, writes, safe commands) run automatically.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from brain_build import store
from brain_build.tools import BuildTools, classify_command
from brain_core.config import settings
from brain_core.llm import LLMRouter

MAX_STEPS = 30
_OBS_CAP = 6000  # max chars of an observation fed back into the model / UI

_SYSTEM = """You are KIA's autonomous build agent working inside the directory:
  {root}

You accomplish the user's GOAL by taking ONE action at a time and observing its result.

Respond with EXACTLY ONE JSON object and NOTHING else — no prose, no code fences:
  {{"thought": "<brief reasoning>", "tool": "<name>", "args": {{...}}}}

Available tools:
  - list_dir   {{"path": "."}}                         list a directory
  - read_file  {{"path": "rel/or/abs/path"}}           read a file's text
  - write_file {{"path": "...", "content": "..."}}     create/overwrite a file (exact content)
  - edit_file  {{"path": "...", "old": "...", "new": "..."}}  replace a unique exact substring
  - run_command{{"command": "..."}}   run a shell command (CWD = the working directory)
  - fetch_url  {{"url": "https://..."}}                fetch a web page for reference
  - finish     {{"summary": "what you did + how you verified it"}}  end the build

Rules:
- Paths are relative to the working directory; you cannot touch anything outside it.
- Make small, verifiable steps. After writing code, RUN it (or the tests/build) and read
  the output before deciding the next step. Fix failures and re-run until it works.
- When the goal is achieved AND you've verified it from real command output, call finish.
- Destructive or system-level commands (delete, install, registry/service, force-push)
  will be paused for human approval — prefer safe, idempotent commands.
- Keep file writes complete and runnable. Don't invent file contents you haven't read."""


def _resolve_model() -> tuple[str, dict[str, Any]]:
    """Resolve (model, kwargs) — prefer the strong cloud planner; else local default."""
    configured = settings.connector_planner_model
    base_url = settings.connector_planner_base_url
    if configured and base_url:
        name = configured.split("/", 1)[-1]
        return f"openai/{name}", {
            "api_base": base_url,
            "api_key": settings.connector_planner_api_key or "sk-dummy",
        }
    if configured:
        return configured, {}
    return f"{settings.default_oss_provider}/{settings.default_oss_model}", {}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first balanced JSON object out of the model's reply, robustly."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s[3:] else s.strip("`")
        s = s.removeprefix("json").strip()
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _cap(text: str) -> str:
    return text if len(text) <= _OBS_CAP else text[:_OBS_CAP] + "\n…[truncated]"


def _action_preview(tool: str, args: dict[str, Any]) -> str:
    """A one-line human-readable preview of an action for the UI."""
    if tool == "run_command":
        return str(args.get("command", ""))
    if tool in ("read_file", "list_dir"):
        return str(args.get("path", "."))
    if tool == "write_file":
        return f"{args.get('path', '')} ({len(str(args.get('content', '')))} bytes)"
    if tool == "edit_file":
        return str(args.get("path", ""))
    if tool == "fetch_url":
        return str(args.get("url", ""))
    return json.dumps(args)[:200]


class BuildAgent:
    """Runs (and resumes) the ReAct build loop for a session."""

    def __init__(self) -> None:
        """Resolve the driver model once."""
        self.model, self.kwargs = _resolve_model()

    async def _execute(
        self, tools: BuildTools, tool: str, args: dict[str, Any]
    ) -> tuple[str, bool]:
        """Run a tool call; return (observation_text, ok)."""
        try:
            if tool == "read_file":
                return tools.read_file(str(args["path"])), True
            if tool == "list_dir":
                return tools.list_dir(str(args.get("path", "."))), True
            if tool == "write_file":
                return tools.write_file(str(args["path"]), str(args.get("content", ""))), True
            if tool == "edit_file":
                return tools.edit_file(str(args["path"]), str(args["old"]), str(args["new"])), True
            if tool == "fetch_url":
                return await tools.fetch_url(str(args["url"])), True
            if tool == "run_command":
                res = await tools.run_command(str(args["command"]))
                out = f"exit={res.get('exit_code')}\n"
                if res.get("stdout"):
                    out += f"stdout:\n{res['stdout']}\n"
                if res.get("stderr"):
                    out += f"stderr:\n{res['stderr']}"
                return out.strip(), bool(res.get("ok"))
            return f"ERROR: unknown tool '{tool}'", False
        except KeyError as e:
            return f"ERROR: missing arg {e} for tool '{tool}'", False
        except Exception as e:  # noqa: BLE001 - surface tool errors to the loop as observations
            return f"ERROR: {type(e).__name__}: {e}", False

    def _record(self, sid: str, role: str, content: str) -> None:
        s = store.get(sid)
        if s is not None:
            s["messages"].append({"role": role, "content": content})

    async def run(self, sid: str) -> AsyncGenerator[dict[str, Any], None]:
        """Drive the loop from the session's current state until pause/finish/limit/error."""
        s = store.get(sid)
        if s is None:
            yield {"type": "error", "content": "session not found"}
            return
        tools = BuildTools(s["root"])

        while True:
            if s["step"] >= MAX_STEPS:
                yield {"type": "limit", "content": f"reached the {MAX_STEPS}-step limit"}
                store.save(sid, status="done")
                return
            s["step"] += 1
            step_no = s["step"]

            try:
                resp = await LLMRouter().complete(self.model, s["messages"], **self.kwargs)
                reply = str(resp.choices[0].message.content or "")
            except Exception as e:  # noqa: BLE001
                yield {"type": "error", "content": f"model error: {type(e).__name__}: {e}"}
                store.save(sid, status="done")
                return

            action = _extract_json_object(reply)
            if action is None or "tool" not in action:
                # Nudge the model back to protocol instead of failing the build.
                self._record(sid, "assistant", reply)
                self._record(
                    sid, "user",
                    "OBSERVATION: your reply was not a single JSON object with a 'tool'. "
                    "Respond with exactly one JSON action object.",
                )
                continue

            tool = str(action.get("tool", ""))
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            thought = str(action.get("thought", "")).strip()
            self._record(sid, "assistant", reply)
            if thought:
                yield {"type": "thought", "step": step_no, "content": thought}

            if tool == "finish":
                summary = str(args.get("summary", "Build complete.")).strip()
                yield {"type": "finish", "step": step_no, "summary": summary}
                store.save(sid, status="done")
                return

            danger = (
                classify_command(str(args.get("command", ""))) if tool == "run_command" else "low"
            )
            preview = _action_preview(tool, args)
            yield {
                "type": "action", "step": step_no, "tool": tool,
                "preview": preview, "danger": danger,
            }

            # Guardrail: high-risk shell commands pause for approval.
            if tool == "run_command" and danger == "high":
                store.save(sid, status="paused", pending={"tool": tool, "args": args})
                yield {
                    "type": "approval",
                    "step": step_no,
                    "session_id": sid,
                    "tool": tool,
                    "command": str(args.get("command", "")),
                    "danger": danger,
                }
                return

            obs, ok = await self._execute(tools, tool, args)
            obs = _cap(obs)
            self._record(sid, "user", f"OBSERVATION:\n{obs}")
            yield {"type": "observation", "step": step_no, "ok": ok, "content": obs}

    async def resume(self, sid: str, approve: bool) -> AsyncGenerator[dict[str, Any], None]:
        """Apply the approval decision to the pending action, then continue the loop."""
        s = store.get(sid)
        if s is None:
            yield {"type": "error", "content": "session not found"}
            return
        pending = s.get("pending")
        if not pending:
            yield {"type": "error", "content": "no pending action to resume"}
            return
        store.save(sid, pending=None, status="running")
        tools = BuildTools(s["root"])
        if approve:
            obs, ok = await self._execute(tools, str(pending["tool"]), dict(pending["args"]))
            obs = _cap(obs)
            self._record(sid, "user", f"OBSERVATION:\n{obs}")
            yield {
                "type": "observation", "step": s["step"], "ok": ok,
                "content": obs, "approved": True,
            }
        else:
            self._record(
                sid, "user",
                "OBSERVATION: the user REJECTED that command. Do not run it. "
                "Choose a safer approach or finish.",
            )
            yield {"type": "observation", "step": s["step"], "ok": False,
                   "content": "(rejected by user)", "approved": False}
        async for ev in self.run(sid):
            yield ev


def initial_messages(goal: str, root: str) -> list[dict[str, str]]:
    """Seed the conversation for a new build session."""
    return [
        {"role": "system", "content": _SYSTEM.format(root=root)},
        {"role": "user", "content": f"GOAL: {goal}"},
    ]
