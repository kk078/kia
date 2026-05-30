"""Context retriever for RAG operations (hybrid keyword + vector search)."""

from typing import Any

from llama_index.core import VectorStoreIndex

from brain_knowledge.models import Chunk
from brain_knowledge.vector_store import get_vector_store


class ContextRetriever:
    """Retrieves context from indexed documents using hybrid search when available."""

    def __init__(self) -> None:
        """Initialize the context retriever."""
        self.vector_store = get_vector_store("Documents")
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)

    async def retrieve_context(self, query: str, top_k: int = 8) -> list[Chunk]:
        """Retrieve context chunks. Hybrid (BM25 keyword + vector) with vector fallback.

        Hybrid search matches exact terms (e.g. a class or file name) AND semantics,
        which fixes vector-only retrieval grabbing the wrong same-named symbol.
        """
        nodes: list[Any]
        try:
            retriever = self.index.as_retriever(
                similarity_top_k=top_k,
                vector_store_query_mode="hybrid",
                alpha=0.5,  # 0=keyword only, 1=vector only
            )
            nodes = retriever.retrieve(query)
        except Exception:
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)

        chunks: list[Chunk] = []
        for node in nodes[:top_k]:
            chunks.append(
                Chunk(
                    id=node.node_id,
                    document_id=node.metadata.get("source", ""),
                    content=node.text,
                    metadata=node.metadata,
                )
            )
        return chunks
