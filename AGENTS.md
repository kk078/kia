# Secondary Brain - Agent Instructions

## Project Overview
Autonomous knowledge system with multi-layer memory, hierarchical planning, and multi-agent orchestration.
Dual-stack: Python agents + .NET gateway, running natively on Windows.

## Architecture

```
.NET Gateway (ASP.NET Core 8) ←→ Python Agents (uv workspace) ←→ Infrastructure
```

**Directory Ownership:**
- `agents/brain_core/` - Base primitives, LLM routing, A2A protocol, task router
- `agents/brain_memory/` - Multi-layer memory (working, episodic, semantic, procedural)
- `agents/brain_knowledge/` - RAG, knowledge graph, ingestion, predictive layer, user model
- `agents/brain_orchestrator/` - LangGraph planning, execution
- `agents/brain_crews/` - CrewAI multi-agent teams
- `agents/brain_researchers/` - smolagents/Agno research agents
- `agents/brain_proactive/` - Schedulers, watchers, triggers
- `agents/brain_n8n/` - n8n workflow bridge
- `agents/api/` - FastAPI gateway (REST API)
- `agents/mcp/` - MCP server (Model Context Protocol)
- `gateway/` - ASP.NET Core API + Python bridge

## Framework Selection Guide

**Use LangGraph when:**
- Complex multi-step planning with state management
- Hierarchical task decomposition
- Conditional branching and loops

**Use CrewAI when:**
- Role-based multi-agent collaboration
- Research, synthesis, review workflows
- Agents need defined roles and goals

**Use smolagents when:**
- Tool-heavy research tasks
- Web scraping, code analysis
- Lightweight single-purpose agents

**Use Agno when:**
- Fast, lightweight agents with minimal overhead
- Simple tool-use patterns
- Rapid prototyping

**Use LlamaIndex when:**
- Document indexing and retrieval
- RAG pipelines
- Complex query engines

## Commands

### Python (uv workspace)
```powershell
# Install dependencies
uv sync

# Lint
uv run ruff check .
uv run ruff format --check .

# Typecheck
uv run mypy .

# Test
uv run pytest tests/unit -v
uv run pytest tests/integration -v -m integration

# Run single test
uv run pytest tests/unit/test_core.py::test_function_name -v

# Run Python API gateway
uv run uvicorn api.main:app --reload --port 8000

# Run MCP server
uv run python -m mcp.server
```

### .NET Gateway
```powershell
# Build
dotnet build gateway/Gateway.sln

# Test
dotnet test gateway/Gateway.sln

# Run
dotnet run --project gateway/Gateway.Api

# Single test
dotnet test gateway/Gateway.Tests --filter "FullyQualifiedName=Namespace.Class.Method"
```

### Infrastructure
```powershell
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f weaviate

# Stop all
docker-compose down
```

## Critical Rules

### Memory Abstraction
**NEVER** use raw Weaviate, FalkorDB, or Redis clients outside their respective packages.
- All memory writes → `brain_memory.store.MemoryStore`
- All graph queries → `brain_knowledge.graph.KnowledgeGraph`
- All cache operations → `brain_core.cache.Cache`

### LLM Provider Conventions
- API keys via environment variables only (see `.env.example`)
- Use `litellm` for all LLM calls (unified interface)
- Model strings: `provider/model` (e.g., `anthropic/claude-3-5-sonnet`, `ollama/llama3.1`)
- Routing logic in `brain_core.llm.LLMRouter`

### A2A Protocol
- All agent communication via Redis pub/sub
- Channel naming: `brain:{agent_type}:{agent_id}`
- Message format: `A2AMessage` from `brain_core.a2a`

### n8n Bridge
- All n8n interactions via `brain_n8n.client.N8NClient`
- Never make raw HTTP calls to n8n API

### API Gateway
- Python FastAPI gateway exposes all components via REST API
- Run with: `uv run uvicorn api.main:app --reload --port 8000`
- Endpoints: `/api/v1/memory/*`, `/api/v1/orchestrator/*`, `/api/v1/llm/*`, `/api/v1/knowledge/*`
- Health check: `/health`

### Task Router
- Use `brain_core.router.TaskRouter` for intelligent framework selection
- Heuristic-based classification (fast) or LLM-based classification (accurate)
- Returns framework, complexity, and reasoning

### MCP Server
- Exposes brain capabilities as MCP tools
- Tools: memory operations, knowledge queries, orchestration, LLM generation
- Run with: `uv run python -m mcp.server`
- Connect from OpenCode or any MCP client

### Observability
- OpenTelemetry tracing integrated into LLMRouter, Orchestrator, MemoryStore
- Metrics collection for LLM calls, agent invocations, memory operations, API requests
- Langfuse for LLM-specific observability (traces, generations, scores)
- Access Langfuse UI: http://localhost:3000
- Configure via environment variables: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_URL`

### Evaluation Harness
```powershell
# List available benchmark scenarios
uv run python -m evals.runner --list

# Run single benchmark (with mock responses)
uv run python -m evals.runner simple_qa

# Run single benchmark (with real brain system)
uv run python -m evals.runner simple_qa --no-mock

# Run all benchmarks
uv run python -m evals.runner --all

# Save results to file
uv run python -m evals.runner --all --output results.json
```

**Available Benchmarks:**
- `simple_qa` - Simple question answering
- `code_explanation` - Code explanation task
- `summarization` - Text summarization
- `planning_task` - Complex planning task
- `research_task` - Research and synthesis

**Evaluators:**
- Task completion (response quality, keyword matching)
- RAG accuracy (retrieval quality, answer relevance)
- Latency (response time, percentiles)

## Testing

### Unit Tests
- No external services required
- Mock LLM calls with `pytest-mock`
- Fast execution (< 10s)

### Integration Tests
- Require Redis, Weaviate, FalkorDB running
- Mark with `@pytest.mark.integration`
- Use real services, mock LLM calls

### Test Order
```powershell
uv run ruff check .
uv run mypy .
uv run pytest tests/unit -v
uv run pytest tests/integration -v -m integration
```

## Infrastructure Services

| Service | Port | Purpose |
|---------|------|---------|
| Redis | 6379 | Working memory + A2A bus |
| Weaviate | 8081 | Vector store (episodic/semantic) |
| FalkorDB | 6380 | Knowledge graph |
| Langfuse | 3000 | Observability + eval |
| n8n | 5678 | Workflow automation |
| Ollama | 11434 | Local LLMs |
| Python API | 8000 | FastAPI gateway |
| .NET Gateway | 5000 | ASP.NET Core unified API |

## Environment Setup

1. Copy `.env.example` to `.env`
2. Fill in API keys (Anthropic, OpenAI, etc.)
3. Start infrastructure: `docker-compose up -d`
4. Install Python deps: `uv sync`
5. Install .NET deps: `dotnet restore gateway/Gateway.sln`
6. Create Langfuse project and add keys to `.env`

## Common Pitfalls

1. **Wrong framework**: Don't use CrewAI for simple tasks or smolagents for complex planning
2. **Bypassing abstractions**: Never use raw DB clients outside their packages
3. **Hardcoded models**: Always use `LLMRouter` for model selection
4. **Missing tests**: Integration tests must be marked with `@pytest.mark.integration`
5. **Port conflicts**: Weaviate is on 8081 (not 8080) due to existing services

## Code Style

### Python
- Type hints required on all public functions
- Use `pydantic` for all data models
- Async-first (use `async/await`)
- Max line length: 100 chars (ruff default)

### .NET
- Follow standard C# conventions
- Use records for DTOs
- Async methods end with `Async`
- XML docs on public APIs
