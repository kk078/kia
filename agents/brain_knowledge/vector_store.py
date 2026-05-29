"""Shared Weaviate client / vector-store factory for the knowledge layer.

Centralizes the Weaviate v4 client connection (parsed from ``settings.weaviate_url``)
so the indexer and retriever use a real, connected client instead of ``None``,
and configures LlamaIndex to use a LOCAL Ollama embedding model (provider-free)
instead of defaulting to OpenAI.
"""

from __future__ import annotations

from typing import Any

import weaviate
from llama_index.vector_stores.weaviate import WeaviateVectorStore
from weaviate.classes.init import AdditionalConfig

from brain_core.config import settings

_embed_configured = False


def _configure_local_embeddings() -> None:
    """Set LlamaIndex's global embed model to local Ollama (once)."""
    global _embed_configured
    if _embed_configured:
        return
    from llama_index.core import Settings
    from llama_index.embeddings.ollama import OllamaEmbedding

    embed = OllamaEmbedding(model_name=settings.embed_model, base_url=settings.ollama_base_url)
    # setattr avoids static attribute checks while still invoking LlamaIndex's setter
    setattr(Settings, "embed_model", embed)
    _embed_configured = True


def get_weaviate_client() -> Any:
    """Connect a Weaviate v4 client from settings.weaviate_url (http host:port)."""
    url = settings.weaviate_url.replace("http://", "").replace("https://", "")
    host, _, port_str = url.partition(":")
    port = int(port_str) if port_str else 8080
    return weaviate.connect_to_local(
        host=host or "localhost", port=port, additional_config=AdditionalConfig()
    )


def get_vector_store(index_name: str = "Documents") -> Any:
    """Return a LlamaIndex WeaviateVectorStore backed by a real client (local embeddings)."""
    _configure_local_embeddings()
    return WeaviateVectorStore(weaviate_client=get_weaviate_client(), index_name=index_name)
