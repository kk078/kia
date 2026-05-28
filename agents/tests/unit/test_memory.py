"""Unit tests for brain_memory package."""

from datetime import datetime

from brain_memory.models import Episode, Fact, MemoryType, Skill


def test_episode_creation() -> None:
    """Test Episode model creation."""
    episode = Episode(content="Test episode")
    assert episode.content == "Test episode"
    assert isinstance(episode.timestamp, datetime)
    assert episode.context == {}


def test_fact_creation() -> None:
    """Test Fact model creation."""
    fact = Fact(
        subject="Python",
        predicate="is_a",
        object="programming_language",
        confidence=0.99,
    )
    assert fact.subject == "Python"
    assert fact.predicate == "is_a"
    assert fact.object == "programming_language"
    assert fact.confidence == 0.99


def test_skill_creation() -> None:
    """Test Skill model creation."""
    skill = Skill(
        name="code_review",
        description="Review code for best practices",
        steps=["Check style", "Check logic", "Check tests"],
    )
    assert skill.name == "code_review"
    assert len(skill.steps) == 3
    assert skill.success_rate == 0.0
    assert skill.usage_count == 0


def test_memory_type_enum() -> None:
    """Test MemoryType enum."""
    assert MemoryType.WORKING.value == "working"
    assert MemoryType.EPISODIC.value == "episodic"
    assert MemoryType.SEMANTIC.value == "semantic"
    assert MemoryType.PROCEDURAL.value == "procedural"
