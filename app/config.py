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

    # Embedding Provider Configuration (004-cloud-embedding-refactor)
    # Options: "local" (Qwen3-Embedding-0.6B on device), "openrouter" (Qwen3 API), "aliyun" (text-embedding-v4)
    embedding_provider: str = "local"

    # Device for local embedding provider (mps/cuda/cpu)
    # Auto-detection fallback in encoder if device unavailable
    device: str = "mps"

    # Aliyun DashScope API Key (for embedding_provider="aliyun")
    aliyun_api_key: str = ""

    # Database table name for vector embeddings (supports A/B testing with multiple tables)
    table_name: str = "vector_chunks"

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        """Validate embedding_provider is one of the supported values."""
        valid_providers = ["local", "openrouter", "aliyun"]
        if v not in valid_providers:
            raise ValueError(
                f"Invalid embedding_provider: '{v}'. "
                f"Must be one of: {', '.join(valid_providers)}"
            )
        return v

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        """Validate table_name is a safe SQL identifier.

        Security: Prevents SQL injection by enforcing strict whitelist.
        Only predefined table names are allowed for production safety.
        """
        # Whitelist of allowed table names (for A/B testing scenarios)
        allowed_tables = frozenset({
            "vector_chunks",
            "vector_chunks_test",
            "vector_chunks_prod",
            "vector_chunks_staging",
        })

        # Strict whitelist enforcement - reject anything not explicitly allowed
        assert v in allowed_tables, \
            f"Invalid table name: '{v}'. " \
            f"Allowed tables: {', '.join(sorted(allowed_tables))}"

        return v


# Global settings instance
settings = Settings()
