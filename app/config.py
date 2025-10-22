"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenRouter / LLM Configuration
    openai_api_base: str = "https://openrouter.ai/api/v1"
    openai_api_key: str
    model_name: str = "qwen/qwen3-max"

    # Application Settings
    log_level: str = "INFO"
    session_ttl_seconds: int = 3600
    environment: str = "development"

    # Embedding Model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Embedding Persistence Settings
    index_path: str = "data/embeddings/"  # Path to persistent index storage
    use_persistent_index: bool = True  # Enable/disable loading from persistent index
    force_recompute: bool = False  # Force re-computation of embeddings (development flag)

    # Retrieval Settings
    top_k_documents: int = 3


# Global settings instance
settings = Settings()
