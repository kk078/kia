"""Unit tests for brain_knowledge package."""

from datetime import datetime

from brain_knowledge.models import Chunk, Document, Entity, Relation


def test_document_creation() -> None:
    """Test Document model creation."""
    doc = Document(
        content="Test document content",
        source="test.txt",
    )
    assert doc.content == "Test document content"
    assert doc.source == "test.txt"
    assert isinstance(doc.timestamp, datetime)


def test_chunk_creation() -> None:
    """Test Chunk model creation."""
    chunk = Chunk(
        document_id="doc1",
        content="Chunk content",
    )
    assert chunk.document_id == "doc1"
    assert chunk.content == "Chunk content"


def test_entity_creation() -> None:
    """Test Entity model creation."""
    entity = Entity(
        name="Python",
        type="programming_language",
        properties={"paradigm": "multi-paradigm"},
    )
    assert entity.name == "Python"
    assert entity.type == "programming_language"
    assert entity.properties["paradigm"] == "multi-paradigm"


def test_relation_creation() -> None:
    """Test Relation model creation."""
    relation = Relation(
        source_id="Python",
        target_id="programming_language",
        type="is_a",
    )
    assert relation.source_id == "Python"
    assert relation.target_id == "programming_language"
    assert relation.type == "is_a"
