# Secondary Brain

Autonomous knowledge system with multi-layer memory, hierarchical planning, and multi-agent orchestration.

## Features

- **Multi-Layer Memory**: Working (Redis), Episodic (Weaviate), Semantic (Weaviate + FalkorDB), Procedural
- **Hierarchical Planning**: LangGraph orchestrator with strategic + tactical planners
- **Multi-Agent Orchestration**: CrewAI crews, smolagents researchers, Agno lightweight agents
- **Knowledge Graph**: Entity extraction, relationship tracking, temporal reasoning
- **Proactive Behavior**: File watchers, schedulers, predictive layer
- **Multi-Modal Ingestion**: OCR, audio transcription, image understanding
- **Unified API Gateway**: ASP.NET Core REST API + MCP server
- **Observability**: Langfuse tracing, eval harness, dashboards
- **Workflow Automation**: n8n integration for external services

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Gateway | ASP.NET Core 8, MCP |
| Agents | Python 3.11+, uv workspace |
| Orchestration | LangGraph, CrewAI |
| Research | smolagents, Agno |
| RAG | LlamaIndex |
| Vector DB | Weaviate |
| Graph DB | FalkorDB |
| Cache/Bus | Redis |
| Observability | Langfuse |
| Local LLMs | Ollama |
| Workflow | n8n |

## Quick Start

### Prerequisites

- Python 3.11+
- .NET SDK 8.0
- Node.js 18+
- Docker Desktop
- Ollama (for local models)

### Setup

1. **Clone and install tools**
   ```powershell
   # Install uv (Python package manager)
   irm https://astral.sh/uv/install.ps1 | iex
   
   # Install n8n
   npm install -g n8n
   ```

2. **Start infrastructure**
   ```powershell
   docker-compose up -d
   ```

3. **Configure environment**
   ```powershell
   copy .env.example .env
   # Edit .env with your API keys
   ```

4. **Install dependencies**
   ```powershell
   # Python
   uv sync
   
   # .NET
   dotnet restore gateway/Gateway.sln
   ```

5. **Run tests**
   ```powershell
   # Python
   uv run pytest tests/unit -v
   
   # .NET
   dotnet test gateway/Gateway.sln
   ```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    .NET Gateway (ASP.NET Core)           │
│         Unified API  |  MCP Server  |  Router           │
└──────────────┬──────────────────────────────┬───────────┘
               │ HTTP/gRPC                    │ MCP
┌──────────────▼──────────────────────────────▼───────────┐
│                  Python Agent Layer (uv workspace)       │
│                                                         │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Orchestrator │  │  Crews   │  │   Researchers     │  │
│  │ (LangGraph)  │  │ (CrewAI) │  │ (smolagents/Agno) │  │
│  └──────┬───────┘  └────┬─────┘  └────────┬──────────┘  │
│         │               │                  │             │
│  ┌──────▼───────────────▼──────────────────▼──────────┐  │
│  │              Core (shared primitives)               │  │
│  │  BaseAgent | LLM Router | Reflection | Confidence  │  │
│  │  World Model | User Model | A2A Protocol | Tracing │  │
│  └──────┬───────────────┬──────────────────┬──────────┘  │
│         │               │                  │             │
│  ┌──────▼──────┐ ┌──────▼──────┐  ┌───────▼──────────┐  │
│  │  Knowledge  │ │  Proactive  │  │   n8n Bridge     │  │
│  │ (LlamaIndex │ │ (Scheduler, │  │  (API client,    │  │
│  │  + Ingestion│ │  Watchers,  │  │   workflow auto) │  │
│  │  + Graph)   │ │  Predictors)│  │                  │  │
│  └──────┬──────┘ └──────┬──────┘  └───────┬──────────┘  │
└─────────┼───────────────┼──────────────────┼────────────┘
          │               │                  │
┌─────────▼───────────────▼──────────────────▼────────────┐
│                    Infrastructure (native)               │
│  Redis (cache + A2A bus)  |  Weaviate (vectors)         │
│  FalkorDB (knowledge graph) | Langfuse (observability)  │
│  n8n (workflows)          |  Ollama (local LLMs)        │
└─────────────────────────────────────────────────────────┘
```

## Development

### Running Tests

```powershell
# Python unit tests
uv run pytest tests/unit -v

# Python integration tests (requires infrastructure)
uv run pytest tests/integration -v -m integration

# .NET tests
dotnet test gateway/Gateway.sln

# Lint + typecheck
uv run ruff check .
uv run mypy .
```

### Starting Services

```powershell
# Infrastructure
docker-compose up -d

# Python API (future)
uv run uvicorn agents.api.main:app --reload --port 8001

# .NET Gateway (future)
dotnet run --project gateway/Gateway.Api

# n8n
n8n start
```

## Documentation

- [Architecture](docs/architecture.md)
- [Memory System](docs/memory.md)
- [API Reference](docs/api.md)
- [Agent Instructions](AGENTS.md)

## License

MIT
