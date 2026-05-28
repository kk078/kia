"""Task router for intelligent framework selection."""

from typing import Any

from brain_core.llm import LLMRouter


class TaskRouter:
    """Routes tasks to the best framework based on task type and complexity."""

    def __init__(self) -> None:
        """Initialize the task router."""
        self.llm = LLMRouter()

    def classify_task(self, task: str) -> dict[str, Any]:
        """Classify a task to determine the best framework.

        Args:
            task: Task description

        Returns:
            Classification dict with framework, complexity, and reasoning
        """
        task_lower = task.lower()

        # Simple heuristic-based classification
        if any(word in task_lower for word in ["plan", "strategy", "break down", "decompose"]):
            return {
                "framework": "langgraph",
                "complexity": "high",
                "reasoning": "Task requires planning and state management",
            }
        elif any(word in task_lower for word in ["research", "investigate", "analyze", "compare"]):
            return {
                "framework": "crewai",
                "complexity": "medium",
                "reasoning": "Task requires multi-agent research and synthesis",
            }
        elif any(word in task_lower for word in ["search", "find", "lookup", "scrape"]):
            return {
                "framework": "smolagents",
                "complexity": "low",
                "reasoning": "Task requires tool use for web/code research",
            }
        elif any(word in task_lower for word in ["quick", "simple", "fast", "basic"]):
            return {
                "framework": "agno",
                "complexity": "low",
                "reasoning": "Task is lightweight and requires minimal overhead",
            }
        elif any(word in task_lower for word in ["index", "retrieve", "search documents", "rag"]):
            return {
                "framework": "llamaindex",
                "complexity": "medium",
                "reasoning": "Task requires document indexing and retrieval",
            }
        else:
            # Default to LangGraph for complex tasks
            return {
                "framework": "langgraph",
                "complexity": "medium",
                "reasoning": "Default routing for general-purpose tasks",
            }

    async def classify_with_llm(self, task: str) -> dict[str, Any]:
        """Classify a task using LLM for more accurate routing.

        Args:
            task: Task description

        Returns:
            Classification dict with framework, complexity, and reasoning
        """
        prompt = f"""Classify the following task to determine the best AI framework to use.

Task: {task}

Available frameworks:
- langgraph: Complex multi-step planning with state management
- crewai: Role-based multi-agent collaboration
- smolagents: Tool-heavy research tasks
- agno: Fast, lightweight agents
- llamaindex: Document indexing and retrieval

Respond in JSON format:
{{
    "framework": "framework_name",
    "complexity": "low|medium|high",
    "reasoning": "brief explanation"
}}"""

        response = await self.llm.generate(prompt, task_type="planning")

        # Parse JSON response (simplified - in production use proper JSON parsing)
        try:
            import json

            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                classification: dict[str, Any] = json.loads(json_str)
                return classification
        except Exception:
            # Fallback to heuristic classification
            return self.classify_task(task)

        return self.classify_task(task)

    def get_framework_info(self, framework: str) -> dict[str, Any]:
        """Get information about a framework.

        Args:
            framework: Framework name

        Returns:
            Framework info dict
        """
        frameworks = {
            "langgraph": {
                "name": "LangGraph",
                "description": "Stateful, graph-based orchestration",
                "best_for": "Complex planning, hierarchical tasks",
                "module": "brain_orchestrator",
                "recommended_models": [
                    "ollama/llama3.1",
                    "ollama/qwen2.5",
                    "anthropic/claude-3-5-sonnet-20241022",
                ],
            },
            "crewai": {
                "name": "CrewAI",
                "description": "Role-based multi-agent crews",
                "best_for": "Research, synthesis, review workflows",
                "module": "brain_crews",
                "recommended_models": [
                    "ollama/llama3.1",
                    "ollama/mistral",
                    "anthropic/claude-3-5-sonnet-20241022",
                ],
            },
            "smolagents": {
                "name": "smolagents",
                "description": "Lightweight tool-use agents",
                "best_for": "Web scraping, code analysis",
                "module": "brain_researchers",
                "recommended_models": [
                    "ollama/codellama",
                    "ollama/deepseek-coder-v2",
                    "anthropic/claude-3-5-sonnet-20241022",
                ],
            },
            "agno": {
                "name": "Agno",
                "description": "Fast, minimal agents",
                "best_for": "Simple tasks, rapid prototyping",
                "module": "brain_researchers",
                "recommended_models": [
                    "ollama/phi3",
                    "ollama/gemma2",
                    "ollama/llama3.2",
                ],
            },
            "llamaindex": {
                "name": "LlamaIndex",
                "description": "Document indexing and RAG",
                "best_for": "Knowledge retrieval, Q&A",
                "module": "brain_knowledge",
                "recommended_models": [
                    "ollama/llama3.1",
                    "ollama/mistral",
                    "openai/gpt-4-turbo",
                ],
            },
        }
        return frameworks.get(framework, {})
