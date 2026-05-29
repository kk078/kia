"""Python FastAPI Gateway for Secondary Brain."""

import traceback
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from api.openai_compat import router as openai_router
from brain_core.config import settings
from brain_core.trace_context import set_trace_context
from brain_core.types import Context
from brain_memory.models import Episode, Fact, Skill

app = FastAPI(
    title="Secondary Brain API",
    description="Autonomous knowledge system with multi-layer memory and multi-agent orchestration",
    version="0.1.0",
)

# Allowed browser origins. In production the Worker proxies same-origin, but we
# keep an explicit allow-list (wildcard + credentials is invalid per the CORS spec).
_cors_origins = [
    "https://kia.aetherahealthcare.com",
    "http://localhost:3001",  # vite dev server
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# KIA OpenAI-compatible surface (/v1/models, /v1/chat/completions)
app.include_router(openai_router)


@app.middleware("http")
async def trace_context_middleware(request: Request, call_next: Any) -> Any:
    """Attach session + user (from Cloudflare Access) to all LLM traces for this request."""
    user = request.headers.get("x-auth-user") or request.headers.get(
        "cf-access-authenticated-user-email"
    )
    session_id = request.query_params.get("session_id") or request.headers.get("x-session-id")
    set_trace_context(session_id=session_id, user_id=user)
    return await call_next(request)


def _llm_error(e: Exception) -> HTTPException:
    """Turn an LLM provider failure into an actionable 502 instead of a bare 500."""
    traceback.print_exc()  # surface the real litellm/provider error in container logs
    hint = (
        "LLM call failed. Configure a commercial key (e.g. ANTHROPIC_API_KEY) in .env, "
        "or ensure local Ollama has the model pulled (e.g. `ollama pull llama3.2:3b`) and "
        "OLLAMA_MODEL/DEFAULT_OSS_MODEL match it."
    )
    return HTTPException(status_code=502, detail=f"{type(e).__name__}: {e} | {hint}")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/status")
async def get_status() -> dict[str, Any]:
    """Get system status."""
    return {
        "version": "0.1.0",
        "environment": settings.environment,
        "services": {
            "redis": settings.redis_url,
            "weaviate": settings.weaviate_url,
            "falkordb": settings.falkordb_url,
            "langfuse": settings.langfuse_url,
        },
    }


@app.post("/api/v1/memory/episodes")
async def store_episode(content: str, context: dict[str, Any] | None = None) -> dict[str, str]:
    """Store an episode in episodic memory."""
    from brain_memory.episodic import EpisodicMemory

    try:
        em = EpisodicMemory()
        episode = Episode(content=content, context=context or {})
        episode_id = await em.store_episode(episode)
        await em.close()
        return {"id": episode_id, "status": "stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/memory/episodes")
async def retrieve_episodes(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve episodes from episodic memory."""
    from brain_memory.episodic import EpisodicMemory

    try:
        em = EpisodicMemory()
        episodes = await em.retrieve_episodes(query, limit)
        await em.close()
        return [ep.model_dump() for ep in episodes]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/memory/facts")
async def store_fact(
    subject: str, predicate: str, object: str, confidence: float = 1.0
) -> dict[str, str]:
    """Store a fact in semantic memory."""
    from brain_memory.semantic import SemanticMemory

    try:
        sm = SemanticMemory()
        fact = Fact(subject=subject, predicate=predicate, object=object, confidence=confidence)
        fact_id = await sm.store_fact(fact)
        await sm.close()
        return {"id": fact_id, "status": "stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/memory/facts")
async def query_facts(
    subject: str | None = None,
    predicate: str | None = None,
    object: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Query facts from semantic memory."""
    from brain_memory.semantic import SemanticMemory

    try:
        sm = SemanticMemory()
        facts = await sm.query_facts(
            subject=subject, predicate=predicate, object=object, limit=limit
        )
        await sm.close()
        return [f.model_dump() for f in facts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/memory/skills")
async def store_skill(name: str, description: str, steps: list[str]) -> dict[str, str]:
    """Store a skill in procedural memory."""
    from brain_memory.procedural import ProceduralMemory

    try:
        pm = ProceduralMemory()
        skill = Skill(name=name, description=description, steps=steps)
        skill_id = await pm.store_skill(skill)
        await pm.close()
        return {"id": skill_id, "status": "stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/memory/skills")
async def list_skills() -> list[dict[str, Any]]:
    """List all skills from procedural memory."""
    from brain_memory.procedural import ProceduralMemory

    try:
        pm = ProceduralMemory()
        skills = await pm.list_skills()
        await pm.close()
        return [s.model_dump() for s in skills]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/orchestrator/run")
async def run_orchestrator(goal: str, session_id: str = "default") -> dict[str, Any]:
    """Run the orchestrator on a goal."""
    from brain_orchestrator.planner import Orchestrator

    try:
        orchestrator = Orchestrator()
        context = Context(session_id=session_id)
        response = await orchestrator.run(goal, context)
        result: dict[str, Any] = response.model_dump()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/llm/generate")
async def generate_text(
    prompt: str,
    task_type: str = "simple",
    model: str | None = None,
    session_id: str | None = None,
    verify: bool = False,
) -> dict[str, str]:
    """Generate text using LLM router (optionally with self-consistency verification)."""
    from brain_core.llm import LLMRouter

    try:
        router = LLMRouter()
        if verify or settings.verify_enabled:
            response = await router.generate_verified(prompt, task_type=task_type, model=model)
        else:
            response = await router.generate(prompt, task_type, model)
        return {"response": response}
    except Exception as e:
        raise _llm_error(e)


@app.post("/api/v1/llm/dspy")
async def dspy_answer(question: str) -> dict[str, str]:
    """Answer via a DSPy ChainOfThought program over a local model (opt-in)."""
    if not settings.dspy_enabled:
        raise HTTPException(status_code=503, detail="DSPy disabled (set DSPY_ENABLED=true)")
    from brain_core.optimize import DSPyReasoner

    try:
        return {"answer": DSPyReasoner().answer(question)}
    except Exception as e:
        raise _llm_error(e)


@app.get("/api/v1/llm/route")
async def route_task(task_type: str) -> dict[str, str]:
    """Get the model route for a task type."""
    from brain_core.llm import LLMRouter

    router = LLMRouter()
    model = router.route(task_type)
    return {"task_type": task_type, "model": model}


@app.post("/api/v1/knowledge/index")
async def index_document(content: str, source: str) -> dict[str, Any]:
    """Index a document in the knowledge base."""
    from brain_knowledge.indexer import DocumentIndexer
    from brain_knowledge.models import Document

    try:
        indexer = DocumentIndexer()
        doc = Document(content=content, source=source)
        chunk_ids = await indexer.index_document(doc)
        return {"chunk_ids": chunk_ids, "status": "indexed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/knowledge/retrieve")
async def retrieve_context(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve context from knowledge base."""
    from brain_knowledge.retriever import ContextRetriever

    try:
        retriever = ContextRetriever()
        chunks = await retriever.retrieve_context(query, top_k)
        return [c.model_dump() for c in chunks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/knowledge/graphrag/ingest")
async def graphrag_ingest(text: str, document_id: str) -> dict[str, Any]:
    """Ingest text into the FalkorDB knowledge graph (provider-free, local models)."""
    if not settings.graphrag_enabled:
        raise HTTPException(status_code=503, detail="GraphRAG disabled (set GRAPHRAG_ENABLED=true)")
    from brain_knowledge.graphrag import GraphRAGEngine

    try:
        return await GraphRAGEngine().ingest(text, document_id)
    except Exception as e:
        raise _llm_error(e)


@app.post("/api/v1/knowledge/graphrag/query")
async def graphrag_query(question: str) -> dict[str, str]:
    """Answer a question via knowledge-graph traversal (cited, multi-hop)."""
    if not settings.graphrag_enabled:
        raise HTTPException(status_code=503, detail="GraphRAG disabled (set GRAPHRAG_ENABLED=true)")
    from brain_knowledge.graphrag import GraphRAGEngine

    try:
        return {"answer": await GraphRAGEngine().query(question)}
    except Exception as e:
        raise _llm_error(e)


@app.post("/api/v1/knowledge/rag")
async def rag_query(
    question: str, model: str | None = None, session_id: str | None = None
) -> dict[str, str]:
    """Answer a question using RAG."""
    from brain_knowledge.rag import RAGEngine

    try:
        rag = RAGEngine()
        answer = await rag.query(question, model)
        return {"answer": answer}
    except Exception as e:
        raise _llm_error(e)
