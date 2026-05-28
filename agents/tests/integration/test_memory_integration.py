"""Integration tests for memory system with real services."""

import pytest

from brain_memory.episodic import EpisodicMemory
from brain_memory.models import Episode, Fact
from brain_memory.semantic import SemanticMemory
from brain_memory.working import WorkingMemory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_working_memory_set_get() -> None:
    """Test working memory set and get operations."""
    wm = WorkingMemory()
    await wm.set("test-session", "key1", "value1")
    result = await wm.get("test-session", "key1")
    assert result == "value1"
    await wm.delete("test-session", "key1")
    await wm.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_episodic_memory_store_retrieve() -> None:
    """Test episodic memory store and retrieve."""
    em = EpisodicMemory()
    episode = Episode(
        content="Test episode for integration testing",
        context={"test": True},
    )
    episode_id = await em.store_episode(episode)
    assert episode_id

    episodes = await em.retrieve_episodes("test episode", limit=5)
    assert len(episodes) > 0
    assert any("test" in ep.content.lower() for ep in episodes)
    await em.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_memory_store_query() -> None:
    """Test semantic memory store and query."""
    sm = SemanticMemory()
    fact = Fact(
        subject="Python",
        predicate="is_a",
        object="programming_language",
        confidence=0.99,
    )
    fact_id = await sm.store_fact(fact)
    assert fact_id

    facts = await sm.query_facts(subject="Python")
    assert len(facts) > 0
    assert any(f.subject == "Python" for f in facts)
    await sm.close()
