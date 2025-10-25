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
    # IMPORTANT: Embeddings must be pre-computed before starting the service
    # Run: python -m src.precompute_embeddings (for medical docs)
    # Run: python -m src.precompute_parenting_embeddings --force (for parenting videos)
    index_path: str = "data/embeddings/"  # Path to pre-computed medical embeddings
    parenting_index_path: str = "data/parenting_index"  # Path to pre-computed parenting embeddings

    # Retrieval Settings
    top_k_documents: int = 3


# Global settings instance
settings = Settings()
