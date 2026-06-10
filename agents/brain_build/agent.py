"""The agentic build loop (ReAct): KIA thinks, takes ONE tool action, observes the
result, and repeats until the goal is met — driven by the strong cloud planner model.

The loop is resumable: when it proposes a high-risk shell command it pauses, persists
the session, and emits an ``approval`` event; the API resumes it once the user decides.
Low/medium-risk steps (reads, writes, safe commands) run automatically.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from brain_build import store
from brain_build.tools import BuildTools, classify_command
from brain_core.config import settings
from brain_core.llm import LLMRouter

MAX_STEPS = 50  # per run; /build/continue extends the budget for very large tasks
_OBS_CAP = 6000  # max chars of an observation fed back into the model / UI

_SYSTEM = """You are KIA's autonomous build agent working inside the directory:
  {root}

You accomplish the user's GOAL by reasoning step by step and taking ONE tool action at a
time, observing its result, then deciding the next action — like a careful senior engineer.

Respond with EXACTLY ONE JSON object and NOTHING else — no prose, no code fences:
  {{"thought": "<reasoning + which TODO item you're on>", "tool": "<name>", "args": {{...}}}}

Tools:
  - list_dir   {{"path": "."}}                                list a directory
  - read_file  {{"path": "..."}}                              read a file's text
  - search     {{"query": "regex", "glob": "*.py"}}           grep text across files
  - write_file {{"path": "...", "content": "..."}}            create/overwrite (exact content)
  - edit_file  {{"path": "...", "old": "...", "new": "..."}}  replace a unique exact substring
  - run_command{{"command": "..."}}                           shell, CWD = the working directory
  - fetch_url  {{"url": "https://..."}}                       fetch a web page for reference
  - finish     {{"summary": "what you built + the evidence it works"}}  end the build

How to work well on COMPLEX tasks:
1. PLAN FIRST. In your first thought, write a numbered TODO covering the whole task. Then
   begin with an exploration action (list_dir / read_file / search). Restate the TODO in each
   thought and mark items [done] as you complete them.
2. EXPLORE before you edit. Understand what already exists; never invent the contents of a
   file you have not read.
3. SMALL STEPS. Change one thing, then verify it. Prefer edit_file over rewriting whole files.
4. VERIFY WITH REALITY. After writing code, actually RUN it (or its tests/build) with
   run_command and read the output. Exit code AND output are the source of truth.
5. RECOVER. If a command fails, read the error, state a hypothesis in your thought, fix it,
   and re-run. Never repeat the same failing action unchanged.
6. REFLECT BEFORE FINISH. finish is REJECTED unless a command has passed (exit 0) since your
   last file change — a confident summary is NOT evidence. Actually run the program or its
   tests, see it pass, THEN finish and cite the command + its key output in the summary.
7. REPORT LIKE A PROFESSIONAL. The finish summary leads with the outcome (what now works),
   then the evidence (the exact command run and its key output). State plainly anything you
   did NOT do or could not verify — an honest gap beats a polished overclaim. Never describe
   a partial result as complete.

Safety: destructive/system commands (delete, install, registry/service, force-push) pause for
human approval — prefer safe, idempotent commands. Paths are confined to the working directory."""


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


def _resolve_escalate() -> tuple[str, dict[str, Any]]:
    """Resolve the stronger escalation model (e.g. Claude), or ('', {}) if disabled.

    Provider-prefixed routes like ``anthropic/claude-...`` authenticate via the provider's
    env key (ANTHROPIC_API_KEY) through litellm, so no extra kwargs are needed.
    """
    return settings.build_escalate_model.strip(), {}


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
    if tool == "search":
        return str(args.get("query", "")) + (f"  in {args['glob']}" if args.get("glob") else "")
    if tool == "write_file":
        return f"{args.get('path', '')} ({len(str(args.get('content', '')))} bytes)"
    if tool == "edit_file":
        return str(args.get("path", ""))
    if tool == "fetch_url":
        return str(args.get("url", ""))
    return json.dumps(args)[:200]


def _trace_path() -> str:
    """Where to append successful-build transcripts (next to the training capture file)."""
    base = settings.training_capture_path or ""
    d = os.path.dirname(base) if base else ""
    return os.path.join(d, "kia_build_traces.jsonl") if d else "kia_build_traces.jsonl"


def _capture_trace(session: dict[str, Any], summary: str) -> None:
    """Append a successful build's full transcript to the trace dataset (best-effort).

    This is KIA's own-wins dataset for later fine-tuning the local model on agentic builds.
    """
    try:
        rec = {
            "ts": time.time(),
            "goal": session.get("goal", ""),
            "root": session.get("root", ""),
            "steps": session.get("step", 0),
            "summary": summary,
            "escalated": bool(session.get("escalated")),
            "model": session.get("model") or session.get("base_model", ""),
            "source": session.get("source", "agent"),
            "messages": session.get("messages", []),
        }
        with open(_trace_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - capture is best-effort
        pass


class BuildAgent:
    """Runs (and resumes) the ReAct build loop for a session."""

    def __init__(self) -> None:
        """Resolve the default driver model and the stronger escalation model."""
        self.model, self.kwargs = _resolve_model()
        self.escalate_model, self.escalate_kwargs = _resolve_escalate()

    def _escalate(self, sid: str, s: dict[str, Any], step_no: int) -> dict[str, Any] | None:
        """Switch the session to the stronger model once the default has stalled.

        Returns an ``escalate`` event to emit, or None if not applicable.
        """
        if s.get("escalated") or not self.escalate_model:
            return None
        blocks = int(s.get("finish_blocks") or 0)
        fails = int(s.get("consec_fail") or 0)
        if blocks < settings.build_escalate_after and fails < 5:
            return None
        s["model"] = self.escalate_model
        s["kwargs"] = self.escalate_kwargs
        s["escalated"] = True
        self._record(
            sid,
            "user",
            "NOTE: escalating to a stronger model. Do NOT trust earlier claims of completion — "
            "use list_dir and read_file to verify what is ACTUALLY on disk, create any missing "
            "files, run the program/tests to confirm, and only then finish.",
        )
        return {"type": "escalate", "step": step_no, "model": self.escalate_model}

    async def _execute(
        self, tools: BuildTools, tool: str, args: dict[str, Any]
    ) -> tuple[str, bool]:
        """Run a tool call; return (observation_text, ok)."""
        try:
            if tool == "read_file":
                return tools.read_file(str(args["path"])), True
            if tool == "list_dir":
                return tools.list_dir(str(args.get("path", "."))), True
            if tool == "search":
                return tools.search(str(args["query"]), str(args.get("glob", ""))), True
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
        s.setdefault("base_model", self.model)  # record the default driver for trace metadata
        budget = int(s.get("max_steps") or MAX_STEPS)

        while True:
            if s["step"] >= budget:
                store.save(sid, status="limit")
                yield {
                    "type": "limit",
                    "session_id": sid,
                    "content": f"hit the {budget}-step budget — /agent continue to keep going",
                }
                return
            s["step"] += 1
            step_no = s["step"]

            model = str(s.get("model") or self.model)
            sk = s.get("kwargs")
            call_kwargs = sk if isinstance(sk, dict) else self.kwargs
            try:
                resp = await LLMRouter().complete(model, s["messages"], **call_kwargs)
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
                    sid,
                    "user",
                    "OBSERVATION: your reply was not a single JSON object with a 'tool'. "
                    "Respond with exactly one JSON action object.",
                )
                continue

            tool = str(action.get("tool", ""))
            raw_args = action.get("args")
            args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            thought = str(action.get("thought", "")).strip()
            self._record(sid, "assistant", reply)
            if thought:
                yield {"type": "thought", "step": step_no, "content": thought}

            if tool == "finish":
                # Verification gate: refuse to finish unless a command has PASSED since the
                # last file change. A confident summary is not evidence — a green run is.
                blocks = int(s.get("finish_blocks") or 0)
                if s.get("last_cmd_ok") is not True and blocks < 3:
                    s["finish_blocks"] = blocks + 1
                    esc = self._escalate(sid, s, step_no)
                    if esc is not None:
                        yield esc
                    self._record(
                        sid,
                        "user",
                        "OBSERVATION: finish REJECTED. You have not verified success since your "
                        "last change. Do NOT claim completion — actually run a command that "
                        "exercises the deliverable (run the program or its tests) and shows it "
                        "works (exit code 0). Then call finish.",
                    )
                    yield {
                        "type": "observation",
                        "step": step_no,
                        "ok": False,
                        "content": "finish blocked — run a passing verification command first",
                    }
                    continue
                summary = str(args.get("summary", "Build complete.")).strip()
                _capture_trace(s, summary)
                yield {"type": "finish", "step": step_no, "summary": summary}
                store.save(sid, status="done")
                return

            danger = (
                classify_command(str(args.get("command", ""))) if tool == "run_command" else "low"
            )
            preview = _action_preview(tool, args)
            yield {
                "type": "action",
                "step": step_no,
                "tool": tool,
                "preview": preview,
                "danger": danger,
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
            # Track verification state: a passing command satisfies the finish gate; any file
            # mutation invalidates it (you must re-verify after changing code).
            if tool == "run_command":
                s["last_cmd_ok"] = ok
                s["consec_fail"] = 0 if ok else int(s.get("consec_fail") or 0) + 1
            elif tool in ("write_file", "edit_file"):
                s["last_cmd_ok"] = None
            self._record(sid, "user", f"OBSERVATION:\n{obs}")
            yield {"type": "observation", "step": step_no, "ok": ok, "content": obs}
            # Escalate to the stronger tier if the default keeps failing commands.
            esc = self._escalate(sid, s, step_no)
            if esc is not None:
                yield esc

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
            s["last_cmd_ok"] = ok  # the approved action is always a run_command
            self._record(sid, "user", f"OBSERVATION:\n{obs}")
            yield {
                "type": "observation",
                "step": s["step"],
                "ok": ok,
                "content": obs,
                "approved": True,
            }
        else:
            self._record(
                sid,
                "user",
                "OBSERVATION: the user REJECTED that command. Do not run it. "
                "Choose a safer approach or finish.",
            )
            yield {
                "type": "observation",
                "step": s["step"],
                "ok": False,
                "content": "(rejected by user)",
                "approved": False,
            }
        async for ev in self.run(sid):
            yield ev

    async def continue_(self, sid: str) -> AsyncGenerator[dict[str, Any], None]:
        """Extend the step budget and keep building (after hitting the limit)."""
        s = store.get(sid)
        if s is None:
            yield {"type": "error", "content": "build session not found (it may have expired)"}
            return
        s["max_steps"] = int(s.get("step", 0)) + MAX_STEPS
        store.save(sid, status="running")
        self._record(sid, "user", "Continue the build from where you left off. Re-check your TODO.")
        async for ev in self.run(sid):
            yield ev


def initial_messages(goal: str, root: str) -> list[dict[str, str]]:
    """Seed the conversation for a new build session."""
    return [
        {"role": "system", "content": _SYSTEM.format(root=root)},
        {"role": "user", "content": f"GOAL: {goal}"},
    ]
