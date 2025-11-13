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

    # Streaming Configuration (FR-014: idle timeout for SSE streams)
    # Maximum seconds of stream inactivity before timeout
    # Note: This is IDLE timeout (no events), not total execution time
    stream_idle_timeout: int = 30

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
    # EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    EMBEDDING_MODEL: str = "text-embedding-v4"

    RERANKER_MODEL: str = "Qwen/Qwen3-Reranker-0.6B"

    # Embedding Provider Configuration (004-cloud-embedding-refactor)
    # Options: "local" (Qwen3-Embedding-0.6B on device), "openrouter" (Qwen3 API), "aliyun" (text-embedding-v4)
    embedding_provider: str = "aliyun"

    # Device for local embedding provider (mps/cuda/cpu)
    # Auto-detection fallback in encoder if device unavailable
    device: str = "mps"
    batch_size: int = 10

    # Aliyun DashScope API Key (for embedding_provider="aliyun")
    aliyun_api_key: str = ""

    # Database table name for vector embeddings (supports A/B testing with multiple tables)
    table_name: str = "text-embedding-v4"

    # API Authentication (001-api-bearer-auth)
    API_BEARER_TOKEN: str

    # Keyword Search Configuration (005-multi-query-keyword-search)
    # Enable pg_trgm trigram-based keyword matching alongside vector search
    # Default: False (allows testing vector-only behavior first)
    enable_keyword_search: bool = True

    # Keyword search similarity threshold (0.0-1.0)
    # Default pg_trgm threshold is 0.3, but this is too high for short queries
    # against long documents. Recommended: 0.1 for medical terminology
    keyword_similarity_threshold: float = 0.1

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
            "text-embedding-v4",
            "qwen3-8b-openrouter"
        })

        # Strict whitelist enforcement - reject anything not explicitly allowed
        assert v in allowed_tables, \
            f"Invalid table name: '{v}'. " \
            f"Allowed tables: {', '.join(sorted(allowed_tables))}"

        return v

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
