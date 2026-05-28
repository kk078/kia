"""Code researcher using Agno."""

from typing import Any

from agno.agent import Agent
from agno.models.anthropic import Claude

from brain_core.config import settings


class CodeResearcher:
    """Code analysis and research agent using Agno."""

    def __init__(self) -> None:
        """Initialize the code researcher."""
        self.model = Claude(
            id="claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )

    async def analyze(self, code: str, question: str = "") -> dict[str, Any]:
        """Analyze code and answer questions.

        Args:
            code: The code to analyze
            question: Optional specific question about the code

        Returns:
            Analysis results dict
        """
        agent = Agent(
            model=self.model,
            markdown=True,
        )

        prompt = f"""Analyze the following code:

```
{code}
```

{f"Question: {question}" if question else "Provide a comprehensive analysis."}

Include:
- Code purpose and functionality
- Key components and their roles
- Potential issues or improvements
- Best practices assessment"""

        response = agent.run(prompt)

        return {
            "code_length": len(code),
            "question": question,
            "analysis": response.content if hasattr(response, "content") else str(response),
        }

    async def review(self, code: str) -> dict[str, Any]:
        """Review code for quality and best practices.

        Args:
            code: The code to review

        Returns:
            Review results dict
        """
        agent = Agent(
            model=self.model,
            markdown=True,
        )

        prompt = f"""Review the following code for quality, best practices, and potential issues:

```
{code}
```

Provide:
- Code quality score (1-10)
- Best practices adherence
- Security considerations
- Performance considerations
- Specific recommendations"""

        response = agent.run(prompt)

        return {
            "code_length": len(code),
            "review": response.content if hasattr(response, "content") else str(response),
        }
