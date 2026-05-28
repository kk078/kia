"""Tests for predictive layer and user model."""

from datetime import datetime
from typing import Any

import pytest

from brain_knowledge.user_model import UserBehavior, UserModel, UserProfile


class TestUserProfile:
    """Test UserProfile model."""

    def test_create_profile(self) -> None:
        """Test creating a user profile."""
        profile = UserProfile(user_id="test_user")
        assert profile.user_id == "test_user"
        assert profile.name == ""
        assert profile.preferences == {}

    def test_profile_with_data(self) -> None:
        """Test creating profile with data."""
        profile = UserProfile(
            user_id="test_user",
            name="Test User",
            email="test@example.com",
            preferences={"theme": "dark"},
        )
        assert profile.name == "Test User"
        assert profile.email == "test@example.com"
        assert profile.preferences["theme"] == "dark"


class TestUserBehavior:
    """Test UserBehavior model."""

    def test_create_behavior(self) -> None:
        """Test creating user behavior."""
        behavior = UserBehavior()
        assert behavior.active_hours == []
        assert behavior.common_tasks == []
        assert behavior.communication_style == "neutral"

    def test_behavior_with_data(self) -> None:
        """Test creating behavior with data."""
        behavior = UserBehavior(
            active_hours=[9, 10, 11, 14, 15, 16],
            common_tasks=["code review", "documentation"],
            preferred_tools=["vscode", "github"],
            communication_style="concise",
        )
        assert len(behavior.active_hours) == 6
        assert "code review" in behavior.common_tasks
        assert behavior.communication_style == "concise"


class TestUserModel:
    """Test UserModel functionality."""

    @pytest.fixture
    def user_model(self, mock_memory_store: Any) -> UserModel:
        """Create user model instance."""
        return UserModel(user_id="test_user", memory_store=mock_memory_store)

    @pytest.mark.asyncio
    async def test_load_new_user(self, user_model: UserModel) -> None:
        """Test loading a new user."""
        await user_model.load()
        assert user_model.profile is not None
        assert user_model.profile.user_id == "test_user"
        assert user_model.behavior is not None

    @pytest.mark.asyncio
    async def test_update_preferences(self, user_model: UserModel) -> None:
        """Test updating user preferences."""
        await user_model.load()
        await user_model.update_preferences({"theme": "dark", "language": "en"})

        assert user_model.profile is not None
        assert user_model.profile.preferences["theme"] == "dark"
        assert user_model.profile.preferences["language"] == "en"

    @pytest.mark.asyncio
    async def test_record_activity(self, user_model: UserModel) -> None:
        """Test recording user activity."""
        await user_model.load()
        await user_model.record_activity("code review")

        assert user_model.behavior is not None
        assert "code review" in user_model.behavior.common_tasks

    @pytest.mark.asyncio
    async def test_record_activity_updates_hours(self, user_model: UserModel) -> None:
        """Test that recording activity updates active hours."""
        await user_model.load()
        current_hour = datetime.now().hour
        await user_model.record_activity("test activity")

        assert user_model.behavior is not None
        assert current_hour in user_model.behavior.active_hours

    @pytest.mark.asyncio
    async def test_get_context(self, user_model: UserModel) -> None:
        """Test getting user context."""
        await user_model.load()
        context = await user_model.get_context()

        assert "user_id" in context
        assert "profile" in context
        assert "behavior" in context
        assert "current_hour" in context
        assert "is_active_hour" in context

    @pytest.mark.asyncio
    async def test_get_personalization_hints(self, user_model: UserModel) -> None:
        """Test getting personalization hints."""
        await user_model.load()
        hints = await user_model.get_personalization_hints()

        assert "communication_style" in hints
        assert "preferred_tools" in hints
        assert "preferences" in hints
