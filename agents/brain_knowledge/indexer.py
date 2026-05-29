"""Document indexer using LlamaIndex."""

import uuid

from llama_index.core import Document as LlamaDocument
from llama_index.core import VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter

from brain_core.security import sanitize_untrusted
from brain_knowledge.models import Document
from brain_knowledge.vector_store import get_vector_store


class DocumentIndexer:
    """Indexes documents into Weaviate using LlamaIndex."""

    def __init__(self) -> None:
        """Initialize the document indexer."""
        self.vector_store = get_vector_store("Documents")
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        self._splitter = SentenceSplitter()

    async def index_document(self, document: Document) -> list[str]:
        """Index a document (sanitized against prompt injection) and return chunk IDs."""
        guard = sanitize_untrusted(document.content)
        if guard.blocked:
            # High-risk content is refused at the ingestion boundary.
            return []
        doc_id = document.id or uuid.uuid4().hex
        # Prepend the (trusted) source path so retrieval matches on filename and the
        # model can cite where each chunk came from.
        text = f"# Source: {document.source}\n\n{guard.clean_text}"
        llama_doc = LlamaDocument(
            text=text,
            id_=doc_id,
            metadata={
                "source": document.source,
                "timestamp": document.timestamp.isoformat(),
                "guard_risk": guard.risk,
                "guard_findings": ",".join(f.kind for f in guard.findings),
                **document.metadata,
            },
        )
        # Chunk explicitly so we can report and return the real per-chunk IDs.
        nodes = self._splitter.get_nodes_from_documents([llama_doc])
        if not nodes:
            return []
        self.index.insert_nodes(nodes)
        return [n.node_id for n in nodes]

    async def index_documents(self, documents: list[Document]) -> list[str]:
        """Index multiple documents and return chunk IDs."""
        chunk_ids: list[str] = []
        for doc in documents:
            ids = await self.index_document(doc)
            chunk_ids.extend(ids)
        return chunk_ids
