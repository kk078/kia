"""RAG accuracy evaluation."""

from typing import Any

from evals.base import BaseEvaluator, EvalResult


class RAGAccuracyEvaluator(BaseEvaluator):
    """Evaluates RAG retrieval and generation accuracy."""

    def __init__(self) -> None:
        """Initialize RAG accuracy evaluator."""
        super().__init__("rag_accuracy")

    async def evaluate(self, **kwargs: Any) -> EvalResult:
        """Evaluate RAG accuracy.

        Args:
            question: Question asked
            expected_answer: Expected answer
            retrieved_context: List of retrieved context chunks
            generated_answer: Generated answer from RAG
            **kwargs: Additional arguments

        Returns:
            Evaluation result
        """
        question = kwargs.get("question", "")
        expected_answer = kwargs.get("expected_answer", "")
        retrieved_context = kwargs.get("retrieved_context")
        generated_answer = kwargs.get("generated_answer")
        if not generated_answer:
            return EvalResult(
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": "No generated answer provided"},
            )

        # Check if expected answer keywords are in generated answer
        expected_words = set(expected_answer.lower().split())
        generated_words = set(generated_answer.lower().split())

        # Calculate overlap
        overlap = expected_words.intersection(generated_words)
        relevance_score = len(overlap) / len(expected_words) if expected_words else 0.0

        # Check context retrieval quality
        context_score = 1.0
        if retrieved_context is not None:
            # Check if expected answer appears in context
            context_text = " ".join(retrieved_context).lower()
            if expected_answer.lower() in context_text:
                context_score = 1.0
            else:
                # Partial match
                context_words = set(context_text.split())
                context_overlap = expected_words.intersection(context_words)
                context_score = (
                    len(context_overlap) / len(expected_words) if expected_words else 0.0
                )

        # Overall score
        score = (relevance_score * 0.6) + (context_score * 0.4)
        passed = score >= 0.6

        return EvalResult(
            name=self.name,
            passed=passed,
            score=score,
            details={
                "question": question,
                "relevance_score": relevance_score,
                "context_score": context_score,
                "context_chunks": len(retrieved_context) if retrieved_context else 0,
                "answer_length": len(generated_answer),
            },
        )
