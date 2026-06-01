"""Context retriever for RAG (hybrid keyword + vector search).

Weaviate backend uses its native BM25+vector hybrid. The embedded Chroma backend is
vector-only, so we add a lightweight keyword pass here (dependency-free): exact-term
matches (e.g. a city or company name) are surfaced first, then vector results fill in.
This restores the precision that pure vector search loses on small structured records.
"""

from __future__ import annotations

import re
from typing import Any

from llama_index.core import VectorStoreIndex

from brain_core.config import settings
from brain_knowledge.models import Chunk
from brain_knowledge.vector_store import get_vector_store


class ContextRetriever:
    """Retrieves context from indexed documents using hybrid search."""

    def __init__(self, collection: str = "KiaKnowledge") -> None:
        """Initialize the context retriever."""
        self.collection = collection
        self.vector_store = get_vector_store(collection)
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        self._chroma = (settings.vector_backend or "weaviate").lower() == "chroma"

    async def retrieve_context(self, query: str, top_k: int = 8) -> list[Chunk]:
        """Retrieve context chunks (hybrid keyword + vector)."""
        if self._chroma:
            return self._chroma_hybrid(query, top_k)
        return self._weaviate_hybrid(query, top_k)

    def _weaviate_hybrid(self, query: str, top_k: int) -> list[Chunk]:
        """Weaviate native BM25+vector hybrid, with a vector-only fallback."""
        try:
            retriever = self.index.as_retriever(
                similarity_top_k=top_k, vector_store_query_mode="hybrid", alpha=0.5
            )
            nodes = retriever.retrieve(query)
        except Exception:
            nodes = self.index.as_retriever(similarity_top_k=top_k).retrieve(query)
        return [self._to_chunk(getattr(n, "node", n)) for n in nodes[:top_k]]

    def _chroma_hybrid(self, query: str, top_k: int) -> list[Chunk]:
        """Vector results, with exact keyword matches surfaced first (in-process fusion)."""
        # 1. vector results
        vec_nodes: list[Any] = []
        try:
            vec = self.index.as_retriever(similarity_top_k=top_k).retrieve(query)
            vec_nodes = [getattr(n, "node", n) for n in vec]
        except Exception:
            vec_nodes = []

        # 2. keyword scan over all records (small KB) — score by query-term hit count
        terms = re.findall(r"[a-z0-9]{3,}", query.lower())
        kw_nodes: list[Any] = []
        if terms:
            scored: list[tuple[int, Any]] = []
            for node in self._all_nodes():
                text = (getattr(node, "text", "") or "").lower()
                score = sum(text.count(t) for t in terms)
                if score:
                    scored.append((score, node))
            scored.sort(key=lambda x: -x[0])
            kw_nodes = [n for _, n in scored[:top_k]]

        # 3. fuse: keyword (exact) first, then vector; dedup by node id; cap at top_k
        out: list[Chunk] = []
        seen: set[str] = set()
        for node in kw_nodes + vec_nodes:
            nid = str(getattr(node, "node_id", None) or getattr(node, "id_", "") or "")
            if nid and nid in seen:
                continue
            seen.add(nid)
            out.append(self._to_chunk(node))
            if len(out) >= top_k:
                break
        return out

    def _all_nodes(self) -> list[Any]:
        """Load all records from the Chroma collection as TextNodes (small KB).

        Reuse the vector store's OWN chroma collection — opening a second
        PersistentClient to the same path in-process makes chromadb error out.
        """
        from llama_index.core.schema import TextNode

        coll = getattr(self.vector_store, "_collection", None)
        if coll is None:
            return []
        try:
            data = coll.get(include=["documents", "metadatas"])
        except Exception:
            return []
        docs = data.get("documents") or []
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        nodes: list[Any] = []
        for i, doc in enumerate(docs):
            nodes.append(
                TextNode(
                    text=doc or "",
                    id_=ids[i] if i < len(ids) else None,
                    metadata=(metas[i] if i < len(metas) and metas[i] else {}),
                )
            )
        return nodes

    @staticmethod
    def _to_chunk(node: Any) -> Chunk:
        """Normalize a LlamaIndex node into a Chunk."""
        meta = getattr(node, "metadata", {}) or {}
        return Chunk(
            id=str(getattr(node, "node_id", "") or ""),
            document_id=meta.get("source", ""),
            content=getattr(node, "text", "") or "",
            metadata=meta,
        )
