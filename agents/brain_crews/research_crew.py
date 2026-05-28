"""Research crew for information gathering."""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.llm import LLM

from brain_core.config import settings


class ResearchCrew:
    """Crew for research and information gathering."""

    def __init__(self) -> None:
        """Initialize the research crew."""
        self.llm = LLM(
            model="anthropic/claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )

    def create_researcher(self) -> Agent:
        """Create a research agent."""
        return Agent(
            role="Senior Research Analyst",
            goal="Uncover cutting-edge developments and gather comprehensive information",
            backstory=(
                "You are a seasoned researcher with a knack for finding "
                "and synthesizing information from various sources. You excel at "
                "identifying key insights and trends."
            ),
            llm=self.llm,
            verbose=True,
        )

    def create_writer(self) -> Agent:
        """Create a writer agent."""
        return Agent(
            role="Technical Writer",
            goal="Craft clear, concise, and well-structured research reports",
            backstory=(
                "You are a skilled technical writer who transforms "
                "complex information into accessible, well-organized documents "
                "that highlight key findings."
            ),
            llm=self.llm,
            verbose=True,
        )

    async def research(self, topic: str, depth: int = 3) -> dict[str, Any]:
        """Conduct research on a topic.

        Args:
            topic: The topic to research
            depth: Research depth (1=quick, 2=moderate, 3=comprehensive)

        Returns:
            Research results dict
        """
        researcher = self.create_researcher()
        writer = self.create_writer()

        research_task = Task(
            description=f"""Research the following topic thoroughly:
            {topic}

            Focus on:
            - Key facts and statistics
            - Recent developments
            - Expert opinions
            - Potential implications

            Depth level: {depth}/3""",
            expected_output="A comprehensive research summary with key findings",
            agent=researcher,
        )

        writing_task = Task(
            description=f"""Based on the research findings, create a well-structured
            report on: {topic}

            Include:
            - Executive summary
            - Key findings
            - Analysis
            - Conclusions""",
            expected_output="A polished research report",
            agent=writer,
        )

        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, writing_task],
            verbose=True,
        )

        result = await crew.kickoff_async()

        return {
            "topic": topic,
            "depth": depth,
            "result": str(result),
        }
