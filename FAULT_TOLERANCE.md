# KIA — Fault Tolerance Design

How KIA stays useful when something breaks. The guiding principle is **graceful
degradation**: a failed dependency should narrow what KIA can do, never take the whole
system down. A user should always get *an* answer — even if it's "I saved your message,
the model is down, retry shortly" — rather than a spinner or a 500.

This document covers the failure modes per component, the fallback chains, the
circuit-breaker/retry policy, the three degradation levels, the health model, and the
recovery procedures. The implementation lives in `brain_core/fallback.py`,
`brain_core/circuit_breaker.py`, `brain_core/health.py`, and the resilience wiring in
`api/main.py`.

## Components and failure modes

KIA depends on five backing services. Each has a defined behavior when it fails:

| Component | Role | If it fails | Severity |
|-----------|------|-------------|----------|
| Ollama (local LLM) | Generation + embeddings | Fall back to cloud model if a key is set; otherwise KIA cannot generate | Critical (no cloud) / Degraded (cloud present) |
| Cloud model (planner/fallback) | Stronger generation + tool planning | Fall back to local Ollama | Degraded |
| Redis | Conversation history, response cache, job queue | Chat still works; history + caching disabled | Degraded |
| Weaviate | Vector retrieval (RAG) | Answers come from the model alone, uncited | Degraded |
| FalkorDB | Knowledge-graph (GraphRAG) | GraphRAG endpoints unavailable; vector RAG still works | Degraded |

The .NET gateway and Langfuse are non-critical: Langfuse tracing is best-effort (a
tracing failure never blocks a generation), and the gateway is not on the chat path.

## Fallback chains

### LLM generation — the primary chain

Every user-facing generation runs through `resilient_generate` / `resilient_stream`,
which build an ordered chain and try each model in turn, each guarded by its own
circuit breaker:

```
preferred model (router.route(task_type) — cloud if a key is set)
        │  breaker open or call fails
        ▼
local Ollama default (DEFAULT_OSS_PROVIDER/DEFAULT_OSS_MODEL)
        │  also fails
        ▼
graceful degraded message  ("models unavailable — your message was saved, retry")
```

- **Non-streaming** (`/api/v1/llm/generate`, RAG fallback): tries the full chain, returns
  the first success; on total failure returns the degraded message instead of raising.
- **Streaming** (`/api/v1/chat/stream`): falls forward to the next model *only if nothing
  has been streamed yet*. Once a token has gone out, a mid-stream error is surfaced as a
  short inline note rather than silently swapping models — the user never sees a partial
  answer replaced by a different one.

The verification path (`generate_verified`, used for reasoning-heavy prompts) is
deliberately **not** wrapped in silent fallback: switching models mid-judge would corrupt
the self-consistency vote, so it surfaces a normal error if its model is down.

### Connectors

The connector subsystem (`/api/v1/connectors/query`) runs behind a dedicated circuit
breaker named `connectors`. Repeated failures (a flaky MCP server, a stalled planner)
open the breaker, and further calls fast-fail with a `503` ("temporarily disabled after
repeated failures") instead of hanging the request thread on a broken server.

## Circuit breakers

`CircuitBreaker` (`brain_core/circuit_breaker.py`) is a consecutive-failure breaker with
three states:

- **closed** — calls pass through; failures increment a counter.
- **open** — after `BREAKER_THRESHOLD` (default 5) consecutive failures, calls fast-fail
  for `BREAKER_COOLDOWN_SECONDS` (default 30s) instead of hammering a broken dependency.
- **half-open** — after the cooldown, one trial call decides whether to close (success) or
  re-open (failure).

There is one breaker per model string (`llm:<model>`) plus one for `connectors`, all held
process-wide so state persists across requests. `breaker_states()` exposes every breaker's
state to the health endpoint.

## Retry policy

Transient provider errors are retried at the litellm layer (`LLM_NUM_RETRIES`, default 2,
with litellm's native exponential backoff) *before* a failure counts against the breaker.
So the order of defense is: **retry (transient) → fallback model (sustained) → circuit
breaker (systemic) → degraded message (total).** Retries are bounded and never applied to
streaming once tokens have started.

## Degradation levels

`GET /health/deep` (and `/api/v1/health/deep`) probes all dependencies concurrently and
rolls them into one of three levels. The chat UI shows a banner for anything but healthy.

| Level | Meaning | What still works |
|-------|---------|------------------|
| `healthy` | All dependencies up | Everything |
| `degraded` | A non-critical dependency is down, or LLM is on cloud fallback | Chat works; the specific feature (history / RAG / graph) is reduced |
| `critical` | Local LLM down **and** no cloud key configured | KIA cannot generate; messages are still persisted for retry |

The response includes per-component `{status, latency_ms, error}`, the breaker states, and
whether a cloud LLM fallback is available — enough for both the UI banner and ops triage.

## Graceful degradation by dependency

- **Redis down** → conversation history and caching are skipped. The conversation store is
  best-effort: writes return `False`, reads return empty, and chat proceeds without saving.
  The streaming endpoint still streams the answer; it just isn't persisted.
- **Weaviate down** → `/api/v1/knowledge/rag` catches the retrieval error and falls back to
  `resilient_generate`, returning an answer with a `degraded: "retrieval unavailable"` flag
  instead of failing.
- **FalkorDB down** → GraphRAG endpoints return `503`; vector RAG and chat are unaffected.
- **Cloud model down** → the fallback chain drops to the local model automatically.
- **Local model down (cloud present)** → the chain uses the cloud model; level is
  `degraded`, not `critical`.

## Durability

- **Conversation history** is stored in Redis (lists + meta hash + per-user recency ZSET).
  Production Redis runs with **AOF (`appendonly yes`)** so history survives a restart, not
  just an RDB snapshot window. Each conversation is capped at 2000 messages to bound memory.
- **Background work** (ingestion, distillation, long generations) uses the Redis Streams
  job queue (`brain_core/queue.py`) with a consumer group + explicit ack, so a job survives
  a worker crash and is redelivered rather than lost.
- **In-flight chats**: the user's message is persisted to history *before* generation
  starts, so an interrupted or failed generation never loses the user's input.

## Recovery procedures

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Banner: "Local LLM down, using cloud" | Ollama not running / model not pulled | `ollama serve`; `ollama pull <model>`; confirm `OLLAMA_BASE_URL` |
| Banner: critical | Ollama down and no cloud key | Start Ollama, or set `ANTHROPIC_API_KEY` in `.env` |
| Connectors return 503 | Connector breaker open | Fix the failing MCP server; breaker auto-closes after cooldown + a success |
| History not saving | Redis down | `docker compose ... up -d redis`; check `REDIS_URL`; chat still works meanwhile |
| RAG answers uncited (`degraded` flag) | Weaviate down | Restart Weaviate; re-check `/health/deep` |
| Breaker stuck open | Dependency still failing | Resolve root cause; one trial call after the 30s cooldown closes it on success |

## SLOs (single-user, local deployment)

These are intent targets, not contractual guarantees, for the local laptop deployment:

- **Availability of "an answer":** ≥ 99% of chat requests return either a real answer or a
  clear degraded message (never a hang or bare 500).
- **No data loss of user input:** 100% — the user message is persisted before generation.
- **Fallback latency:** a dead preferred model adds ≤ one breaker trip (~1 failed attempt)
  before the local model serves the request; once the breaker is open, fallback is immediate.
- **Recovery:** breakers self-heal within `BREAKER_COOLDOWN_SECONDS` of the dependency
  recovering.

## Tunables (`.env`)

```
LLM_NUM_RETRIES=2                 # transient retry count (litellm backoff)
BREAKER_THRESHOLD=5               # consecutive failures before a breaker opens
BREAKER_COOLDOWN_SECONDS=30       # how long a breaker stays open before a trial call
CACHE_ENABLED=true                # Redis response cache
DEFAULT_OSS_PROVIDER=ollama       # local fallback provider
DEFAULT_OSS_MODEL=llama3.2:3b     # local fallback model (must be pulled)
ANTHROPIC_API_KEY=...             # optional cloud fallback (turns 'critical' into 'degraded')
```
