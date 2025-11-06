"""Application configuration using pydantic-settings."""
# TODO: We probably should not read .env directly.
# In production, environment variables should be set externally.

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
    top_k_documents: int = 5

    # PostgreSQL + pgvector Settings (002-semantic-search)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medical_knowledge"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL from components."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # embedding model
    embedding_model_name: str = "Qwen/Qwen3-Embedding-0.6B"

    # Parenting Agent Hybrid Retrieval Settings
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"
    reranker_top_k: int = 3

    # Retrieval Strategy Configuration
    # Options: "simple" (no reranking), "rerank" (two-stage), "advanced" (query expansion + rerank)
    RETRIEVAL_STRATEGY: str = "advanced"

    # Model Loading Configuration
    # True = load models at startup, False = lazy load on first use
    PRELOAD_MODELS: bool = False

    # Feature Flags
    # Temporarily disable parenting system to focus on medication Q&A POC
    ENABLE_PARENTING: bool = False
    # Enable database retry logic (False for POC to fail fast)
    ENABLE_RETRIES: bool = False

    # Model Names (standardized uppercase constants)
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    RERANKER_MODEL: str = "Qwen/Qwen3-Reranker-0.6B"


# Global settings instance
settings = Settings()
