"""Vector-store factory for the knowledge layer (backend-selectable).

Two backends, chosen by ``settings.vector_backend``:
  * ``weaviate`` (default) — the containerized Weaviate server (Docker/Podman).
  * ``chroma``   — an EMBEDDED ChromaDB that runs in-process and persists to
                   ``settings.chroma_path``. No server, no container, no VM —
                   used for the fully-native deployment.

Either way LlamaIndex is configured to embed with a LOCAL Ollama model
(provider-free). Heavy backend imports are lazy so only the selected backend's
package needs to be importable.
"""

from __future__ import annotations

from typing import Any

from brain_core.config import settings

KNOWLEDGE_COLLECTION = "KiaKnowledge"
CODEBASE_COLLECTION = "KiaCodebase"

_embed_configured = False


def _backend() -> str:
    return (settings.vector_backend or "weaviate").lower()


def _configure_local_embeddings() -> None:
    """Set LlamaIndex's global embed model to local Ollama (once)."""
    global _embed_configured
    if _embed_configured:
        return
    from llama_index.core import Settings
    from llama_index.embeddings.ollama import OllamaEmbedding

    # Assign through an Any alias so static checks don't gate the dynamic Settings attr.
    li_settings: Any = Settings
    li_settings.embed_model = OllamaEmbedding(
        model_name=settings.embed_model, base_url=settings.ollama_base_url
    )
    _embed_configured = True


def get_weaviate_client() -> Any:
    """Connect a Weaviate v4 client from settings.weaviate_url (http host:port)."""
    import weaviate
    from weaviate.classes.init import AdditionalConfig

    url = settings.weaviate_url.replace("http://", "").replace("https://", "")
    host, _, port_str = url.partition(":")
    port = int(port_str) if port_str else 8080
    return weaviate.connect_to_local(
        host=host or "localhost", port=port, additional_config=AdditionalConfig()
    )


def _chroma_collection(index_name: str) -> Any:
    """Get/create a persistent embedded Chroma collection."""
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(index_name)


def get_vector_store(index_name: str = KNOWLEDGE_COLLECTION) -> Any:
    """Return a LlamaIndex vector store for the selected backend (local embeddings)."""
    _configure_local_embeddings()
    if _backend() == "chroma":
        from llama_index.vector_stores.chroma import ChromaVectorStore

        return ChromaVectorStore(chroma_collection=_chroma_collection(index_name))
    from llama_index.vector_stores.weaviate import WeaviateVectorStore

    return WeaviateVectorStore(weaviate_client=get_weaviate_client(), index_name=index_name)


def clear_collection(index_name: str = KNOWLEDGE_COLLECTION) -> None:
    """Delete a collection so a re-index does not create duplicates (backend-aware)."""
    if _backend() == "chroma":
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_path)
        try:
            client.delete_collection(index_name)
        except Exception:
            pass
        return
    client = get_weaviate_client()
    try:
        client.collections.delete(index_name)
    finally:
        client.close()
