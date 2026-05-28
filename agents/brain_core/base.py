"""Base agent protocol and types."""

from typing import Any, Protocol, runtime_checkable

from brain_core.types import AgentResponse, Context


@runtime_checkable
class BaseAgent(Protocol):
    """Protocol that all agents must implement."""

    async def run(self, task: str, context: Context) -> AgentResponse:
        """Execute a task and return a response."""
        ...

    async def reflect(self, response: AgentResponse) -> dict[str, Any]:
        """Reflect on a response for self-improvement."""
        ...
