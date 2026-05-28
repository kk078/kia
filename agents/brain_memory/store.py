"""Unified memory store interface."""

from brain_core.metrics import Timer, track_memory_operation
from brain_core.tracing import traced
from brain_memory.episodic import EpisodicMemory
from brain_memory.models import Episode, Fact, MemoryType, Skill
from brain_memory.procedural import ProceduralMemory
from brain_memory.semantic import SemanticMemory
from brain_memory.working import WorkingMemory


class MemoryStore:
    """Unified interface to the multi-layer memory system."""

    def __init__(self) -> None:
        """Initialize all memory layers."""
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()

    @traced(name="memory_store_episode")
    async def store_episode(self, episode: Episode) -> str:
        """Store an episode in episodic memory."""
        with Timer("memory_operation_duration", operation="store", memory_type="episodic"):
            result = await self.episodic.store_episode(episode)
            track_memory_operation("store", "episodic")
            return result

    @traced(name="memory_store_fact")
    async def store_fact(self, fact: Fact) -> str:
        """Store a fact in semantic memory."""
        with Timer("memory_operation_duration", operation="store", memory_type="semantic"):
            result = await self.semantic.store_fact(fact)
            track_memory_operation("store", "semantic")
            return result

    @traced(name="memory_store_skill")
    async def store_skill(self, skill: Skill) -> str:
        """Store a skill in procedural memory."""
        with Timer("memory_operation_duration", operation="store", memory_type="procedural"):
            result = await self.procedural.store_skill(skill)
            track_memory_operation("store", "procedural")
            return result

    @traced(name="memory_retrieve")
    async def retrieve(
        self,
        query: str,
        memory_type: MemoryType,
        limit: int = 10,
    ) -> list[Episode] | list[Fact] | list[Skill]:
        """Retrieve memories matching a query."""
        with Timer(
            "memory_operation_duration",
            operation="retrieve",
            memory_type=memory_type.value,
        ):
            if memory_type == MemoryType.EPISODIC:
                return await self.episodic.retrieve_episodes(query, limit)
            elif memory_type == MemoryType.SEMANTIC:
                return await self.semantic.query_facts(limit=limit)
            elif memory_type == MemoryType.PROCEDURAL:
                return await self.procedural.list_skills()
            else:
                raise ValueError(f"Unsupported memory type: {memory_type}")

            track_memory_operation("retrieve", memory_type.value)

    async def close(self) -> None:
        """Close all memory connections."""
        await self.working.close()
        await self.episodic.close()
        await self.semantic.close()
        await self.procedural.close()
