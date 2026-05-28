"""Synthesis crew for information integration."""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.llm import LLM

from brain_core.config import settings


class SynthesisCrew:
    """Crew for synthesizing information from multiple sources."""

    def __init__(self) -> None:
        """Initialize the synthesis crew."""
        self.llm = LLM(
            model="anthropic/claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )

    def create_analyst(self) -> Agent:
        """Create an analyst agent."""
        return Agent(
            role="Data Analyst",
            goal="Analyze and identify patterns across multiple information sources",
            backstory=(
                "You are an expert analyst who excels at finding "
                "connections and patterns across diverse information sources. "
                "You synthesize complex data into actionable insights."
            ),
            llm=self.llm,
            verbose=True,
        )

    def create_synthesizer(self) -> Agent:
        """Create a synthesizer agent."""
        return Agent(
            role="Knowledge Synthesizer",
            goal="Integrate diverse information into coherent, actionable knowledge",
            backstory=(
                "You are a master synthesizer who weaves together "
                "disparate pieces of information into a unified understanding. "
                "You excel at creating comprehensive overviews."
            ),
            llm=self.llm,
            verbose=True,
        )

    async def synthesize(self, sources: list[dict[str, Any]]) -> dict[str, Any]:
        """Synthesize information from multiple sources.

        Args:
            sources: List of source dicts with 'title' and 'content'

        Returns:
            Synthesis results dict
        """
        analyst = self.create_analyst()
        synthesizer = self.create_synthesizer()

        # Format sources for analysis
        sources_text = "\n\n".join(
            [f"Source: {s.get('title', 'Unknown')}\n{s.get('content', '')}" for s in sources]
        )

        analysis_task = Task(
            description=f"""Analyze the following sources and identify key patterns,
            connections, and insights:

            {sources_text}

            Focus on:
            - Common themes
            - Contradictions or conflicts
            - Gaps in information
            - Emerging patterns""",
            expected_output="Analysis of patterns and connections across sources",
            agent=analyst,
        )

        synthesis_task = Task(
            description="""Based on the analysis, create a comprehensive synthesis
            that integrates all sources into a coherent whole.

            Include:
            - Integrated overview
            - Key insights
            - Actionable recommendations
            - Areas for further investigation""",
            expected_output="Comprehensive synthesis of all sources",
            agent=synthesizer,
        )

        crew = Crew(
            agents=[analyst, synthesizer],
            tasks=[analysis_task, synthesis_task],
            verbose=True,
        )

        result = await crew.kickoff_async()

        return {
            "source_count": len(sources),
            "result": str(result),
        }
