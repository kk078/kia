"""Task completion evaluation."""

from typing import Any

from evals.base import BaseEvaluator, EvalResult


class TaskCompletionEvaluator(BaseEvaluator):
    """Evaluates whether agents complete tasks successfully."""

    def __init__(self) -> None:
        """Initialize task completion evaluator."""
        super().__init__("task_completion")

    async def evaluate(self, **kwargs: Any) -> EvalResult:
        """Evaluate task completion.

        Args:
            task: Task description
            expected_keywords: Keywords that should appear in response
            min_length: Minimum response length
            **kwargs: Additional arguments (should include 'response')

        Returns:
            Evaluation result
        """
        task = kwargs.get("task", "")
        expected_keywords = kwargs.get("expected_keywords")
        min_length = kwargs.get("min_length", 50)
        response = kwargs.get("response", "")

        if not response:
            return EvalResult(
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": "No response provided"},
            )

        # Check response length
        length_score = min(len(response) / min_length, 1.0)

        # Check for expected keywords
        keyword_score = 1.0
        if expected_keywords:
            found_keywords = [kw for kw in expected_keywords if kw.lower() in response.lower()]
            keyword_score = len(found_keywords) / len(expected_keywords)

        # Overall score (weighted average)
        score = (length_score * 0.3) + (keyword_score * 0.7)
        passed = score >= 0.7

        return EvalResult(
            name=self.name,
            passed=passed,
            score=score,
            details={
                "task": task,
                "response_length": len(response),
                "length_score": length_score,
                "keyword_score": keyword_score,
                "found_keywords": found_keywords if expected_keywords else [],
            },
        )
