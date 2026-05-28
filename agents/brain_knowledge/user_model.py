"""User model for digital twin representation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from brain_memory.store import MemoryStore


class UserProfile(BaseModel):
    """User profile data."""

    user_id: str
    name: str = ""
    email: str = ""
    preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserBehavior(BaseModel):
    """User behavior patterns."""

    active_hours: list[int] = Field(default_factory=list)  # Hours of day (0-23)
    common_tasks: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    communication_style: str = "neutral"
    response_patterns: dict[str, Any] = Field(default_factory=dict)


class UserModel:
    """Digital twin representation of a user."""

    def __init__(self, user_id: str, memory_store: MemoryStore) -> None:
        """Initialize user model.

        Args:
            user_id: Unique user identifier
            memory_store: Memory store for persistence
        """
        self.user_id = user_id
        self.memory = memory_store
        self.profile: UserProfile | None = None
        self.behavior: UserBehavior | None = None

    async def load(self) -> None:
        """Load user model from memory."""
        # Load profile from semantic memory
        profile_data = await self.memory.semantic.get_entity(
            entity_type="user_profile", entity_id=self.user_id
        )
        if profile_data:
            self.profile = UserProfile(**profile_data)
        else:
            self.profile = UserProfile(user_id=self.user_id)

        # Load behavior patterns
        behavior_data = await self.memory.semantic.get_entity(
            entity_type="user_behavior", entity_id=self.user_id
        )
        if behavior_data:
            self.behavior = UserBehavior(**behavior_data)
        else:
            self.behavior = UserBehavior()

    async def save(self) -> None:
        """Save user model to memory."""
        if self.profile:
            self.profile.updated_at = datetime.now()
            await self.memory.semantic.store_entity(
                entity_type="user_profile",
                entity_id=self.user_id,
                data=self.profile.model_dump(),
            )

        if self.behavior:
            await self.memory.semantic.store_entity(
                entity_type="user_behavior",
                entity_id=self.user_id,
                data=self.behavior.model_dump(),
            )

    async def update_preferences(self, preferences: dict[str, Any]) -> None:
        """Update user preferences.

        Args:
            preferences: Dict of preference key-value pairs
        """
        if not self.profile:
            await self.load()

        if self.profile:
            self.profile.preferences.update(preferences)
            await self.save()

    async def record_activity(self, activity: str, timestamp: datetime | None = None) -> None:
        """Record a user activity.

        Args:
            activity: Activity description
            timestamp: Activity timestamp (default: now)
        """
        if not self.behavior:
            await self.load()

        if self.behavior:
            ts = timestamp or datetime.now()

            # Update active hours
            hour = ts.hour
            if hour not in self.behavior.active_hours:
                self.behavior.active_hours.append(hour)
                self.behavior.active_hours.sort()

            # Update common tasks (keep top 20)
            if activity not in self.behavior.common_tasks:
                self.behavior.common_tasks.append(activity)
                if len(self.behavior.common_tasks) > 20:
                    self.behavior.common_tasks = self.behavior.common_tasks[-20:]

            await self.save()

    async def get_context(self) -> dict[str, Any]:
        """Get user context for personalization.

        Returns:
            Dict with user context
        """
        if not self.profile or not self.behavior:
            await self.load()

        return {
            "user_id": self.user_id,
            "profile": self.profile.model_dump() if self.profile else {},
            "behavior": self.behavior.model_dump() if self.behavior else {},
            "current_hour": datetime.now().hour,
            "is_active_hour": (
                datetime.now().hour in self.behavior.active_hours if self.behavior else False
            ),
        }

    async def get_personalization_hints(self) -> dict[str, Any]:
        """Get hints for personalizing responses.

        Returns:
            Dict with personalization hints
        """
        if not self.profile or not self.behavior:
            await self.load()

        hints = {
            "communication_style": (
                self.behavior.communication_style if self.behavior else "neutral"
            ),
            "preferred_tools": self.behavior.preferred_tools if self.behavior else [],
            "preferences": self.profile.preferences if self.profile else {},
        }

        return hints
