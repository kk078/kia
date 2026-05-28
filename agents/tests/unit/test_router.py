"""Tests for task router."""

import pytest

from brain_core.router import TaskRouter


class TestTaskRouter:
    """Test TaskRouter functionality."""

    @pytest.fixture
    def router(self) -> TaskRouter:
        """Create router instance."""
        return TaskRouter()

    def test_classify_planning_task(self, router: TaskRouter) -> None:
        """Test classification of planning tasks."""
        result = router.classify_task("Plan a strategy for project management")
        assert result["framework"] == "langgraph"
        assert result["complexity"] == "high"

    def test_classify_research_task(self, router: TaskRouter) -> None:
        """Test classification of research tasks."""
        result = router.classify_task("Research the latest AI developments")
        assert result["framework"] == "crewai"
        assert result["complexity"] == "medium"

    def test_classify_search_task(self, router: TaskRouter) -> None:
        """Test classification of search tasks."""
        result = router.classify_task("Search for information about Python")
        assert result["framework"] == "smolagents"
        assert result["complexity"] == "low"

    def test_classify_simple_task(self, router: TaskRouter) -> None:
        """Test classification of simple tasks."""
        result = router.classify_task("Quick answer to a simple question")
        assert result["framework"] == "agno"
        assert result["complexity"] == "low"

    def test_classify_rag_task(self, router: TaskRouter) -> None:
        """Test classification of RAG tasks."""
        result = router.classify_task("Index and retrieve documents")
        assert result["framework"] == "llamaindex"
        assert result["complexity"] == "medium"

    def test_classify_unknown_task(self, router: TaskRouter) -> None:
        """Test classification of unknown tasks defaults to langgraph."""
        result = router.classify_task("Some random task")
        assert result["framework"] == "langgraph"
        assert result["complexity"] == "medium"

    def test_get_framework_info(self, router: TaskRouter) -> None:
        """Test getting framework information."""
        info = router.get_framework_info("langgraph")
        assert info["name"] == "LangGraph"
        assert "description" in info
        assert "best_for" in info

    def test_get_framework_info_unknown(self, router: TaskRouter) -> None:
        """Test getting info for unknown framework."""
        info = router.get_framework_info("unknown")
        assert info == {}
