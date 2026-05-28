"""Agent-to-Agent communication protocol."""

import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from brain_core.config import settings
from brain_core.types import AgentResponse


class A2AMessage:
    """Message for agent-to-agent communication."""

    def __init__(
        self,
        sender: str,
        receiver: str,
        content: str,
        message_type: str = "request",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an A2A message."""
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.id = f"{sender}:{receiver}:{self.timestamp.isoformat()}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "message_type": self.message_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AMessage":
        """Create from dict."""
        msg = cls(
            sender=data["sender"],
            receiver=data["receiver"],
            content=data["content"],
            message_type=data.get("message_type", "request"),
            metadata=data.get("metadata", {}),
        )
        msg.timestamp = datetime.fromisoformat(data["timestamp"])
        msg.id = data["id"]
        return msg


class A2ABus:
    """Agent-to-Agent communication bus using Redis pub/sub."""

    def __init__(self) -> None:
        """Initialize the A2A bus."""
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.handlers: dict[str, Callable[[A2AMessage], Awaitable[None]]] = {}

    def _channel_name(self, agent_id: str) -> str:
        """Generate channel name for an agent."""
        return f"brain:agent:{agent_id}"

    async def publish(self, message: A2AMessage) -> None:
        """Publish a message to an agent."""
        channel = self._channel_name(message.receiver)
        await self.redis.publish(channel, json.dumps(message.to_dict()))

    async def subscribe(
        self, agent_id: str, handler: Callable[[A2AMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to messages for an agent."""
        self.handlers[agent_id] = handler
        channel = self._channel_name(agent_id)

        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                a2a_msg = A2AMessage.from_dict(data)
                await handler(a2a_msg)

    async def request(
        self,
        sender: str,
        receiver: str,
        task: str,
        timeout: float = 30.0,
    ) -> AgentResponse | None:
        """Send a request and wait for response.

        Args:
            sender: Sender agent ID
            receiver: Receiver agent ID
            task: Task description
            timeout: Response timeout in seconds

        Returns:
            AgentResponse or None if timeout
        """
        request_msg = A2AMessage(
            sender=sender,
            receiver=receiver,
            content=task,
            message_type="request",
        )

        response_channel = f"brain:response:{request_msg.id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(response_channel)

        await self.publish(request_msg)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    return AgentResponse(
                        content=data["content"],
                        confidence=data.get("confidence", 1.0),
                        metadata=data.get("metadata", {}),
                    )
        except Exception:
            return None
        finally:
            await pubsub.unsubscribe(response_channel)
            await pubsub.close()

        return None

    async def respond(self, request_id: str, response: AgentResponse) -> None:
        """Send a response to a request."""
        response_channel = f"brain:response:{request_id}"
        await self.redis.publish(
            response_channel,
            json.dumps(
                {
                    "content": response.content,
                    "confidence": response.confidence,
                    "metadata": response.metadata,
                }
            ),
        )

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.redis.aclose()
