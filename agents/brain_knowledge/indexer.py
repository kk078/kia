"""Document indexer using LlamaIndex (with content-hash dedup)."""

import hashlib
import os
import re
import uuid

from llama_index.core import Document as LlamaDocument
from llama_index.core import VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter

from brain_core.config import settings
from brain_core.security import sanitize_untrusted
from brain_knowledge.models import Document
from brain_knowledge.vector_store import get_vector_store


def _content_hash(text: str) -> str:
    """Stable hash of normalized content for duplicate detection."""
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class DocumentIndexer:
    """Indexes documents into Weaviate using LlamaIndex, skipping duplicates."""

    def __init__(self, collection: str = "KiaKnowledge") -> None:
        """Initialize the document indexer and load the seen-content registry."""
        self.vector_store = get_vector_store(collection)
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        self._splitter = SentenceSplitter()
        data_dir = os.path.dirname(settings.training_capture_path) or "."
        self._hash_file = os.path.join(data_dir, "ingest_hashes.txt")
        self._seen: set[str] = set()
        try:
            if os.path.exists(self._hash_file):
                with open(self._hash_file, encoding="utf-8") as f:
                    self._seen = {ln.strip() for ln in f if ln.strip()}
        except OSError:
            self._seen = set()

    def _remember(self, h: str) -> None:
        self._seen.add(h)
        try:
            os.makedirs(os.path.dirname(self._hash_file) or ".", exist_ok=True)
            with open(self._hash_file, "a", encoding="utf-8") as f:
                f.write(h + "\n")
        except OSError:
            pass

    async def index_document(self, document: Document) -> list[str]:
        """Index a document (sanitized + deduped) and return chunk IDs (empty if dup/blocked)."""
        guard = sanitize_untrusted(document.content)
        if guard.blocked:
            # High-risk content is refused at the ingestion boundary.
            return []
        # Duplicate detection: skip content KIA has already learned.
        h = _content_hash(guard.clean_text)
        if h in self._seen:
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
                "content_hash": h,
                **document.metadata,
            },
        )
        # Chunk explicitly so we can report and return the real per-chunk IDs.
        nodes = self._splitter.get_nodes_from_documents([llama_doc])
        if not nodes:
            return []
        self.index.insert_nodes(nodes)
        self._remember(h)
        return [n.node_id for n in nodes]

    async def index_documents(self, documents: list[Document]) -> list[str]:
        """Index multiple documents and return chunk IDs."""
        chunk_ids: list[str] = []
        for doc in documents:
            ids = await self.index_document(doc)
            chunk_ids.extend(ids)
        return chunk_ids
