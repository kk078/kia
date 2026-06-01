"""Graded eval suite for KIA's build agent.

Runs the REAL BuildAgent (same loop, model, tools as /agent) against a set of
complex scenarios, each in its own temp directory, and scores pass/fail with a
concrete checker (run the result, inspect files). Auto-approves gated steps so
it can run unattended. Writes a JSON + text report under data/.

Run on the HOST (needs the venv, host runner, and cloud creds), e.g. via
kia_eval.ps1, or:  python -m brain_build.eval
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from brain_build import store
from brain_build.agent import BuildAgent, initial_messages
from brain_core.config import settings

PER_SCENARIO_TIMEOUT = 480.0  # seconds


@dataclass
class Scenario:
    """One eval task: a goal, optional pre-seed setup, and a pass/fail checker."""

    name: str
    goal: str
    check: Callable[[str], tuple[bool, str]]
    setup: Callable[[str], None] | None = None
    tags: list[str] = field(default_factory=list)


# -- helpers ---------------------------------------------------------------
def _py() -> str:
    """Python executable to use for checker subprocesses."""
    return sys.executable or "python"


def _run(cmd: list[str], cwd: str, timeout: int = 60) -> tuple[int, str]:
    """Run a checker command, returning (returncode, combined output)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except Exception as e:  # noqa: BLE001 - checker failures are just a failed scenario
        return -1, f"{type(e).__name__}: {e}"


def _write(root: str, rel: str, content: str) -> None:
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# -- scenarios -------------------------------------------------------------
def _check_cli(root: str) -> tuple[bool, str]:
    rc, out = _run([_py(), os.path.join(root, "app", "cli.py"), "add", "2", "3"], root)
    ok = rc == 0 and "5" in out
    return ok, f"rc={rc} out={out.strip()[:120]}"


def _check_fix_tests(root: str) -> tuple[bool, str]:
    rc, out = _run([_py(), "-m", "pytest", "-q"], root, timeout=120)
    return rc == 0, f"pytest rc={rc} tail={out.strip()[-160:]}"


def _setup_fix_tests(root: str) -> None:
    _write(root, "mathx.py", "def add(a, b):\n    return a - b  # BUG: should add\n")
    _write(
        root, "test_mathx.py",
        "from mathx import add\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n    assert add(10, 5) == 15\n",
    )


def _check_wordcount(root: str) -> tuple[bool, str]:
    rc, out = _run([_py(), os.path.join(root, "wordcount.py")], root)
    return (rc == 0 and "the" in out.lower()), f"rc={rc} out={out.strip()[:120]}"


def _setup_wordcount(root: str) -> None:
    _write(root, "sample.txt", "the cat sat on the mat the cat ran the end\n")


def _check_json_merge(root: str) -> tuple[bool, str]:
    path = os.path.join(root, "merged.json")
    if not os.path.isfile(path):
        return False, "merged.json not created"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        return False, f"merged.json invalid: {e}"
    return data == {"x": 1, "y": 9, "z": 3}, f"merged={data}"


def _setup_json_merge(root: str) -> None:
    _write(root, "a.json", '{"x": 1, "y": 2}')
    _write(root, "b.json", '{"y": 9, "z": 3}')


def _check_fib(root: str) -> tuple[bool, str]:
    rc, out = _run([_py(), "-m", "pytest", "-q"], root, timeout=120)
    has_fib = os.path.isfile(os.path.join(root, "fib.py"))
    return (rc == 0 and has_fib), f"pytest rc={rc} fib.py={has_fib} tail={out.strip()[-140:]}"


SCENARIOS: list[Scenario] = [
    Scenario(
        name="multifile_cli",
        goal=(
            "Create a small CLI in this directory: a module app/calc.py providing "
            "add(a,b), sub(a,b), mul(a,b), div(a,b), and app/cli.py that parses "
            "`python app/cli.py <op> <x> <y>` and prints the integer/number result. "
            "Verify that `python app/cli.py add 2 3` prints 5."
        ),
        check=_check_cli,
        tags=["multi-file", "cli"],
    ),
    Scenario(
        name="fix_failing_tests",
        goal=(
            "There is a module mathx.py and a test file test_mathx.py. The tests fail. "
            "Find the bug in mathx.py and fix it so the tests pass. Run pytest to confirm."
        ),
        check=_check_fix_tests,
        setup=_setup_fix_tests,
        tags=["debug", "tests"],
    ),
    Scenario(
        name="wordcount_stdlib",
        goal=(
            "Using the existing sample.txt in this directory, write wordcount.py that prints "
            "the single most common word in the file (use collections.Counter). Running "
            "`python wordcount.py` should print that word. Run it to confirm."
        ),
        check=_check_wordcount,
        setup=_setup_wordcount,
        tags=["stdlib"],
    ),
    Scenario(
        name="json_merge",
        goal=(
            "There are two files a.json and b.json. Write merge.py that deep-merges them into "
            "merged.json, with values from b.json overriding a.json on key conflicts, then run "
            "it so merged.json is produced."
        ),
        check=_check_json_merge,
        setup=_setup_json_merge,
        tags=["json", "files"],
    ),
    Scenario(
        name="fib_with_tests",
        goal=(
            "Write fib.py with a function fib(n) returning the nth Fibonacci number (fib(0)=0, "
            "fib(1)=1), and test_fib.py with pytest tests covering base cases and fib(10)==55. "
            "Run pytest and make sure it passes."
        ),
        check=_check_fib,
        tags=["algorithm", "tests"],
    ),
]


# -- driver ----------------------------------------------------------------
async def _drive(agent: BuildAgent, sid: str) -> AsyncGenerator[dict[str, Any], None]:
    """Yield all events from a build, auto-approving any gated step (eval is unattended)."""
    gen: AsyncGenerator[dict[str, Any], None] | None = agent.run(sid)
    while gen is not None:
        nxt: AsyncGenerator[dict[str, Any], None] | None = None
        async for ev in gen:
            yield ev
            if ev.get("type") == "approval":
                nxt = agent.resume(sid, True)
                break
        gen = nxt


async def run_scenario(sc: Scenario, runs_dir: str) -> dict[str, Any]:
    """Run one scenario end-to-end and return a result record."""
    root = os.path.join(runs_dir, sc.name)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    if sc.setup:
        sc.setup(root)

    sid = store.create(sc.goal, root, initial_messages(sc.goal, root))
    agent = BuildAgent()
    steps = 0
    finished = False
    last_summary = ""
    error = ""
    t0 = time.monotonic()
    try:
        async def _go() -> None:
            nonlocal steps, finished, last_summary, error
            async for ev in _drive(agent, sid):
                t = ev.get("type")
                if t == "action":
                    steps += 1
                elif t == "finish":
                    finished = True
                    last_summary = str(ev.get("summary", ""))
                elif t == "error":
                    error = str(ev.get("content", ""))

        await asyncio.wait_for(_go(), timeout=PER_SCENARIO_TIMEOUT)
    except TimeoutError:
        error = f"timed out after {PER_SCENARIO_TIMEOUT:.0f}s"
    finally:
        store.delete(sid)

    passed, detail = sc.check(root)
    return {
        "name": sc.name,
        "tags": sc.tags,
        "passed": passed,
        "finished": finished,
        "steps": steps,
        "seconds": round(time.monotonic() - t0, 1),
        "detail": detail,
        "error": error,
        "summary": last_summary[:200],
    }


async def main() -> int:
    """Run all scenarios, print a table, write reports; return 0 if all passed."""
    data_dir = os.path.dirname(settings.training_capture_path or "") or "."
    runs_dir = os.path.join(data_dir, "eval_runs")
    os.makedirs(runs_dir, exist_ok=True)

    print(f"KIA build-agent eval — {len(SCENARIOS)} scenarios — model={BuildAgent().model}")
    results: list[dict[str, Any]] = []
    for sc in SCENARIOS:
        print(f"  running {sc.name} …", flush=True)
        res = await run_scenario(sc, runs_dir)
        mark = "PASS" if res["passed"] else "FAIL"
        print(f"    {mark}  steps={res['steps']} {res['seconds']}s  {res['detail']}", flush=True)
        results.append(res)

    passed = sum(1 for r in results if r["passed"])
    report = {"ts": time.time(), "model": BuildAgent().model, "passed": passed,
              "total": len(results), "results": results}
    report_path = os.path.join(data_dir, "eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n=== {passed}/{len(results)} scenarios passed ===")
    print(f"report: {report_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
