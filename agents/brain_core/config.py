"""Application settings loaded from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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

    # Verification / self-consistency (sample N candidates + judge). Opt-in (N x cost).
    verify_enabled: bool = False
    verify_samples: int = 3

    # DSPy programmatic reasoning/optimization (local/provider-free). Opt-in + lazy.
    dspy_enabled: bool = False
    dspy_model: s