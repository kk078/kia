"""Unit tests for brain_core package."""

from datetime import datetime

from brain_core.config import Settings
from brain_core.types import AgentResponse, Context, Message


def test_message_creation() -> None:
    """Test Message model creation."""
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert isinstance(msg.timestamp, datetime)


def test_context_creation() -> None:
    """Test Context model creation."""
    ctx = Context(session_id="test-session", user_id="test-user")
    assert ctx.session_id == "test-session"
    assert ctx.user_id == "test-user"
    assert ctx.messages == []


def test_agent_response() -> None:
    """Test AgentResponse model."""
    response = AgentResponse(
        content="Test response",
        confidence=0.95,
        sources=["source1", "source2"],
    )
    assert response.content == "Test response"
    assert response.confidence == 0.95
    assert len(response.sources) == 2


def test_settings_defaults() -> None:
    """Test Settings default values."""
    settings = Settings()
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.weaviate_url == "http://localhost:8081"
    assert settings.environment == "development"
