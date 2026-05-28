"""Knowledge models for RAG and graph operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A document to be indexed."""

    id: str = Field(default_factory=lambda: "")
    content: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Chunk(BaseModel):
    """A chunk of a document."""

    id: str = Field(default_factory=lambda: "")
    document_id: str
    content: str
    embedding: list[float] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """An entity in the knowledge graph."""

    id: str = Field(default_factory=lambda: "")
    name: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class Relation(BaseModel):
    """A relation between entities."""

    id: str = Field(default_factory=lambda: "")
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
