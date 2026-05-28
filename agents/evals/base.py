"""Base evaluation framework."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """Result of a single evaluation."""

    name: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "duration": self.duration,
            "error": self.error,
        }


class BaseEvaluator(ABC):
    """Base class for all evaluators."""

    def __init__(self, name: str) -> None:
        """Initialize evaluator.

        Args:
            name: Name of the evaluator
        """
        self.name = name
        self.results: list[EvalResult] = []

    @abstractmethod
    async def evaluate(self, **kwargs: Any) -> EvalResult:
        """Run the evaluation.

        Args:
            **kwargs: Evaluation-specific arguments

        Returns:
            Evaluation result
        """
        pass

    async def run(self, **kwargs: Any) -> EvalResult:
        """Run the evaluation with timing.

        Args:
            **kwargs: Evaluation-specific arguments

        Returns:
            Evaluation result with timing
        """
        start_time = time.time()
        try:
            result = await self.evaluate(**kwargs)
            result.duration = time.time() - start_time
            self.results.append(result)
            return result
        except Exception as e:
            duration = time.time() - start_time
            result = EvalResult(
                name=self.name,
                passed=False,
                score=0.0,
                error=str(e),
                duration=duration,
            )
            self.results.append(result)
            return result

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all evaluation runs.

        Returns:
            Summary statistics
        """
        if not self.results:
            return {
                "name": self.name,
                "total_runs": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "avg_score": 0.0,
                "avg_duration": 0.0,
            }

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        return {
            "name": self.name,
            "total_runs": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "avg_score": sum(r.score for r in self.results) / total,
            "avg_duration": sum(r.duration for r in self.results) / total,
        }

    def clear(self) -> None:
        """Clear all results."""
        self.results.clear()


class EvalSuite:
    """Collection of evaluators to run together."""

    def __init__(self, name: str) -> None:
        """Initialize evaluation suite.

        Args:
            name: Name of the suite
        """
        self.name = name
        self.evaluators: list[BaseEvaluator] = []

    def add_evaluator(self, evaluator: BaseEvaluator) -> None:
        """Add an evaluator to the suite.

        Args:
            evaluator: Evaluator to add
        """
        self.evaluators.append(evaluator)

    async def run_all(self, **kwargs: Any) -> list[EvalResult]:
        """Run all evaluators in the suite.

        Args:
            **kwargs: Arguments passed to all evaluators

        Returns:
            List of evaluation results
        """
        results = []
        for evaluator in self.evaluators:
            result = await evaluator.run(**kwargs)
            results.append(result)
        return results

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all evaluators.

        Returns:
            Suite summary
        """
        summaries = [e.get_summary() for e in self.evaluators]

        total_runs = sum(s["total_runs"] for s in summaries)
        total_passed = sum(s["passed"] for s in summaries)

        return {
            "suite_name": self.name,
            "evaluators": summaries,
            "total_runs": total_runs,
            "total_passed": total_passed,
            "overall_pass_rate": total_passed / total_runs if total_runs > 0 else 0.0,
        }

    def clear_all(self) -> None:
        """Clear all evaluator results."""
        for evaluator in self.evaluators:
            evaluator.clear()
