"""Integration tests for A2A protocol."""

import pytest

from brain_core.a2a import A2ABus, A2AMessage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a2a_message_creation() -> None:
    """Test A2A message creation."""
    msg = A2AMessage(
        sender="agent1",
        receiver="agent2",
        content="Test message",
    )
    assert msg.sender == "agent1"
    assert msg.receiver == "agent2"
    assert msg.content == "Test message"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a2a_message_serialization() -> None:
    """Test A2A message serialization."""
    msg = A2AMessage(
        sender="agent1",
        receiver="agent2",
        content="Test message",
        message_type="request",
        metadata={"key": "value"},
    )
    data = msg.to_dict()
    assert data["sender"] == "agent1"
    assert data["receiver"] == "agent2"

    restored = A2AMessage.from_dict(data)
    assert restored.sender == msg.sender
    assert restored.receiver == msg.receiver
    assert restored.content == msg.content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a2a_bus_connection() -> None:
    """Test A2A bus Redis connection."""
    bus = A2ABus()
    # Just test connection by pinging
    await bus.redis.ping()
    await bus.close()
