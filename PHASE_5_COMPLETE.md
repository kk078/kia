# Phase 5 Completion Summary — Hardening + Runtime Completion

**Date**: 2026-06-09

Phase 5 was never formally planned — it existed as a "Next Steps" sketch at the
end of PHASE_4_COMPLETE.md. This document closes it out item by item, including
the items that were completed by post-phase work (May–June 2026) and the ones
that were intentionally resolved differently than sketched.

## The Phase 5 sketch, item by item

| # | Item (as sketched in Phase 4) | Resolution |
|---|---|---|
| 1 | Observability (OpenTelemetry tracing) | ✅ Done earlier: `brain_core/tracing.py`, Langfuse, Prometheus/Grafana/Loki |
| 2 | Authentication | ✅ `api/security.py` — `KIA_API_KEY` Bearer/X-API-Key, constant-time compare (2026-06-09) |
| 3 | Caching | ✅ Done earlier: `brain_core/cache.py` (Redis-backed response cache) |
| 4 | Rate limiting | ✅ `api/security.py` — per-client sliding window, `RATE_LIMIT_PER_MINUTE` (2026-06-09) |
| 5 | WebSocket support | ✅ Resolved differently: SSE streaming chat (`/api/v1/chat/stream`) covers the real-time need |
| 6 | Advanced/ML-based routing | ✅ Resolved differently: heuristic + LLM-based classification (`TaskRouter.classify_with_llm`). A bespoke trained classifier was judged not worth it — no labeled corpus, no observed misrouting. |
| 7 | API versioning | ✅ Done earlier: everything under `/api/v1/` |
| 8 | Load testing | ✅ `scripts/load_test.py`, results below (2026-06-09) |

## Runtime completion (gaps found during closure)

Auditing the "partial" modules showed `brain_proactive`, `brain_n8n`, and
`worker/` were already fully implemented — the real gap was that proactive and
n8n had **no runtime exposure**. Fixed:

- **`/api/v1/proactive/*`** (`api/routes/proactive.py`): schedule recurring
  prompts (interval or cron) whose results are stored to episodic memory, and
  watch directories so file changes become episodic memories. In-process state
  (not persisted across restarts — `GET /status` is the source of truth);
  scheduler/watcher stopped cleanly via an app shutdown hook.
- **`/api/v1/n8n/*`** (`api/routes/n8n.py`): list/run/activate/deactivate
  workflows through the existing `N8NClient`.
- **Bug fixed**: `FileWatcher.stop()` joined a never-started observer thread
  (crashed shutdown if a watch had only ever failed validation).

## Load test results (2026-06-09)

Conditions: native Windows dev server (uvicorn `--reload`, single process,
embedded SQLite/Chroma), localhost, run via `scripts/load_test.py`.

**Throughput + latency (`/health`):**

| Workers | Duration | Requests | Errors | RPS | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| 4 | 10s | 1726 | 0 | 172.6 | 16ms | 32ms | 47ms |
| 20 | 15s | 1451 | 0 | 96.7 | 109ms | 687ms | 1140ms |

Single-process queueing dominates at 20-way concurrency — expected for a
personal assistant serving one user; multiple uvicorn workers are the lever if
it ever matters.

**Rate limiter (`/api/v1/status`, burst of 150, limit 120/min):**
first 429 at exactly request #120 of the window, `Retry-After: 8`. 0 false
positives on the exempt `/health` path.

## Honestly out of scope

- **GPU training**: the LoRA pipeline works (smoke-tested) but full runs need
  a GPU; CPU-only is impractical.
- **Multi-replica rate limiting**: the limiter is in-process by design.
- **Schedule persistence**: proactive schedules don't survive restarts (v1).

## Verification

- `ruff check` / `ruff format --check`: clean
- `mypy`: clean
- `pytest tests/unit`: 138 passing (124 prior + 14 new proactive/n8n)

With this, every numbered phase (1–5) is closed. Future work is backlog-driven,
not phase-driven.
