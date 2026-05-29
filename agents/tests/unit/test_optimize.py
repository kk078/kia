"""Tests for the DSPy reasoner config (no dspy / no model required)."""

from brain_core.config import settings
from brain_core.optimize import DSPyReasoner


def test_default_model_is_local_chat() -> None:
    r = DSPyReasoner()
    assert r.model.startswith("ollama_chat/")
    assert settings.default_oss_model in r.model


def test_explicit_model_override() -> None:
    r = DSPyReasoner(model="ollama_chat/qwen2.5:3b")
    assert r.model == "ollama_chat/qwen2.5:3b"
    assert r._predictor is None  # lazy: nothing constructed until used
