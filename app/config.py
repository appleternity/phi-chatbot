"""Application configuration using pydantic-settings."""
# TODO: We probably should not read .env directly.
# In production, environment variables should be set externally.

from pydantic import field_validator
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
    index_path: str = "data/embeddings/"  # Path to pre-computed medical embeddings

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

    # Retrieval Strategy Configuration
    # Options: "simple" (no reranking), "rerank" (two-stage), "advanced" (query expansion + rerank)
    RETRIEVAL_STRATEGY: str = "advanced"

    # Model Loading Configuration
    # True = load models at startup, False = lazy load on first use
    PRELOAD_MODELS: bool = False

    # Feature Flags
    # Enable database retry logic (False for POC to fail fast)
    ENABLE_RETRIES: bool = False

    # Model Names (standardized uppercase constants)
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    RERANKER_MODEL: str = "Qwen/Qwen3-Reranker-0.6B"

    # API Authentication (001-api-bearer-auth)
    API_BEARER_TOKEN: str

    @field_validator("API_BEARER_TOKEN")
    @classmethod
    def validate_api_bearer_token(cls, v: str) -> str:
        """Validate API Bearer token format and security requirements.

        Requirements:
        - Must be at least 64 characters (256-bit entropy minimum)
        - Must be hexadecimal format (0-9, a-f, A-F)
        - Whitespace is stripped automatically

        Args:
            v: The token value from environment variable

        Returns:
            str: The validated and stripped token value

        Raises:
            ValueError: If token is empty, too short, or not hexadecimal
        """
        # Strip whitespace
        v = v.strip()

        # Check if empty after stripping
        if not v:
            raise ValueError(
                "API_BEARER_TOKEN cannot be empty. "
                "Generate using: openssl rand -hex 32"
            )

        # Check minimum length (64 hex chars = 256-bit entropy)
        if len(v) < 64:
            raise ValueError(
                f"API_BEARER_TOKEN must be at least 64 hexadecimal characters "
                f"(got {len(v)}). Generate using: openssl rand -hex 32"
            )

        # Validate hexadecimal format (case-insensitive)
        if not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError(
                "API_BEARER_TOKEN must contain only hexadecimal characters "
                "(0-9, a-f, A-F). Generate using: openssl rand -hex 32"
            )

        return v


# Global settings instance
settings = Settings()
