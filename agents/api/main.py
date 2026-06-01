"""Python FastAPI Gateway for Secondary Brain."""

import json
import traceback
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.openai_compat import router as openai_router
from brain_core.config import settings
from brain_core.llm import needs_deep_reasoning
from brain_core.persona import KIA_SYSTEM
from brain_core.trace_context import set_trace_context
from brain_core.training_capture import capture, stats
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


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics exposition (scraped by the monitoring stack)."""
    from brain_core.metrics import render_prometheus

    return Response(content=render_prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/health/deep")
@app.get("/api/v1/health/deep")
async def deep_health_check() -> dict[str, Any]:
    """Probe every dependency and roll up a degradation level (healthy/degraded/critical)."""
    from brain_core.health import deep_health

    return await deep_health()


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
    from brain_core.fallback import resilient_generate
    from brain_core.llm import LLMRouter

    try:
        router = LLMRouter()
        auto = settings.auto_verify and needs_deep_reasoning(prompt, task_type)
        if verify or settings.verify_enabled or auto:
            # Verification path is reasoning-heavy; keep it (no silent fallback mid-judge).
            response = await router.generate_verified(
                prompt, task_type=task_type, model=model, system=KIA_SYSTEM, force=True
            )
        else:
            # Fault-tolerant path: cloud→local fallback with circuit breakers.
            response, _model_used = await resilient_generate(
                router, prompt, task_type=task_type, model=model, system=KIA_SYSTEM
            )
        capture(prompt, response, source="chat", model=model or "")
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


@app.get("/api/v1/training/stats")
async def training_stats() -> dict[str, Any]:
    """Stats about the captured fine-tuning dataset (Phase 3 capture loop)."""
    return stats()


@app.post("/api/v1/connectors/query")
async def connectors_query(prompt: str, max_steps: int = 5) -> dict[str, Any]:
    """Answer a prompt using connected MCP tools (hybrid tool-calling agent)."""
    if not settings.connectors_enabled:
        raise HTTPException(status_code=503, detail="Connectors disabled (CONNECTORS_ENABLED=true)")
    from brain_connectors.agent import ConnectorAgent
    from brain_connectors.client import MCPConnectorManager
    from brain_core.circuit_breaker import CircuitOpenError
    from brain_core.fallback import get_breaker

    breaker = get_breaker("connectors")
    manager = MCPConnectorManager(settings.connectors_config)
    try:
        await manager.connect()

        async def _run() -> str:
            return await ConnectorAgent(manager).run(prompt, max_steps=max_steps)

        # Circuit breaker: if connectors keep failing, fast-fail instead of stalling.
        answer = await breaker.call(_run)
        return {"answer": answer, "tools_available": len(manager.tools)}
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail="Connector subsystem temporarily disabled after repeated failures; retry soon.",
        )
    except Exception as e:
        raise _llm_error(e)
    finally:
        await manager.close()


@app.get("/api/v1/connectors/list")
async def connectors_list() -> dict[str, Any]:
    """List the tools exposed by currently configured MCP connectors."""
    if not settings.connectors_enabled:
        raise HTTPException(status_code=503, detail="Connectors disabled (CONNECTORS_ENABLED=true)")
    from brain_connectors.client import MCPConnectorManager

    manager = MCPConnectorManager(settings.connectors_config)
    try:
        tools = await manager.connect()
        return {"tools": [t["function"]["name"] for t in tools], "count": len(tools)}
    finally:
        await manager.close()


# ---------------------------------------------------------------------------
# Host command execution (confirmation-gated): plan -> approve in UI -> run
# ---------------------------------------------------------------------------


class ExecPlanRequest(BaseModel):
    """A natural-language task to turn into reviewable shell commands."""

    task: str
    os: str = "Windows"


class ExecRunRequest(BaseModel):
    """Run one approved command from a previously-planned set."""

    plan_id: str
    index: int


@app.get("/api/v1/exec/status")
async def exec_status() -> dict[str, Any]:
    """Whether execution is enabled and the host runner is reachable."""
    if not settings.exec_enabled:
        return {"enabled": False}
    from brain_exec.runner_client import HostRunnerClient

    return {"enabled": True, "runner": await HostRunnerClient().health()}


@app.post("/api/v1/exec/plan")
async def exec_plan(body: ExecPlanRequest) -> dict[str, Any]:
    """Propose shell commands for a task. Does NOT execute anything."""
    if not settings.exec_enabled:
        raise HTTPException(status_code=503, detail="Execution disabled (set EXEC_ENABLED=true)")
    from brain_exec.planner import CommandPlanner
    from brain_exec.store import ExecPlanStore

    try:
        commands = await CommandPlanner().plan(body.task, os_name=body.os)
    except Exception as e:
        raise _llm_error(e)
    store = ExecPlanStore()
    try:
        plan_id = await store.save(body.task, commands)
    finally:
        await store.close()
    return {"plan_id": plan_id, "commands": commands, "os": body.os}


@app.post("/api/v1/exec/run")
async def exec_run(body: ExecRunRequest) -> dict[str, Any]:
    """Run a SINGLE approved command (must belong to a stored plan)."""
    if not settings.exec_enabled:
        raise HTTPException(status_code=503, detail="Execution disabled (set EXEC_ENABLED=true)")
    from brain_exec.runner_client import HostRunnerClient
    from brain_exec.store import ExecPlanStore

    store = ExecPlanStore()
    try:
        command = await store.command_at(body.plan_id, body.index)
    finally:
        await store.close()
    if command is None:
        raise HTTPException(status_code=404, detail="command not found for this plan/index")
    traceback_logged = f"[exec] running approved command: {command}"
    print(traceback_logged)  # audit trail in container logs
    result = await HostRunnerClient().run(command)
    return {"command": command, **result}


# ---------------------------------------------------------------------------
# Conversation history (durable, Redis-backed) + streaming chat
# ---------------------------------------------------------------------------


def _user_from(request: Request) -> str:
    """Resolve the user id from Cloudflare Access headers (single-user → 'default')."""
    return (
        request.headers.get("x-auth-user")
        or request.headers.get("cf-access-authenticated-user-email")
        or "default"
    )


class NewConversation(BaseModel):
    """Optional title for a new conversation."""

    title: str | None = None


class RenameConversation(BaseModel):
    """New title for an existing conversation."""

    title: str


class StreamChatRequest(BaseModel):
    """Body for the streaming chat endpoint."""

    message: str
    conversation_id: str | None = None
    task_type: str = "simple"
    model: str | None = None


@app.post("/api/v1/conversations")
async def create_conversation(request: Request, body: NewConversation) -> dict[str, Any]:
    """Create a new conversation for the current user."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        return await store.create(_user_from(request), body.title)
    finally:
        await store.close()


@app.get("/api/v1/conversations")
async def list_conversations(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    """List the current user's conversations, most recent first."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        return await store.list(_user_from(request), limit)
    finally:
        await store.close()


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    """Return a conversation's metadata + ordered messages."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        meta = await store.get_meta(conversation_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        messages = await store.messages(conversation_id)
        return {"conversation": meta, "messages": messages}
    finally:
        await store.close()


@app.patch("/api/v1/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, body: RenameConversation) -> dict[str, str]:
    """Rename a conversation."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        ok = await store.rename(conversation_id, body.title)
        if not ok:
            raise HTTPException(status_code=404, detail="conversation not found")
        return {"status": "renamed"}
    finally:
        await store.close()


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, str]:
    """Delete a conversation (user-initiated)."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        await store.delete(conversation_id)
        return {"status": "deleted"}
    finally:
        await store.close()


class AppendMessages(BaseModel):
    """Append one or more {role, content} turns to a conversation."""

    messages: list[dict[str, str]]


@app.post("/api/v1/conversations/{conversation_id}/messages")
async def append_messages(conversation_id: str, body: AppendMessages) -> dict[str, Any]:
    """Append turns to a conversation (used to persist non-streamed slash commands)."""
    from brain_memory.conversations import ConversationStore

    store = ConversationStore()
    try:
        count = 0
        for m in body.messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if content and role in ("user", "assistant"):
                if await store.append(conversation_id, role, content):
                    count += 1
        return {"status": "appended", "count": count}
    finally:
        await store.close()


def _sse(payload: dict[str, Any]) -> str:
    """Encode one Server-Sent Event line."""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@app.post("/api/v1/chat/stream")
async def chat_stream(request: Request, body: StreamChatRequest) -> StreamingResponse:
    """Stream a chat reply token-by-token (SSE) with cloud→local fallback, and
    persist both the user message and the full reply to durable history."""
    from brain_core.fallback import resilient_stream
    from brain_core.llm import LLMRouter
    from brain_memory.conversations import ConversationStore

    user_id = _user_from(request)
    store = ConversationStore()
    router = LLMRouter()

    # Ensure a conversation exists, then persist the user's message up-front so it
    # is never lost even if the stream is interrupted.
    conv_id = body.conversation_id
    if not conv_id:
        meta = await store.create(user_id)
        conv_id = str(meta["id"])
    prior = await store.messages(conv_id)
    await store.append(conv_id, "user", body.message)

    # Build the LLM message list: persona + recent history + new user turn.
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": KIA_SYSTEM}]
    for m in prior[-20:]:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            llm_messages.append({"role": role, "content": content})
    llm_messages.append({"role": "user", "content": body.message})

    async def event_stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "meta", "conversation_id": conv_id})
        full: list[str] = []
        model_used = "unknown"
        try:
            async for piece, used in resilient_stream(
                router, llm_messages, task_type=body.task_type, model=body.model
            ):
                model_used = used
                full.append(piece)
                yield _sse({"type": "token", "content": piece})
        except Exception as e:  # never break the SSE contract
            yield _sse({"type": "token", "content": f"\n\n[KIA error: {type(e).__name__}]"})
        answer = "".join(full)
        await store.append(conv_id, "assistant", answer)
        try:
            capture(body.message, answer, source="chat-stream", model=model_used)
        except Exception:
            pass
        await store.close()
        yield _sse({"type": "done", "conversation_id": conv_id, "model": model_used})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/knowledge/index")
async def index_document(content: str, source: str) -> dict[str, Any]:
    """Index a document in the knowledge base."""
    from brain_knowledge.indexer import DocumentIndexer
    from brain_knowledge.models import Document

    try:
        indexer = DocumentIndexer(collection="KiaCodebase")
        doc = Document(content=content, source=source)
        chunk_ids = await indexer.index_document(doc)
        return {"chunk_ids": chunk_ids, "status": "indexed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class IngestItem(BaseModel):
    """JSON body for ingesting large content (e.g. source files) without query limits."""

    content: str
    source: str
    collection: str = "KiaKnowledge"


@app.post("/api/v1/knowledge/ingest")
async def ingest_document(item: IngestItem) -> dict[str, Any]:
    """Index a document supplied via JSON body (for large content like code files)."""
    from brain_knowledge.indexer import DocumentIndexer
    from brain_knowledge.models import Document

    try:
        indexer = DocumentIndexer(collection=item.collection)
        doc = Document(content=item.content, source=item.source)
        chunk_ids = await indexer.index_document(doc)
        return {"chunk_ids": chunk_ids, "status": "indexed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/knowledge/clear")
async def clear_knowledge(collection: str = "KiaKnowledge") -> dict[str, str]:
    """Delete a knowledge collection so a re-index does not create duplicates."""
    from brain_knowledge.vector_store import get_weaviate_client

    try:
        client = get_weaviate_client()
        try:
            client.collections.delete(collection)
        finally:
            client.close()
        return {"status": "cleared", "collection": collection}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LearnItem(BaseModel):
    """In-chat teaching payload: free text KIA should learn."""

    text: str
    source: str | None = None


@app.post("/api/v1/learn")
async def learn(item: LearnItem) -> dict[str, Any]:
    """Teach KIA from pasted text: index to the knowledge base now, queue for next fine-tune."""
    import json as _json
    import os as _os

    from brain_knowledge.indexer import DocumentIndexer
    from brain_knowledge.models import Document

    src = item.source or f"chat-learn-{datetime.utcnow().date().isoformat()}"
    try:
        indexer = DocumentIndexer()
        chunk_ids = await indexer.index_document(Document(content=item.text, source=src))
    except Exception as e:
        raise _llm_error(e)
    queued = False
    try:
        qpath = settings.training_capture_path.replace("kia_train.jsonl", "kia_learn_queue.jsonl")
        parent = _os.path.dirname(qpath)
        if parent:
            _os.makedirs(parent, exist_ok=True)
        with open(qpath, "a", encoding="utf-8") as f:
            f.write(
                _json.dumps(
                    {"text": item.text, "source": src, "ts": datetime.utcnow().isoformat()},
                    ensure_ascii=False,
                )
                + "\n"
            )
        queued = True
    except Exception:
        queued = False
    return {"status": "learned", "chunks_indexed": len(chunk_ids), "source": src, "queued": queued}


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
    """Answer a question using RAG, degrading to plain generation if retrieval is down."""
    from brain_knowledge.rag import RAGEngine

    try:
        rag = RAGEngine()
        answer = await rag.query(question, model)
        return {"answer": answer}
    except Exception:
        # Graceful degradation: Weaviate/retrieval unavailable → answer from the model
        # alone (with a note) rather than failing the request outright.
        from brain_core.fallback import resilient_generate
        from brain_core.llm import LLMRouter

        try:
            text, _used = await resilient_generate(
                LLMRouter(), question, task_type="research", model=model, system=KIA_SYSTEM
            )
            return {"answer": text, "degraded": "retrieval unavailable — answered without sources"}
        except Exception as e:
            raise _llm_error(e)
