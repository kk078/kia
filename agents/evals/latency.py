"""Latency evaluation."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from evals.base import BaseEvaluator, EvalResult


class LatencyEvaluator(BaseEvaluator):
    """Evaluates response latency and performance."""

    def __init__(self) -> None:
        """Initialize latency evaluator."""
        super().__init__("latency")

    async def evaluate(self, **kwargs: Any) -> EvalResult:
        """Evaluate operation latency.

        Args:
            operation: Async operation to evaluate
            operation_args: Positional arguments for operation
            operation_kwargs: Keyword arguments for operation
            max_latency: Maximum acceptable latency in seconds
            num_runs: Number of times to run the operation
            **kwargs: Additional arguments

        Returns:
            Evaluation result
        """
        operation: Callable[..., Awaitable[Any]] = kwargs["operation"]
        operation_args: tuple[Any, ...] = kwargs.get("operation_args", ())
        operation_kwargs: dict[str, Any] | None = kwargs.get("operation_kwargs")
        max_latency: float = kwargs.get("max_latency", 5.0)
        num_runs: int = kwargs.get("num_runs", 5)
        if operation_kwargs is None:
            operation_kwargs = {}

        latencies = []
        errors = []

        for i in range(num_runs):
            start_time = time.time()
            try:
                await operation(*operation_args, **operation_kwargs)
                latency = time.time() - start_time
                latencies.append(latency)
            except Exception as e:
                latency = time.time() - start_time
                latencies.append(latency)
                errors.append(str(e))

        if not latencies:
            return EvalResult(
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": "No successful runs"},
            )

        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency_actual = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        # Score based on average latency vs max acceptable
        score = max(0.0, 1.0 - (avg_latency / max_latency))
        passed = avg_latency <= max_latency and len(errors) == 0

        return EvalResult(
            name=self.name,
            passed=passed,
            score=score,
            details={
                "num_runs": num_runs,
                "successful_runs": len(latencies) - len(errors),
                "failed_runs": len(errors),
                "avg_latency": avg_latency,
                "min_latency": min_latency,
                "max_latency": max_latency_actual,
                "p95_latency": p95_latency,
                "errors": errors,
            },
        )
