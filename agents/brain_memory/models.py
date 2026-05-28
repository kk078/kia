"""Memory models for the multi-layer memory system."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    """Types of memory in the system."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class Episode(BaseModel):
    """An episodic memory (timestamped event)."""

    id: str = Field(default_factory=lambda: "")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fact(BaseModel):
    """A semantic memory (distilled knowledge)."""

    id: str = Field(default_factory=lambda: "")
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Skill(BaseModel):
    """A procedural memory (learned skill/workflow)."""

    id: str = Field(default_factory=lambda: "")
    name: str
    description: str
    steps: list[str]
    success_rate: float = 0.0
    usage_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
