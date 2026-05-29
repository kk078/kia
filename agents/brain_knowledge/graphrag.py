"""Knowledge-graph-augmented RAG via the FalkorDB GraphRAG SDK.

Graph traversal over an entity/relationship knowledge graph beats flat vector
retrieval on multi-hop questions and returns cited, source-traceable answers.

Design goals for this brain:
- **Provider-free by default** — uses local Ollama for both generation and
  embeddings (no commercial API required).
- **Reuses the existing FalkorDB** instance (parsed from ``settings.falkordb_url``).
- **Optional / opt-in** — the SDK is lazy-imported, so importing this module
  never requires ``graphrag-sdk`` to be installed. Enable with ``graphrag_enabled``.
- **Guard-integrated** — ingested text is sanitized; high-risk content is refused.

Install to use:  ``pip install "graphrag-sdk[litellm]"`` and pull local models,
e.g. ``ollama pull llama3.2:3b`` and ``ollama pull nomic-embed-text``.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from brain_core.config import settings
from brain_core.security import sanitize_untrusted


class GraphRAGEngine:
    """Thin wrapper around the FalkorDB GraphRAG SDK, wired for local/provider-free use."""

    def __init__(
        self,
        graph_name: str | None = None,
        llm_model: str | None = None,
        embed_model: str | None = None,
    ) -> None:
        """Configure connection + models (defaults pull from settings, local-first)."""
        self.graph_name = graph_name or settings.graphrag_graph_name
        self.llm_model = (
            llm_model
            or settings.graphrag_llm_model
            or f"{settings.default_oss_provider}/{settings.default_oss_model}"
        )
        self.embed_model = embed_model or settings.graphrag_embed_model
        parsed = urlparse(settings.falkordb_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        # Ensure litellm's Ollama provider targets the configured Ollama instance.
        os.environ.setdefault("OLLAMA_API_BASE", settings.ollama_base_url)

    def _build(self) -> Any:
        """Construct a GraphRAG instance (lazy import; raises if SDK absent)."""
        from graphrag_sdk import (
            ConnectionConfig,
            GraphRAG,
            LiteLLM,
            LiteLLMEmbedder,
        )

        return GraphRAG(
            connection=ConnectionConfig(
                host=self.host, port=self.port, graph_name=self.graph_name
            ),
            llm=LiteLLM(model=self.llm_model),
            embedder=LiteLLMEmbedder(model=self.embed_model),
        )

    async def ingest(self, text: str, document_id: str) -> dict[str, Any]:
        """Sanitize then ingest text into the knowledge graph."""
        guard = sanitize_untrusted(text)
        if guard.blocked:
            return {"ingested": False, "reason": "blocked_by_guard", "risk": guard.risk}
        async with self._build() as rag:
            result = await rag.ingest(text=guard.clean_text, document_id=document_id)
            await rag.finalize()
        return {
            "ingested": True,
            "nodes": getattr(result, "nodes_created", None),
            "edges": getattr(result, "relationships_created", None),
            "guard_risk": guard.risk,
        }

    async def query(self, question: str) -> str:
        """Answer a question by retrieving + reasoning over the knowledge graph."""
        async with self._build() as rag:
            answer = await rag.completion(question)
        text: str = getattr(answer, "answer", str(answer))
        return text
