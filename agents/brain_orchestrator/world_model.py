"""World model for belief state tracking."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Belief(BaseModel):
    """A belief about the world."""

    entity: str
    property: str
    value: Any
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = ""


class WorldModel:
    """Maintains a belief state about the world."""

    def __init__(self) -> None:
        """Initialize the world model."""
        self.beliefs: dict[str, Belief] = {}
        self.history: list[dict[str, Any]] = []

    def update_belief(self, entity: str, property: str, value: Any, source: str = "") -> None:
        """Update a belief about an entity."""
        key = f"{entity}:{property}"
        self.beliefs[key] = Belief(
            entity=entity,
            property=property,
            value=value,
            source=source,
        )
        self.history.append(
            {
                "action": "update",
                "entity": entity,
                "property": property,
                "value": value,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def get_belief(self, entity: str, property: str) -> Belief | None:
        """Get a belief about an entity."""
        key = f"{entity}:{property}"
        return self.beliefs.get(key)

    def get_entity_beliefs(self, entity: str) -> list[Belief]:
        """Get all beliefs about an entity."""
        return [b for b in self.beliefs.values() if b.entity == entity]

    def get_context(self) -> dict[str, Any]:
        """Get the current world state as context."""
        return {
            "beliefs": {k: v.model_dump() for k, v in self.beliefs.items()},
            "history_count": len(self.history),
        }
