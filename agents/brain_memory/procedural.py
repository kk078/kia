"""Procedural memory (learned skills/workflows)."""

import redis.asyncio as redis

from brain_core.config import settings
from brain_memory.models import Skill


class ProceduralMemory:
    """Procedural memory for learned skills and workflows."""

    def __init__(self) -> None:
        """Initialize procedural memory with Redis connection."""
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def store_skill(self, skill: Skill) -> str:
        """Store a skill in procedural memory."""
        skill_id = skill.id or f"skill:{skill.name}"
        skill_data = skill.model_dump_json()
        await self.redis.set(f"procedural:{skill_id}", skill_data)
        return skill_id

    async def get_skill(self, skill_id: str) -> Skill | None:
        """Retrieve a skill from procedural memory."""
        skill_data = await self.redis.get(f"procedural:{skill_id}")
        if skill_data:
            return Skill.model_validate_json(skill_data)
        return None

    async def list_skills(self) -> list[Skill]:
        """List all stored skills."""
        skills = []
        async for key in self.redis.scan_iter(match="procedural:skill:*"):
            skill_data = await self.redis.get(key)
            if skill_data:
                skills.append(Skill.model_validate_json(skill_data))
        return skills

    async def update_skill_usage(self, skill_id: str, success: bool) -> None:
        """Update skill usage statistics."""
        skill = await self.get_skill(skill_id)
        if skill:
            skill.usage_count += 1
            if success:
                skill.success_rate = (
                    skill.success_rate * (skill.usage_count - 1) + 1.0
                ) / skill.usage_count
            else:
                skill.success_rate = (
                    skill.success_rate * (skill.usage_count - 1)
                ) / skill.usage_count
            await self.store_skill(skill)

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.redis.close()
