"""Document indexer using LlamaIndex."""

from llama_index.core import Document as LlamaDocument
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.weaviate import WeaviateVectorStore

from brain_core.config import settings
from brain_knowledge.models import Document


class DocumentIndexer:
    """Indexes documents into Weaviate using LlamaIndex."""

    def __init__(self) -> None:
        """Initialize the document indexer."""
        self.vector_store = WeaviateVectorStore(
            weaviate_client=None,  # Will be initialized on first use
            index_name="Documents",
            url=settings.weaviate_url,
        )
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)

    async def index_document(self, document: Document) -> list[str]:
        """Index a document and return chunk IDs."""
        llama_doc = LlamaDocument(
            text=document.content,
            metadata={
                "source": document.source,
                "timestamp": document.timestamp.isoformat(),
                **document.metadata,
            },
        )
        self.index.insert(llama_doc)
        return [document.id] if document.id else []

    async def index_documents(self, documents: list[Document]) -> list[str]:
        """Index multiple documents and return chunk IDs."""
        chunk_ids = []
        for doc in documents:
            ids = await self.index_document(doc)
            chunk_ids.extend(ids)
        return chunk_ids
