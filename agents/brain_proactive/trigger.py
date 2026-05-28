"""Event trigger for proactive behavior."""

import asyncio
from collections.abc import Callable
from typing import Any


class EventTrigger:
    """Event-based trigger system."""

    def __init__(self) -> None:
        """Initialize the event trigger."""
        self.handlers: dict[str, list[Callable[..., Any]]] = {}
        self.history: list[dict[str, Any]] = []

    def on(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type string
            handler: Async callback function
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable[..., Any]) -> bool:
        """Remove a handler for an event type.

        Args:
            event_type: Event type string
            handler: Handler to remove

        Returns:
            True if removed, False if not found
        """
        if event_type in self.handlers:
            try:
                self.handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    async def emit(self, event_type: str, data: dict[str, Any] | None = None) -> int:
        """Emit an event and trigger all handlers.

        Args:
            event_type: Event type string
            data: Event data

        Returns:
            Number of handlers triggered
        """
        handlers = self.handlers.get(event_type, [])
        if not handlers:
            return 0

        # Record in history
        self.history.append(
            {
                "event_type": event_type,
                "data": data or {},
                "handler_count": len(handlers),
            }
        )

        # Trigger all handlers
        tasks = [handler(data or {}) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

        return len(handlers)

    def list_handlers(self) -> dict[str, int]:
        """List all registered handlers.

        Returns:
            Dict of event_type -> handler count
        """
        return {event_type: len(handlers) for event_type, handlers in self.handlers.items()}

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get event history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event history dicts
        """
        return self.history[-limit:]
