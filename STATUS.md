# KIA (Secondary Brain) — Project Status

**Date**: 2026-06-09
**Status**: Stabilized — all phases (1–5) complete (see `PHASE_5_COMPLETE.md`)

KIA is a personal AI assistant platform running natively on Windows: FastAPI
backend, React frontend, local-first LLMs (Ollama) with tiered cloud failover,
4-layer persistent memory, an autonomous build agent, and a LoRA fine-tuning
loop fed by captured usage traces.

---

## Current Deployment (native Windows — primary mode)

- `kia_native_run.ps1` — uvicorn on :8000, embedded Chroma + SQLite (no Docker),
  Ollama on :11434, host runner on 127.0.0.1:8765, `kia_watchdog.ps1` self-healing
- Docker compose stacks (`docker-compose*.yml`) remain available for the
  server-backed mode (Redis/Weaviate/FalkorDB/Langfuse)
- Cloudflare Worker + tunnel front the API for remote access

## What Works Today

| Area | State |
|---|---|
| Chat (SSE streaming, history, multi-turn) | ✅ SQLite/Redis-backed, cloud→local fallback |
| Live web retrieval in chat | ✅ web_search/web_fetch + planner phase, read-only |
| Vision / audio | ✅ Ollama llama3.2-vision, faster-whisper endpoints |
| Build agent (`/agent`) | ✅ ReAct loop, approval gates, hard verification gate, Claude escalation |
| Eval suite | ✅ ~30 categorized scenarios, per-tag pass rates (`brain_build/eval.py`) |
| Training loop | ✅ trace capture → LoRA fine-tune (`kia_train.ps1`) → Ollama export |
| Memory (4 layers) | ✅ native SQLite backends; Weaviate/FalkorDB in server mode |
| RAG + GraphRAG | ✅ hybrid retrieval; GraphRAG opt-in |
| MCP (server + connectors) | ✅ stdio MCP server; 7 live connector servers / 55 tools (filesystem, fetch, DDG search, KG memory, sequential-thinking, time, GitHub); persistent pool (~30x faster warm calls); ambient chat is read-only-gated (2026-06-09) |
| Host execution | ✅ confirmation-gated planner → host runner |
| **API auth + rate limiting** | ✅ `KIA_API_KEY` bearer/X-API-Key + per-client sliding window (2026-06-09) |
| **Proactive behavior** | ✅ `/api/v1/proactive/*` — scheduled prompts + file watches feeding episodic memory (2026-06-09) |
| **n8n bridge** | ✅ `/api/v1/n8n/*` — list/run/activate workflows (2026-06-09) |
| **Load testing** | ✅ `scripts/load_test.py` — 172 RPS @ p50 16ms (4 workers); limiter verified at exactly 120/min (2026-06-09) |
| Edge worker | ✅ `worker/` — Access-JWT-validating proxy + Ollama Cloud failover (was wrongly listed as minimal) |
| Observability | ✅ OpenTelemetry, Langfuse, Prometheus/Grafana/Loki configs |

## Quality Gates (last verified 2026-06-09)

- `ruff check` — clean
- `ruff format --check` — clean
- `mypy` — clean
- `pytest tests/unit` — 138 passing

## Persona & Execution Standards

`brain_core/persona.py` defines KIA's identity and standards, applied to every
user-facing generation path (chat, generate, RAG, OpenAI-compat) and mirrored
in the build agent's prompt:

- States its real capabilities (web, code execution via /agent, connectors,
  memory); never recites false generic-LLM disclaimers
- Leads with the outcome; plain complete sentences; no filler/flattery/hedging
- Reports outcomes faithfully: "done" requires observed evidence (exit 0,
  passing test); failures are quoted, not softened; gaps are stated
- Build agent cannot `finish` without a passing command since its last change

Invariants are locked by `tests/unit/test_persona.py`.

## Security Posture

- Auth off by default (localhost native mode); **set `KIA_API_KEY` whenever the
  API is reachable beyond localhost** (tunnel/Worker). `/health` and `/metrics`
  remain open for the watchdog and Prometheus.
- Rate limiting defaults to 120 req/min per client (`RATE_LIMIT_PER_MINUTE`,
  0 disables).
- High-risk actions (host exec, build agent destructive commands) are
  confirmation-gated; prompt-injection guard on untrusted content.

## Known Gaps / Backlog

1. **Training on CPU** — full LoRA runs need a GPU; smoke mode validates the
   pipeline only.
2. **Proactive schedule persistence** — scheduled prompts/watches are
   in-process and don't survive restarts (v1; `GET /api/v1/proactive/status`
   is the source of truth).
3. **Multi-replica rate limiting** — the limiter is in-process by design;
   fine for single-instance deployments.

(Earlier versions of this file listed `brain_proactive`, `brain_n8n`, and
`worker/` as partial — auditing showed they were implemented; proactive and
n8n just lacked API exposure, added 2026-06-09.)

## History

- Phases 1–4 (foundation → memory → orchestration → training → API/MCP):
  complete, see `PHASE_*_COMPLETE.md`
- Post-phase work (May–June 2026): native deployment, tiered failover, build
  agent + evals, LoRA loop, web/vision/audio in chat, honest persona,
  auth + rate limiting
