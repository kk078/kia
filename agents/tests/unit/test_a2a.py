"""Unit tests for A2A protocol."""

from brain_core.a2a import A2AMessage


def test_a2a_message_creation() -> None:
    """Test A2A message creation."""
    msg = A2AMessage(
        sender="agent1",
        receiver="agent2",
        content="Hello",
    )
    assert msg.sender == "agent1"
    assert msg.receiver == "agent2"
    assert msg.content == "Hello"
    assert msg.message_type == "request"


def test_a2a_message_to_dict() -> None:
    """Test A2A message serialization."""
    msg = A2AMessage(
        sender="agent1",
        receiver="agent2",
        content="Test",
        metadata={"key": "value"},
    )
    data = msg.to_dict()
    assert data["sender"] == "agent1"
    assert data["receiver"] == "agent2"
    assert data["content"] == "Test"
    assert data["metadata"]["key"] == "value"


def test_a2a_message_from_dict() -> None:
    """Test A2A message deserialization."""
    data = {
        "id": "test-id",
        "sender": "agent1",
        "receiver": "agent2",
        "content": "Test",
        "message_type": "response",
        "metadata": {},
        "timestamp": "2026-01-01T00:00:00",
    }
    msg = A2AMessage.from_dict(data)
    assert msg.sender == "agent1"
    assert msg.message_type == "response"
