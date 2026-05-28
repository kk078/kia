"""Benchmark scenarios for evaluation."""

from dataclasses import dataclass
from typing import Any


@dataclass
class BenchmarkScenario:
    """A benchmark scenario for evaluation."""

    name: str
    description: str
    task: str
    expected_keywords: list[str]
    expected_answer: str
    context: list[str] | None = None
    metadata: dict[str, Any] | None = None


# Pre-defined benchmark scenarios
BENCHMARK_SCENARIOS = [
    BenchmarkScenario(
        name="simple_qa",
        description="Simple question answering",
        task="What is the capital of France?",
        expected_keywords=["Paris", "France", "capital"],
        expected_answer="The capital of France is Paris.",
    ),
    BenchmarkScenario(
        name="code_explanation",
        description="Code explanation task",
        task=(
            "Explain what this Python function does: "
            "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
        ),
        expected_keywords=["factorial", "recursive", "function", "multiply"],
        expected_answer="This is a recursive function that calculates the factorial of a number.",
    ),
    BenchmarkScenario(
        name="summarization",
        description="Text summarization task",
        task="Summarize the key points of machine learning in 2 sentences.",
        expected_keywords=["machine learning", "algorithms", "data", "patterns"],
        expected_answer=(
            "Machine learning uses algorithms to find patterns in data. "
            "It enables systems to learn and improve from experience."
        ),
    ),
    BenchmarkScenario(
        name="planning_task",
        description="Complex planning task",
        task="Plan a 3-day trip to Tokyo including transportation, accommodation, and activities.",
        expected_keywords=["transportation", "accommodation", "activities", "day", "itinerary"],
        expected_answer=(
            "A comprehensive 3-day Tokyo itinerary with transportation, "
            "hotel, and daily activities."
        ),
    ),
    BenchmarkScenario(
        name="research_task",
        description="Research and synthesis task",
        task="Research the benefits of exercise and provide 3 key findings.",
        expected_keywords=["benefits", "exercise", "health", "findings"],
        expected_answer=(
            "Exercise provides numerous health benefits including improved "
            "cardiovascular health, mental wellbeing, and longevity."
        ),
    ),
]


def get_scenario(name: str) -> BenchmarkScenario | None:
    """Get a benchmark scenario by name.

    Args:
        name: Scenario name

    Returns:
        Benchmark scenario or None if not found
    """
    for scenario in BENCHMARK_SCENARIOS:
        if scenario.name == name:
            return scenario
    return None


def list_scenarios() -> list[str]:
    """List all available benchmark scenarios.

    Returns:
        List of scenario names
    """
    return [s.name for s in BENCHMARK_SCENARIOS]
