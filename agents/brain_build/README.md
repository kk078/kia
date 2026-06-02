# KIA build agent + eval suite

`brain_build/` is KIA's autonomous build agent (`agent.py`, `tools.py`, `store.py`) and its
graded benchmark (`eval.py`).

## The eval suite

`eval.py` runs the real `BuildAgent` against a list of `Scenario`s, each in a throwaway temp
dir, and scores pass/fail with a concrete checker. Run it via `kia_eval.ps1` (host) or
`python -m brain_build.eval`. It writes `data/eval_report.json` (overall + per-tag) and every
passing build is captured to `data/kia_build_traces.jsonl`.

### Adding a scenario (systematic convention)

A scenario is one `Scenario(...)` entry plus a checker. Keep them **stdlib-only,
deterministic, and independently verified** (don't trust the agent's own claims — run the
result yourself).

1. **Write a checker** above `SCENARIOS`. For "build something and run it", use the `_verify`
   helper — it writes an independent script into the build dir, runs it, and requires a marker:

   ```python
   def _check_thing(root: str) -> tuple[bool, str]:
       return _verify(
           root, "thing",
           "from thing import do\n"
           "assert do(2) == 4\n"
           "print('THING_OK')\n",
           "THING_OK",
       )
   ```

   For "fix/keep tests green" scenarios, reuse `_pytest_green` and seed files with a `setup`.

2. **Add the `Scenario`** to `SCENARIOS`:

   ```python
   Scenario(
       name="thing",
       goal="Write thing.py with do(x) returning x*2. Verify by running it.",
       check=_check_thing,
       setup=_setup_thing,   # optional: pre-seed files (for debug/refactor tasks)
       tags=["category", "hard"],
   ),
   ```

3. **Tag it.** Tags drive the per-tag pass-rate report (so we see *which capability areas*
   are weak, not just an overall number). Use existing tags where possible:

   `multi-file`, `cli`, `state`, `debug`, `tests`, `regression`, `algorithm`, `data-structure`,
   `concurrency`, `async`, `parsing`, `packaging`, `stdlib`, `db`, `json`, `regex`, `decorator`,
   `dataclass`, `sorting`, `context-manager`, `errors`, `recursion`, `feature`, `design`, `hard`.

   Add `hard` to anything you expect gpt-oss to stall on (those exercise the Claude escalation).

### Reading results
- Overall `X/Y scenarios passed`.
- `by tag (passed/total)` — the systematic view. A tag consistently <100% is a real capability
  gap to target (more training traces in that area, or a harness/prompt tweak).
- `data/eval_report.json` holds the machine-readable breakdown; the scheduled runner archives
  each report under `data/eval_history/` and appends a trend row to `data/eval_history.csv`.

## Scheduling
`install_eval_schedule.ps1` registers a weekly Windows Scheduled Task that runs the suite and
archives results, so regressions and corpus growth are tracked over time without manual runs.
