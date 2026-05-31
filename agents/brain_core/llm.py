"""LLM provider abstraction using litellm."""

import os
import time
from typing import Any

import litellm

from brain_core.config import settings
from brain_core.metrics import track_llm_call
from brain_core.trace_context import get_trace_context
from brain_core.tracing import (
    llm_traced,
)


_DEEP_KEYWORDS = (
    "analyze", "analysis", "compare", "evaluate", "assess", "reason", "prove",
    "derive", "why", "trade-off", "tradeoff", "design", "architect", "debug",
    "root cause", "step by step", "step-by-step", "strategy", "pros and cons",
    "explain how", "explain why", "implications", "optimi", "diagnose",
    "critique", "justify", "what if", "plan ",
)


def needs_deep_reasoning(prompt: str, task_type: str = "") -> bool:
    """Heuristic: should KIA spend extra passes verifying this answer?

    True for reasoning/analysis-heavy prompts (keywords, long multi-part questions,
    or planning/synthesis task types); False for simple lookups and short queries.
    """
    p = (prompt or "").lower()
    if task_type in ("planning", "synthesis"):
        return True
    if any(k in p for k in _DEEP_KEYWORDS):
        return True
    # Long or multi-question prompts tend to need more careful answers.
    if len(p) > 600 or p.count("?") >= 3:
        return True
    return False


class LLMRouter:
    """Routes LLM calls to appropriate providers via litellm."""

    def __init__(self) -> None:
        """Initialize the LLM router."""
        self._setup_providers()

    def _setup_providers(self) -> None:
        """Configure API keys and base URLs for providers."""
        # Commercial providers
        if settings.anthropic_api_key:
            litellm.anthropic_key = settings.anthropic_api_key
        if settings.openai_api_key:
            litellm.openai_key = settings.openai_api_key
        if settings.google_api_key:
            litellm.google_key = settings.google_api_key
        if settings.mistral_api_key:
            litellm.mistral_key = settings.mistral_api_key

        # Open-source providers - configure as OpenAI-compatible endpoints
        # litellm uses api_base for custom OpenAI-compatible servers
        self._oss_providers = {
            "ollama": {
                "base_url": settings.ollama_base_url,
                "model": settings.ollama_model,
                "prefix": "ollama",
            },
            "llamacpp": {
                "base_url": f"{settings.llamacpp_base_url}/v1",
                "model": settings.llamacpp_model,
                "prefix": "openai",
            },
            "vllm": {
                "base_url": f"{settings.vllm_base_url}/v1",
                "model": settings.vllm_model,
                "prefix": "openai",
            },
            "localai": {
                "base_url": f"{settings.localai_base_url}/v1",
                "model": settings.localai_model,
                "prefix": "openai",
            },
            "lmstudio": {
                "base_url": f"{settings.lmstudio_base_url}/v1",
                "model": settings.lmstudio_model,
                "prefix": "openai",
            },
            "gpt4all": {
                "base_url": f"{settings.gpt4all_base_url}/v1",
                "model": settings.gpt4all_model,
                "prefix": "openai",
            },
            "bitnet": {
                "base_url": f"{settings.bitnet_base_url}/v1",
                "model": settings.bitnet_model,
                "prefix": "openai",
            },
        }

        self._setup_langfuse()

    def _setup_langfuse(self) -> None:
        """Enable litellm's native Langfuse callback for automatic LLM tracing.

        Best practice for litellm apps: a single global callback captures model,
        token usage, cost, latency, and input/output as Langfuse generations for
        every litellm call across the app (router, crews, RAG). No-op if Langfuse
        credentials are not configured.
        """
        if not settings.litellm_langfuse_callback:
            return
        if not (settings.langfuse_public_key and settings.langfuse_secret_key):
            return
        # litellm's Langfuse logger reads these env vars (host name is LANGFUSE_HOST)
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_url)
        for cb_name in ("success_callback", "failure_callback"):
            cb = list(getattr(litellm, cb_name, None) or [])
            if "langfuse" not in cb:
                cb.append("langfuse")
            setattr(litellm, cb_name, cb)

    @llm_traced(name="llm_complete")
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """Generate a completion using the specified model.

        Args:
            model: Model string in format "provider/model" (e.g., "anthropic/claude-3-5-sonnet")
            messages: List of message dicts with "role" and "content"
            **kwargs: Additional arguments passed to litellm

        Returns:
            litellm response object
        """
        start_time = time.time()

        # Check if this is an open-source provider and set api_base
        oss_config = self._get_oss_config(model)
        if oss_config:
            kwargs["api_base"] = oss_config["api_base"]
            if "api_key" not in kwargs:
                kwargs["api_key"] = "sk-dummy"
            # Keep the local model loaded between requests (avoids cold-start reload).
            if model.startswith("ollama") and "keep_alive" not in kwargs:
                kwargs["keep_alive"] = settings.ollama_keep_alive

        # Langfuse generation metadata (litellm forwards this to the Langfuse callback).
        # Callers may pass metadata={"session_id": ..., "trace_user_id": ..., "tags": [...]}.
        lf_meta: dict[str, Any] = {
            "generation_name": "llm_complete",
            "tags": [f"env:{settings.environment}"],
        }
        lf_meta.update(get_trace_context())  # session_id + trace_user_id (request-scoped)
        caller_meta = kwargs.pop("metadata", None)
        if isinstance(caller_meta, dict):
            lf_meta.update(caller_meta)
        kwargs["metadata"] = lf_meta

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            **kwargs,
        )

        # Track metrics
        duration = time.time() - start_time
        usage = response.usage if hasattr(response, "usage") else None

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Estimate cost if not provided
        cost = self._estimate_cost(model, input_tokens, output_tokens)

        track_llm_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration=duration,
            cost=cost,
        )

        return response

    def _get_oss_config(self, model: str) -> dict[str, str] | None:
        """Get OpenAI-compatible API config for open-source providers.

        Args:
            model: Model string in format "provider/model"

        Returns:
            Dict with api_base or None if not an OSS provider
        """
        provider = model.split("/")[0] if "/" in model else ""
        oss_provider = self._oss_providers.get(provider)
        if oss_provider:
            return {"api_base": oss_provider["base_url"]}
        return None

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost of an LLM call.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of 2024)
        pricing = {
            # Commercial providers
            "anthropic/claude-3-5-sonnet-20241022": {
                "input": 3.0,
                "output": 15.0,
            },
            "anthropic/claude-3-haiku-20240307": {
                "input": 0.25,
                "output": 1.25,
            },
            "openai/gpt-4-turbo": {
                "input": 10.0,
                "output": 30.0,
            },
            "openai/gpt-3.5-turbo": {
                "input": 0.5,
                "output": 1.5,
            },
            # Open-source providers (all free - self-hosted)
            "ollama/llama3.1": {"input": 0.0, "output": 0.0},
            "ollama/llama3.2": {"input": 0.0, "output": 0.0},
            "ollama/mistral": {"input": 0.0, "output": 0.0},
            "ollama/codellama": {"input": 0.0, "output": 0.0},
            "ollama/phi3": {"input": 0.0, "output": 0.0},
            "ollama/gemma2": {"input": 0.0, "output": 0.0},
            "ollama/qwen2.5": {"input": 0.0, "output": 0.0},
            "ollama/deepseek-coder-v2": {"input": 0.0, "output": 0.0},
            "llamacpp/local-model": {"input": 0.0, "output": 0.0},
            "vllm/meta-llama/Llama-3.1-8B-Instruct": {"input": 0.0, "output": 0.0},
            "vllm/meta-llama/Llama-3.1-70B-Instruct": {"input": 0.0, "output": 0.0},
            "localai/gpt-4": {"input": 0.0, "output": 0.0},
            "lmstudio/local-model": {"input": 0.0, "output": 0.0},
            "gpt4all/mistral-7b-instruct": {"input": 0.0, "output": 0.0},
            "bitnet/bitnet-model": {"input": 0.0, "output": 0.0},
        }

        model_pricing = pricing.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]

        return input_cost + output_cost

    def route(self, task_type: str) -> str:
        """Route a task to the appropriate model.

        Args:
            task_type: Type of task (planning, research, synthesis, simple, fast)

        Returns:
            Model string for the task
        """
        default_oss = f"{settings.default_oss_provider}/{settings.default_oss_model}"
        complex_tasks = {"planning", "research", "synthesis", "code"}

        # Prefer a configured commercial provider (better quality); fall back to OSS.
        if settings.anthropic_api_key:
            strong, fast = "anthropic/claude-sonnet-4-6", "anthropic/claude-haiku-4-5-20251001"
        elif settings.openai_api_key:
            strong, fast = "openai/gpt-4-turbo", "openai/gpt-3.5-turbo"
        else:
            strong = fast = default_oss

        return strong if task_type in complex_tasks else fast

    def get_available_providers(self) -> dict[str, dict[str, str]]:
        """Get list of configured LLM providers.

        Returns:
            Dict of provider name to config info
        """
        providers: dict[str, dict[str, str]] = {}

        # Commercial providers
        if settings.anthropic_api_key:
            providers["anthropic"] = {"type": "commercial", "status": "configured"}
        if settings.openai_api_key:
            providers["openai"] = {"type": "commercial", "status": "configured"}
        if settings.google_api_key:
            providers["google"] = {"type": "commercial", "status": "configured"}
        if settings.mistral_api_key:
            providers["mistral"] = {"type": "commercial", "status": "configured"}

        # Open-source providers (always available if running)
        for name, config in self._oss_providers.items():
            providers[name] = {
                "type": "open-source",
                "base_url": config["base_url"],
                "default_model": config["model"],
                "cost": "free",
            }

        return providers

    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get information about a specific model.

        Args:
            model: Model string in format "provider/model"

        Returns:
            Dict with model information
        """
        provider = model.split("/")[0] if "/" in model else "unknown"
        model_name = model.split("/", 1)[1] if "/" in model else model

        is_oss = provider in self._oss_providers
        is_free = is_oss or model in [
            "ollama/llama3.1",
            "ollama/llama3.2",
            "ollama/mistral",
        ]

        return {
            "provider": provider,
            "model": model_name,
            "type": "open-source" if is_oss else "commercial",
            "cost": "free" if is_free else "paid",
            "local": is_oss,
        }

    @llm_traced(name="llm_generate")
    async def generate(
        self,
        prompt: str,
        task_type: str = "simple",
        model: str | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response for a prompt.

        Args:
            prompt: The prompt to generate from
            task_type: Type of task for routing
            model: Optional specific model to use
            system: Optional system prompt (e.g. the KIA persona) prepended to messages
            **kwargs: Additional arguments

        Returns:
            Generated text response
        """
        selected_model = model or self.route(task_type)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.complete(selected_model, messages, **kwargs)
        content: str = response.choices[0].message.content
        return content

    async def generate_verified(
        self,
        prompt: str,
        task_type: str = "research",
        model: str | None = None,
        samples: int | None = None,
        system: str | None = None,
        force: bool = False,
        **kwargs: Any,
    ) -> str:
        """Generate with self-consistency: sample N candidates, then judge/merge.

        Trades extra (local, free) inference for accuracy. No-op unless verification
        is enabled globally OR ``force=True`` (e.g. auto-escalated for a reasoning-heavy
        prompt), in which case it behaves like generate().
        """
        n = samples if samples is not None else settings.verify_samples
        if (not settings.verify_enabled and not force) or n <= 1:
            return await self.generate(prompt, task_type, model, system=system, **kwargs)

        candidates: list[str] = []
        for _ in range(n):
            candidates.append(
                await self.generate(prompt, task_type, model, system=system, **kwargs)
            )

        joined = "\n\n".join(f"Candidate {i + 1}:\n{c}" for i, c in enumerate(candidates))
        judge_prompt = (
            "You are a strict verifier. Several candidate answers to the SAME task are below. "
            "Cross-check them, discard anything unsupported or self-contradictory, prefer the "
            "consensus where they disagree, and produce the single most accurate and complete "
            "answer.\n\n"
            f"Task:\n{prompt}\n\n{joined}\n\nFinal verified answer:"
        )
        return await self.generate(judge_prompt, task_type="synthesis", model=model, system=system)
