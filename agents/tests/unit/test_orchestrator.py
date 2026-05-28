"""Unit tests for orchestrator."""

from brain_orchestrator.world_model import Belief, WorldModel


def test_world_model_update_belief() -> None:
    """Test updating a belief."""
    wm = WorldModel()
    wm.update_belief("user", "preference", "dark_mode", source="test")

    belief = wm.get_belief("user", "preference")
    assert belief is not None
    assert belief.entity == "user"
    assert belief.property == "preference"
    assert belief.value == "dark_mode"


def test_world_model_get_entity_beliefs() -> None:
    """Test getting all beliefs for an entity."""
    wm = WorldModel()
    wm.update_belief("user", "name", "Alice")
    wm.update_belief("user", "role", "developer")
    wm.update_belief("project", "status", "active")

    user_beliefs = wm.get_entity_beliefs("user")
    assert len(user_beliefs) == 2
    assert all(b.entity == "user" for b in user_beliefs)


def test_world_model_get_context() -> None:
    """Test getting world model context."""
    wm = WorldModel()
    wm.update_belief("test", "key", "value")

    context = wm.get_context()
    assert "beliefs" in context
    assert "history_count" in context
    assert context["history_count"] == 1


def test_belief_model() -> None:
    """Test Belief model."""
    belief = Belief(
        entity="test",
        property="key",
        value="value",
        confidence=0.95,
        source="unit_test",
    )
    assert belief.entity == "test"
    assert belief.confidence == 0.95
