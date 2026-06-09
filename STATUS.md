# KIA (Secondary Brain) — Project Status

**Date**: 2026-06-09
**Status**: Stabilized — phased roadmap (1–4) complete, hardening pass applied

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
| MCP (server + connectors) | ✅ stdio MCP server; connector client in chat + `/connectors` |
| Host execution | ✅ confirmation-gated planner → host runner |
| **API auth + rate limiting** | ✅ `KIA_API_KEY` bearer/X-API-Key + per-client sliding window (2026-06-09) |
| Observability | ✅ OpenTelemetry, Langfuse, Prometheus/Grafana/Loki configs |

## Quality Gates (last verified 2026-06-09)

- `ruff check` — clean
- `ruff format --check` — clean
- `mypy` — clean (116 source files)
- `pytest tests/unit` — all passing (120+ tests)

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

1. **Load testing** — never performed; the in-process rate limiter is
   single-instance by design.
2. **`brain_proactive`** — watchers/schedulers are partial.
3. **`brain_n8n`** — bridge exists; little real workflow coverage.
4. **`worker/`** — Cloudflare worker directory is minimal (deployment lives in
   CI + `CLOUDFLARE_DEPLOYMENT.md`).
5. **Training on CPU** — full LoRA runs need a GPU; smoke mode validates the
   pipeline only.
6. **README/AGENTS.md** — still describe the Docker/Weaviate stack as primary;
   accurate for server mode, but native mode is the daily driver.

## History

- Phases 1–4 (foundation → memory → orchestration → training → API/MCP):
  complete, see `PHASE_*_COMPLETE.md`
- Post-phase work (May–June 2026): native deployment, tiered failover, build
  agent + evals, LoRA loop, web/vision/audio in chat, honest persona,
  auth + rate limiting
