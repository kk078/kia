"""Tests for evaluation harness."""

import pytest

from evals import (
    EvalSuite,
    LatencyEvaluator,
    RAGAccuracyEvaluator,
    TaskCompletionEvaluator,
)
from evals.base import EvalResult


class TestEvalResult:
    """Test EvalResult dataclass."""

    def test_eval_result_creation(self) -> None:
        """Test creating an eval result."""
        result = EvalResult(
            name="test_eval",
            passed=True,
            score=0.95,
            details={"key": "value"},
            duration=1.5,
        )

        assert result.name == "test_eval"
        assert result.passed is True
        assert result.score == 0.95
        assert result.details["key"] == "value"
        assert result.duration == 1.5

    def test_eval_result_to_dict(self) -> None:
        """Test converting eval result to dict."""
        result = EvalResult(
            name="test_eval",
            passed=True,
            score=0.95,
        )

        result_dict = result.to_dict()
        assert result_dict["name"] == "test_eval"
        assert result_dict["passed"] is True
        assert result_dict["score"] == 0.95


class TestTaskCompletionEvaluator:
    """Test TaskCompletionEvaluator."""

    @pytest.fixture
    def evaluator(self) -> TaskCompletionEvaluator:
        """Create evaluator instance."""
        return TaskCompletionEvaluator()

    @pytest.mark.asyncio
    async def test_evaluate_with_good_response(self, evaluator: TaskCompletionEvaluator) -> None:
        """Test evaluation with good response."""
        result = await evaluator.run(
            task="What is the capital of France?",
            response="The capital of France is Paris, a beautiful city known for the Eiffel Tower.",
            expected_keywords=["Paris", "France", "capital"],
            min_length=50,
        )

        assert result.passed is True
        assert result.score > 0.7
        assert result.details["response_length"] > 50

    @pytest.mark.asyncio
    async def test_evaluate_with_short_response(self, evaluator: TaskCompletionEvaluator) -> None:
        """Test evaluation with short response."""
        result = await evaluator.run(
            task="What is the capital of France?",
            response="Paris",
            expected_keywords=["Paris", "France", "capital"],
            min_length=50,
        )

        assert result.score < 0.7

    @pytest.mark.asyncio
    async def test_evaluate_with_no_response(self, evaluator: TaskCompletionEvaluator) -> None:
        """Test evaluation with no response."""
        result = await evaluator.run(
            task="What is the capital of France?",
            response="",
        )

        assert result.passed is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_keyword_matching(self, evaluator: TaskCompletionEvaluator) -> None:
        """Test keyword matching."""
        result = await evaluator.run(
            task="Explain Python",
            response="Python is a programming language",
            expected_keywords=["Python", "programming", "language"],
        )

        assert result.details["keyword_score"] == 1.0
        assert len(result.details["found_keywords"]) == 3


class TestRAGAccuracyEvaluator:
    """Test RAGAccuracyEvaluator."""

    @pytest.fixture
    def evaluator(self) -> RAGAccuracyEvaluator:
        """Create evaluator instance."""
        return RAGAccuracyEvaluator()

    @pytest.mark.asyncio
    async def test_evaluate_with_accurate_answer(self, evaluator: RAGAccuracyEvaluator) -> None:
        """Test evaluation with accurate answer."""
        result = await evaluator.run(
            question="What is machine learning?",
            expected_answer="Machine learning is a subset of AI that learns from data",
            retrieved_context=["Machine learning is a subset of artificial intelligence"],
            generated_answer="Machine learning is a subset of AI that learns patterns from data",
        )

        assert result.passed is True
        assert result.score > 0.6

    @pytest.mark.asyncio
    async def test_evaluate_with_no_answer(self, evaluator: RAGAccuracyEvaluator) -> None:
        """Test evaluation with no generated answer."""
        result = await evaluator.run(
            question="What is machine learning?",
            expected_answer="Machine learning is a subset of AI",
            generated_answer=None,
        )

        assert result.passed is False
        assert result.score == 0.0


class TestLatencyEvaluator:
    """Test LatencyEvaluator."""

    @pytest.fixture
    def evaluator(self) -> LatencyEvaluator:
        """Create evaluator instance."""
        return LatencyEvaluator()

    @pytest.mark.asyncio
    async def test_evaluate_fast_operation(self, evaluator: LatencyEvaluator) -> None:
        """Test evaluation of fast operation."""
        import asyncio

        async def fast_operation() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await evaluator.run(
            operation=fast_operation,
            max_latency=1.0,
            num_runs=3,
        )

        assert result.passed is True
        assert result.score > 0.0
        assert result.details["avg_latency"] < 1.0

    @pytest.mark.asyncio
    async def test_evaluate_slow_operation(self, evaluator: LatencyEvaluator) -> None:
        """Test evaluation of slow operation."""
        import asyncio

        async def slow_operation() -> str:
            await asyncio.sleep(0.5)
            return "done"

        result = await evaluator.run(
            operation=slow_operation,
            max_latency=0.1,
            num_runs=2,
        )

        assert result.passed is False
        assert result.details["avg_latency"] > 0.1


class TestEvalSuite:
    """Test EvalSuite."""

    @pytest.fixture
    def suite(self) -> EvalSuite:
        """Create eval suite."""
        suite = EvalSuite(name="test_suite")
        suite.add_evaluator(TaskCompletionEvaluator())
        suite.add_evaluator(RAGAccuracyEvaluator())
        return suite

    @pytest.mark.asyncio
    async def test_run_all_evaluators(self, suite: EvalSuite) -> None:
        """Test running all evaluators."""
        await suite.evaluators[0].run(
            task="Test task",
            response="This is a test response with enough length to pass the evaluation criteria.",
            expected_keywords=["test", "response"],
        )

        await suite.evaluators[1].run(
            question="Test question",
            expected_answer="Test answer",
            generated_answer="Test answer with context",
        )

        summary = suite.get_summary()
        assert summary["suite_name"] == "test_suite"
        assert summary["total_runs"] == 2
        assert len(summary["evaluators"]) == 2

    def test_clear_all(self, suite: EvalSuite) -> None:
        """Test clearing all evaluator results."""
        suite.evaluators[0].results.append(EvalResult(name="test", passed=True, score=1.0))
        suite.clear_all()

        assert len(suite.evaluators[0].results) == 0
