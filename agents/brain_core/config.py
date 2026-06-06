"""Application settings loaded from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # tolerate unrelated keys in .env (GATEWAY_PORT, OLLAMA_API_KEY, ...)
    )

    # Infrastructure
    redis_url: str = "redis://localhost:6379"
    weaviate_url: str = "http://localhost:8081"
    falkordb_url: str = "redis://localhost:6380"
    langfuse_url: str = "http://localhost:3000"

    # Commercial LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""

    # Open-Source LLM Providers (local/self-hosted)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    llamacpp_base_url: str = "http://localhost:8080"
    llamacpp_model: str = "local-model"
    vllm_base_url: str = "http://localhost:8000"
    vllm_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    localai_base_url: str = "http://localhost:8080"
    localai_model: str = "gpt-4"
    lmstudio_base_url: str = "http://localhost:1234"
    lmstudio_model: str = "local-model"
    gpt4all_base_url: str = "http://localhost:4891"
    gpt4all_model: str = "mistral-7b-instruct"
    bitnet_base_url: str = "http://localhost:8080"
    bitnet_model: str = "bitnet-model"

    # Default provider for open-source models
    default_oss_provider: str = "ollama"
    default_oss_model: str = "llama3.1"

    # n8n
    n8n_url: str = "http://localhost:5678"
    n8n_api_key: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    # litellm->Langfuse auto-tracing. OFF by default: a litellm/langfuse version
    # mismatch can raise on every call and break generation. App tracing is separate.
    litellm_langfuse_callback: bool = False

    # Security guard (prompt-injection defense on untrusted content)
    guard_enabled: bool = True
    guard_action: str = "flag"  # flag | redact | block
    guard_block_threshold: int = 80

    # GraphRAG (FalkorDB GraphRAG SDK) — knowledge-graph-augmented retrieval.
    # Provider-free by default: local Ollama for both generation and embeddings.
    graphrag_enabled: bool = False
    graphrag_graph_name: str = "brain_kg"
    graphrag_llm_model: str = ""  # empty -> derived from default_oss_provider/model
    graphrag_embed_model: str = "ollama/nomic-embed-text"

    # Local embedding model for LlamaIndex vector RAG (provider-free, via Ollama).
    embed_model: str = "nomic-embed-text"
    rag_top_k: int = 15  # retrieval window; wide enough for vector-only recall on the KB

    # Storage backends. Native (no Docker/WSL) deployment uses embedded stores.
    vector_backend: str = "weaviate"  # "weaviate" (server) | "chroma" (embedded, in-process)
    chroma_path: str = "/app/data/chroma"
    storage_backend: str = "redis"  # "redis" (server) | "sqlite" (embedded file)
    sqlite_path: str = "/app/data/kia.db"

    # Verification / self-consistency (sample N candidates + judge). Opt-in (N x cost).
    verify_enabled: bool = False  # global force-on; usually False (auto_verify decides)
    verify_samples: int = 3

    # Resilience: retry transient LLM provider failures (litellm native).
    llm_num_retries: int = 2

    # Caching layer (Redis response cache for RAG etc.).
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    # Circuit breaker for LLM calls.
    breaker_threshold: int = 5
    breaker_cooldown_seconds: float = 30.0
    auto_verify: bool = True  # KIA self-escalates to verification on reasoning-heavy prompts
    ollama_keep_alive: str = "30m"  # keep model loaded between requests (avoids cold start)

    # Training-data capture (Phase 3): log user-facing chats as fine-tuning pairs.
    training_capture_enabled: bool = True
    training_capture_path: str = "/app/data/kia_train.jsonl"

    # DSPy programmatic reasoning/optimization (local/provider-free). Opt-in + lazy.
    dspy_enabled: bool = False
    dspy_model: str = ""  # empty -> ollama_chat/<default_oss_model>

    # Host command execution (opt-in, confirmation-gated via the UI + host runner).
    exec_enabled: bool = False
    host_runner_url: str = ""  # e.g. http://host.docker.internal:8765
    host_runner_token: str = ""
    exec_timeout_seconds: int = 300

    # Autonomous build agent: default working directory the agent is jailed to.
    build_root: str = ""  # empty -> C:\dev on Windows, ~ elsewhere

    # Build agent escalation tier: switch to a stronger model when the default stalls
    # (the finish-gate keeps rejecting, or commands thrash). Empty disables escalation.
    build_escalate_model: str = ""  # e.g. "anthropic/claude-opus-4-6" (uses ANTHROPIC_API_KEY)
    build_escalate_after: int = 2   # finish-gate rejections before escalating

    # Connectors / MCP client layer.
    connectors_enabled: bool = False
    connectors_config: str = "/app/data/connectors.json"
    # Strong model for tool-planning (e.g. cloud); empty -> local default model.
    connector_planner_model: str = ""
    # If the planner model is a cloud/OpenAI-compatible endpoint, set its base URL + key.
    connector_planner_base_url: str = ""
    connector_planner_api_key: str = ""
    # Live retrieval in the plain chat box: let chat fetch URLs / search the web inline.
    chat_tools_enabled: bool = True
    # Max tool-calling steps for the chat live-retrieval phase before answering.
    chat_tools_max_steps: int = 4
    # Also offer configured MCP connectors (Notion, GitHub, etc.) in the chat phase.
    chat_connectors_enabled: bool = True
    # Local Ollama vision model for image understanding (pull it first).
    vision_model: str = "llama3.2-vision"
    # faster-whisper model size for audio transcription (tiny/base/small/medium/large-v3).
    whisper_model: str = "base"


settings = Settings()
