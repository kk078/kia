"""DSPy reasoning over a local model (provider-free).

DSPy treats prompts as compiled, optimizable programs. This wraps a
ChainOfThought predictor against a local Ollama model and can be compiled
against the eval set for systematic quality gains. Opt-in (``dspy_enabled``)
and lazy-imported so the package isn't required unless used.

Install to use:  ``uv add dspy-ai`` (then it reaches Ollama via litellm).
"""

from __future__ import annotations

import os
from typing import Any

from brain_core.config import settings


class DSPyReasoner:
    """Chain-of-thought reasoning via DSPy + a local model."""

    def __init__(self, model: str | None = None) -> None:
        """Default model is ``ollama_chat/<default_oss_model>`` (fully local)."""
        self.model = model or settings.dspy_model or f"ollama_chat/{settings.default_oss_model}"
        os.environ.setdefault("OLLAMA_API_BASE", settings.ollama_base_url)
        self._predictor: Any = None

    def _ensure(self) -> Any:
        if self._predictor is None:
            import dspy

            lm = dspy.LM(self.model, api_base=settings.ollama_base_url)
            dspy.configure(lm=lm)
            self._predictor = dspy.ChainOfThought("question -> answer")
        return self._predictor

    def answer(self, question: str) -> str:
        """Answer a question with a DSPy ChainOfThought program."""
        predictor = self._ensure()
        result = predictor(question=question)
        text: str = getattr(result, "answer", str(result))
        return text
