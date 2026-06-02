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


def _pytest_green(root: str) -> tuple[bool, str]:
    rc, out = _run([_py(), "-m", "pytest", "-q"], root, timeout=120)
    return rc == 0, f"pytest rc={rc} tail={out.strip()[-160:]}"


def _setup_cross_file_bug(root: str) -> None:
    _write(root, "shop/__init__.py", "")
    _write(root, "shop/pricing.py", "def line_total(price, qty):\n    return price + qty  # BUG\n")
    _write(
        root, "shop/cart.py",
        "from shop.pricing import line_total\n\n\n"
        "def cart_total(items):\n    return sum(line_total(p, q) for p, q in items)\n",
    )
    _write(
        root, "test_shop.py",
        "from shop.cart import cart_total\n\n\n"
        "def test_cart_total():\n    assert cart_total([(10, 2), (5, 3)]) == 35\n",
    )


def _check_lru(root: str) -> tuple[bool, str]:
    verify = (
        "from lru import LRUCache\n"
        "c = LRUCache(2)\n"
        "c.put(1, 1)\nc.put(2, 2)\n"
        "assert c.get(1) == 1\n"
        "c.put(3, 3)\n"
        "assert c.get(2) == -1, 'LRU eviction failed'\n"
        "assert c.get(3) == 3\n"
        "print('LRU_OK')\n"
    )
    _write(root, "_verify_lru.py", verify)
    rc, out = _run([_py(), "_verify_lru.py"], root)
    return (rc == 0 and "LRU_OK" in out), f"rc={rc} out={out.strip()[-160:]}"


def _setup_feature_add(root: str) -> None:
    calc = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
    _write(root, "calc.py", calc)
    _write(
        root, "test_calc.py",
        "from calc import add, sub\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_sub():\n    assert sub(5, 2) == 3\n",
    )


def _check_feature_add(root: str) -> tuple[bool, str]:
    rc, _ = _run([_py(), "-m", "pytest", "-q"], root, timeout=120)
    rc2, out2 = _run(
        [_py(), "-c", "import calc; assert calc.power(2, 10) == 1024; print('POW_OK')"], root
    )
    ok = rc == 0 and rc2 == 0 and "POW_OK" in out2
    return ok, f"pytest rc={rc}; power rc={rc2} {out2.strip()[-80:]}"


def _check_todo_cli(root: str) -> tuple[bool, str]:
    cli = os.path.join(root, "todo", "cli.py")
    for a in (["add", "alpha"], ["add", "beta"], ["done", "1"]):
        rc, out = _run([_py(), cli, *a], root)
        if rc != 0:
            return False, f"`cli {' '.join(a)}` rc={rc} {out.strip()[-100:]}"
    rc, out = _run([_py(), cli, "list"], root)
    ok = rc == 0 and "alpha" in out and "beta" in out
    return ok, f"list rc={rc} out={out.strip()[:160]}"


def _verify(root: str, name: str, code: str, marker: str) -> tuple[bool, str]:
    """Write an independent verification script, run it, and require a success marker."""
    _write(root, f"_verify_{name}.py", code)
    rc, out = _run([_py(), f"_verify_{name}.py"], root)
    return (rc == 0 and marker in out), f"rc={rc} out={out.strip()[-160:]}"


def _check_expr(root: str) -> tuple[bool, str]:
    return _verify(
        root, "expr",
        "from expr import evaluate\n"
        "assert abs(evaluate('2+3*4-(1+1)') - 12) < 1e-9\n"
        "assert abs(evaluate('10/2/5') - 1) < 1e-9\n"
        "assert abs(evaluate('(1+2)*(3+4)') - 21) < 1e-9\n"
        "print('EXPR_OK')\n",
        "EXPR_OK",
    )


def _check_dijkstra(root: str) -> tuple[bool, str]:
    return _verify(
        root, "dijkstra",
        "from graph import shortest_path\n"
        "g = {'A': [('B', 1), ('C', 4)], 'B': [('C', 2), ('D', 5)], "
        "'C': [('D', 1)], 'D': []}\n"
        "assert shortest_path(g, 'A', 'D') == 4\n"
        "print('DIJKSTRA_OK')\n",
        "DIJKSTRA_OK",
    )


def _check_counter(root: str) -> tuple[bool, str]:
    return _verify(
        root, "counter",
        "import threading\n"
        "from counter import Counter\n"
        "c = Counter()\n"
        "def work():\n"
        "    for _ in range(1000):\n        c.increment()\n"
        "ts = [threading.Thread(target=work) for _ in range(10)]\n"
        "[t.start() for t in ts]\n[t.join() for t in ts]\n"
        "assert c.value == 10000, c.value\n"
        "print('COUNTER_OK')\n",
        "COUNTER_OK",
    )


def _check_package_api(root: str) -> tuple[bool, str]:
    return _verify(
        root, "pkg",
        "from mathpkg import add, sub, power, factorial\n"
        "assert add(2, 3) == 5 and sub(5, 2) == 3\n"
        "assert power(2, 10) == 1024 and factorial(5) == 120\n"
        "print('PKG_OK')\n",
        "PKG_OK",
    )


def _setup_refactor(root: str) -> None:
    _write(
        root, "shapes.py",
        "def circle_area(r):\n    return 3.141592653589793 * r * r\n\n\n"
        "def cylinder_volume(r, h):\n    return 3.141592653589793 * r * r * h\n\n\n"
        "def sphere_volume(r):\n    return (4.0 / 3.0) * 3.141592653589793 * r * r * r\n",
    )
    _write(
        root, "test_shapes.py",
        "from shapes import circle_area, cylinder_volume, sphere_volume\n\n\n"
        "def test_circle():\n    assert abs(circle_area(2) - 12.566370614359172) < 1e-9\n\n\n"
        "def test_cylinder():\n"
        "    assert abs(cylinder_volume(2, 3) - 37.69911184307752) < 1e-9\n\n\n"
        "def test_sphere():\n    assert abs(sphere_volume(3) - 113.09733552923255) < 1e-9\n",
    )


def _setup_mutable_bug(root: str) -> None:
    acc = "def append_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n"
    _write(root, "acc.py", acc)
    _write(
        root, "test_bug.py",
        "from acc import append_item\n\n\n"
        "def test_isolated():\n"
        "    assert append_item(1) == [1]\n    assert append_item(2) == [2]\n",
    )


def _check_sqlite_crud(root: str) -> tuple[bool, str]:
    return _verify(
        root, "db",
        "import os\n"
        "from db import init_db, add_user, get_user, update_age\n"
        "p = 'users.db'\n"
        "if os.path.exists(p):\n    os.remove(p)\n"
        "init_db(p)\nadd_user(p, 'alice', 30)\nadd_user(p, 'bob', 25)\n"
        "assert get_user(p, 'alice') == ('alice', 30)\n"
        "update_age(p, 'alice', 31)\n"
        "assert get_user(p, 'alice') == ('alice', 31)\n"
        "assert get_user(p, 'nobody') is None\n"
        "print('DB_OK')\n",
        "DB_OK",
    )


def _check_regex(root: str) -> tuple[bool, str]:
    return _verify(
        root, "extract",
        "from extract import extract_emails\n"
        "t = 'reach a@b.com, x@y.org and a@b.com; bad@, ok.name+tag@sub.domain.co end'\n"
        "r = extract_emails(t)\n"
        "assert 'a@b.com' in r and 'x@y.org' in r and 'ok.name+tag@sub.domain.co' in r\n"
        "assert r == sorted(set(r))\n"
        "print('RE_OK')\n",
        "RE_OK",
    )


def _check_memoize(root: str) -> tuple[bool, str]:
    return _verify(
        root, "memo",
        "from memo import memoize\n"
        "calls = {'n': 0}\n"
        "@memoize\n"
        "def slow(x):\n    calls['n'] += 1\n    return x * x\n"
        "assert slow(3) == 9 and slow(3) == 9 and slow(4) == 16\n"
        "assert calls['n'] == 2, calls['n']\n"
        "print('MEMO_OK')\n",
        "MEMO_OK",
    )


def _check_toposort(root: str) -> tuple[bool, str]:
    return _verify(
        root, "toposort",
        "from toposort import topo_sort\n"
        "order = topo_sort({'a': [], 'b': ['a'], 'c': ['a', 'b'], 'd': ['c']})\n"
        "pos = {n: i for i, n in enumerate(order)}\n"
        "assert pos['a'] < pos['b'] < pos['c'] < pos['d']\n"
        "try:\n    topo_sort({'x': ['y'], 'y': ['x']})\n"
        "    raise AssertionError('no cycle error')\n"
        "except ValueError:\n    pass\n"
        "print('TOPO_OK')\n",
        "TOPO_OK",
    )


def _check_bank(root: str) -> tuple[bool, str]:
    return _verify(
        root, "bank",
        "from account import BankAccount\n"
        "a = BankAccount()\n"
        "a.deposit(50)\na.withdraw(120)\n"
        "assert a.balance == -70\n"
        "try:\n    a.withdraw(50)\n    raise AssertionError('overdraft not enforced')\n"
        "except ValueError:\n    pass\n"
        "print('BANK_OK')\n",
        "BANK_OK",
    )


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
    Scenario(
        name="cross_file_bug",
        goal=(
            "The tests in test_shop.py fail. There is a bug inside the shop package "
            "(shop/pricing.py and shop/cart.py work together). Find and fix the bug so the "
            "tests pass. Run pytest to confirm."
        ),
        check=_pytest_green,
        setup=_setup_cross_file_bug,
        tags=["debug", "multi-file"],
    ),
    Scenario(
        name="lru_cache",
        goal=(
            "Implement lru.py with a class LRUCache(capacity) supporting get(key) (returns the "
            "value, or -1 if absent) and put(key, value), evicting the least-recently-used entry "
            "when it exceeds capacity. Also write test_lru.py with pytest tests, and run pytest "
            "to confirm they pass."
        ),
        check=_check_lru,
        tags=["data-structure", "design"],
    ),
    Scenario(
        name="feature_add_regression",
        goal=(
            "calc.py has add and sub with passing tests in test_calc.py. Add a power(base, exp) "
            "function to calc.py and a matching test in test_calc.py, WITHOUT breaking the "
            "existing tests. Run pytest and make sure everything passes."
        ),
        check=_check_feature_add,
        setup=_setup_feature_add,
        tags=["feature", "regression"],
    ),
    Scenario(
        name="todo_cli",
        goal=(
            "Build a todo package in this directory: todo/store.py with functions to add, list, "
            "and complete tasks persisted to a JSON file, and todo/cli.py so that "
            "`python todo/cli.py add \"buy milk\"` adds a task, `python todo/cli.py list` prints "
            "the tasks, and `python todo/cli.py done 1` marks task 1 complete. Verify by running "
            "those commands; tasks must persist across separate invocations."
        ),
        check=_check_todo_cli,
        tags=["multi-file", "cli", "state"],
    ),
    Scenario(
        name="expr_parser",
        goal=(
            "Write expr.py with a function evaluate(expr: str) -> float that evaluates arithmetic "
            "expressions supporting + - * / and parentheses with correct operator precedence, "
            "implemented as a recursive-descent parser (do NOT use Python's eval). Verify it "
            "handles nested parentheses and precedence by running it."
        ),
        check=_check_expr,
        tags=["parsing", "hard"],
    ),
    Scenario(
        name="dijkstra",
        goal=(
            "Write graph.py with shortest_path(graph, start, end) that returns the minimum total "
            "weight from start to end using Dijkstra's algorithm. graph is a dict mapping a node "
            "to a list of (neighbor, weight) tuples. Verify on a sample graph by running it."
        ),
        check=_check_dijkstra,
        tags=["algorithm", "hard"],
    ),
    Scenario(
        name="threadsafe_counter",
        goal=(
            "Write counter.py with a thread-safe Counter class exposing increment() and a `value` "
            "property, correct under concurrent access from many threads (use a lock). Verify by "
            "running 10 threads doing 1000 increments each and confirming value == 10000."
        ),
        check=_check_counter,
        tags=["concurrency", "hard"],
    ),
    Scenario(
        name="refactor_keep_green",
        goal=(
            "shapes.py works and test_shapes.py passes, but the circle-area math (pi*r*r) is "
            "duplicated across the functions. Refactor shapes.py to define that once and reuse "
            "it WITHOUT changing any behavior; all tests in test_shapes.py must still pass."
        ),
        check=_pytest_green,
        setup=_setup_refactor,
        tags=["refactor", "regression"],
    ),
    Scenario(
        name="mutable_default_bug",
        goal=(
            "test_bug.py fails. The bug in acc.py is a classic Python pitfall (a mutable default "
            "argument shared across calls). Fix acc.py so each call starts fresh and the tests "
            "pass. Run pytest to confirm."
        ),
        check=_pytest_green,
        setup=_setup_mutable_bug,
        tags=["debug", "subtle"],
    ),
    Scenario(
        name="package_api",
        goal=(
            "Create a package mathpkg/ with mathpkg/basic.py (add, sub), mathpkg/advanced.py "
            "(power(base, exp), factorial(n)), and mathpkg/__init__.py that re-exports all four so "
            "`from mathpkg import add, sub, power, factorial` works. Add test_pkg.py that imports "
            "from mathpkg and tests each, and run pytest to confirm."
        ),
        check=_check_package_api,
        tags=["multi-file", "packaging", "hard"],
    ),
    Scenario(
        name="sqlite_crud",
        goal=(
            "Write db.py using the stdlib sqlite3 module with: init_db(path) creating a 'users' "
            "table (id INTEGER PRIMARY KEY, name TEXT, age INTEGER); add_user(path, name, age); "
            "get_user(path, name) returning a (name, age) tuple or None; and update_age(path, "
            "name, age). Verify by running it end to end."
        ),
        check=_check_sqlite_crud,
        tags=["stdlib", "db", "hard"],
    ),
    Scenario(
        name="regex_extract",
        goal=(
            "Write extract.py with extract_emails(text) that returns a sorted list of the unique "
            "email addresses found in text, using the re module. Verify it on a sample with "
            "duplicates and tricky addresses."
        ),
        check=_check_regex,
        tags=["regex", "stdlib"],
    ),
    Scenario(
        name="memoize_decorator",
        goal=(
            "Write memo.py with a decorator @memoize that caches a function's return values by its "
            "positional arguments so repeated calls with the same args don't recompute. Verify "
            "that the wrapped function body only runs once per distinct argument."
        ),
        check=_check_memoize,
        tags=["decorator", "hard"],
    ),
    Scenario(
        name="topological_sort",
        goal=(
            "Write toposort.py with topo_sort(deps) where deps maps each node to the list of nodes "
            "it depends on; return a valid topological order (dependencies before dependents) and "
            "raise ValueError if there is a cycle. Verify on a DAG and on a cyclic graph."
        ),
        check=_check_toposort,
        tags=["algorithm", "hard"],
    ),
    Scenario(
        name="bank_account_rules",
        goal=(
            "Write account.py with a BankAccount class: deposit(amount), withdraw(amount), and a "
            "balance property. Withdrawals may take the balance down to -100 (a $100 overdraft) "
            "but any withdrawal that would go below -100 must raise ValueError. Add "
            "test_account.py with pytest tests for deposit, an allowed overdraft, and a rejected "
            "over-limit withdrawal, and run pytest."
        ),
        check=_check_bank,
        tags=["state", "rules", "hard"],
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
    store.save(sid, source="eval")  # tag so the corpus separates benchmark runs from real builds
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
