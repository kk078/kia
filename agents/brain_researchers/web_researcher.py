"""Web researcher using smolagents."""

from typing import Any

from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel

from brain_core.config import settings


class WebResearcher:
    """Web research agent using smolagents."""

    def __init__(self) -> None:
        """Initialize the web researcher."""
        self.model = LiteLLMModel(
            model_id="anthropic/claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )
        self.tools = [DuckDuckGoSearchTool()]

    async def research(self, query: str, max_steps: int = 5) -> dict[str, Any]:
        """Research a query using web search.

        Args:
            query: The research query
            max_steps: Maximum research steps

        Returns:
            Research results dict
        """
        agent = CodeAgent(
            tools=self.tools,
            model=self.model,
            max_steps=max_steps,
        )

        result = agent.run(
            f"""Research the following query thoroughly:
            {query}

            Use web search to find relevant information.
            Provide a comprehensive summary with sources."""
        )

        return {
            "query": query,
            "result": str(result),
            "steps": max_steps,
        }
