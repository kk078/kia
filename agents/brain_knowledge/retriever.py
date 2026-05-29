"""Context retriever for RAG operations."""

from llama_index.core import VectorStoreIndex

from brain_knowledge.models import Chunk
from brain_knowledge.vector_store import get_vector_store


class ContextRetriever:
    """Retrieves context from indexed documents."""

    def __init__(self) -> None:
        """Initialize the context retriever."""
        self.vector_store = get_vector_store("Documents")
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        self.retriever = self.index.as_retriever(similarity_top_k=5)

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[Chunk]:
        """Retrieve context chunks for a query."""
        nodes = self.retriever.retrieve(query)
        chunks = []
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
