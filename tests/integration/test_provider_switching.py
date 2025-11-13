"""
Integration tests for embedding provider switching.

Tests provider switching scenarios:
- Config change from local to openrouter
- Config change from openrouter to aliyun
- Service startup with invalid provider type
- Service startup with missing API key

All tests use mocked providers and configurations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError

from app.config import Settings
from app.embeddings.factory import create_embedding_provider
from app.embeddings import LocalEmbeddingProvider
from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider


class TestProviderSwitching:
    """T056-T057: Test configuration changes between providers."""

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    @patch("app.embeddings.openrouter_provider.openai.OpenAI")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_switch_from_local_to_openrouter(
        self, mock_or_client, mock_tokenizer, mock_model
    ):
        """T056: Config change from local to openrouter should create OpenRouter provider."""
        # Start with local provider
        settings_local = Settings(
            embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
        )

        provider_local = create_embedding_provider(
            provider_type=settings_local.embedding_provider,
            embedding_model=settings_local.EMBEDDING_MODEL,
            device=settings_local.device,
            openai_api_key=settings_local.openai_api_key,
            aliyun_api_key=settings_local.aliyun_api_key,
        )

        # Verify local provider created
        assert isinstance(provider_local, LocalEmbeddingProvider)
        assert provider_local.get_provider_name() == "qwen3_local"

        # Switch to openrouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-valid-key-123",
            embedding_dim=1024,
        )

        provider_openrouter = create_embedding_provider(
            provider_type=settings_openrouter.embedding_provider,
            embedding_model=settings_openrouter.EMBEDDING_MODEL,
            device=settings_openrouter.device,
            openai_api_key=settings_openrouter.openai_api_key,
            aliyun_api_key=settings_openrouter.aliyun_api_key,
        )

        # Verify openrouter provider created
        assert isinstance(provider_openrouter, OpenRouterEmbeddingProvider)
        assert provider_openrouter.get_provider_name() == "openrouter"
        # No get_embedding_dimension() method anymore - check model instead
        assert provider_openrouter.model == "Qwen/Qwen3-Embedding-0.6B"

    @patch("app.embeddings.openrouter_provider.openai.OpenAI")
    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    @patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "openrouter",
            "OPENAI_API_KEY": "sk-or-key",
            "EMBEDDING_DIM": "1024",
        },
    )
    def test_switch_from_openrouter_to_aliyun(self, mock_aliyun_client, mock_or_client):
        """T057: Config change from openrouter to aliyun should create Aliyun provider."""
        # Start with openrouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-valid-key-123",
            aliyun_api_key="",
            embedding_dim=1024,
        )

        provider_openrouter = create_embedding_provider(
            provider_type=settings_openrouter.embedding_provider,
            embedding_model=settings_openrouter.EMBEDDING_MODEL,
            device=settings_openrouter.device,
            openai_api_key=settings_openrouter.openai_api_key,
            aliyun_api_key=settings_openrouter.aliyun_api_key,
        )

        # Verify openrouter provider created
        assert isinstance(provider_openrouter, OpenRouterEmbeddingProvider)
        assert provider_openrouter.get_provider_name() == "openrouter"

        # Switch to aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",  # Still required for LLM
            aliyun_api_key="sk-aliyun-valid-key-456",
            embedding_dim=1024,
        )

        provider_aliyun = create_embedding_provider(
            provider_type=settings_aliyun.embedding_provider,
            embedding_model=settings_aliyun.EMBEDDING_MODEL,
            device=settings_aliyun.device,
            openai_api_key=settings_aliyun.openai_api_key,
            aliyun_api_key=settings_aliyun.aliyun_api_key,
        )

        # Verify aliyun provider created
        assert isinstance(provider_aliyun, AliyunEmbeddingProvider)
        assert provider_aliyun.get_provider_name() == "aliyun"
        # No get_embedding_dimension() method anymore - check model and dimensions
        assert provider_aliyun.model == "Qwen/Qwen3-Embedding-0.6B"
        assert provider_aliyun.dimensions == 1024

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_switch_from_aliyun_to_local(
        self, mock_aliyun_client, mock_tokenizer, mock_model
    ):
        """T056-T057: Config change from aliyun to local should create Local provider."""
        # Start with aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-valid-key",
            embedding_dim=1024,
        )

        provider_aliyun = create_embedding_provider(
            provider_type=settings_aliyun.embedding_provider,
            embedding_model=settings_aliyun.EMBEDDING_MODEL,
            device=settings_aliyun.device,
            openai_api_key=settings_aliyun.openai_api_key,
            aliyun_api_key=settings_aliyun.aliyun_api_key,
        )

        # Verify aliyun provider created
        assert isinstance(provider_aliyun, AliyunEmbeddingProvider)

        # Switch back to local provider
        settings_local = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            aliyun_api_key="",
            embedding_dim=1024,
        )

        provider_local = create_embedding_provider(
            provider_type=settings_local.embedding_provider,
            embedding_model=settings_local.EMBEDDING_MODEL,
            device=settings_local.device,
            openai_api_key=settings_local.openai_api_key,
            aliyun_api_key=settings_local.aliyun_api_key,
        )

        # Verify local provider created
        assert isinstance(provider_local, LocalEmbeddingProvider)
        assert provider_local.get_provider_name() == "qwen3_local"


class TestInvalidProviderConfiguration:
    """T058-T059: Test service startup with invalid configurations."""

    @patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "invalid_provider",
            "OPENAI_API_KEY": "sk-test-key",
            "EMBEDDING_DIM": "1024",
        },
    )
    def test_startup_with_invalid_provider_type(self):
        """T058: Service startup with invalid provider type should raise ValidationError."""
        # Attempt to create settings with invalid provider type
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                embedding_provider="invalid_provider",
                openai_api_key="sk-test-key",
                embedding_dim=1024,
            )

        # Verify error message contains valid provider options
        error_message = str(exc_info.value)
        assert (
            "invalid_provider" in error_message.lower()
            or "embedding_provider" in error_message.lower()
        )

    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "unknown", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_startup_with_unknown_provider_rejected(self):
        """T058: Unknown provider types should be rejected by config validation."""
        # Test various invalid provider names
        invalid_providers = ["unknown", "gpt4", "claude", "gemini", ""]

        for invalid_provider in invalid_providers:
            with pytest.raises(ValidationError):
                Settings(
                    embedding_provider=invalid_provider,
                    openai_api_key="sk-test-key",
                    embedding_dim=1024,
                )

    @patch.dict("os.environ", {"EMBEDDING_PROVIDER": "openrouter", "EMBEDDING_DIM": "1024"})
    def test_startup_with_missing_openrouter_api_key(self):
        """T059: Service startup with missing OpenRouter API key should raise ValueError."""
        # Create settings with openrouter but no API key
        settings = Settings(
            embedding_provider="openrouter",
            openai_api_key="",  # Missing API key
            embedding_dim=1024,
        )

        # Factory should raise AssertionError when creating provider
        with pytest.raises(AssertionError, match="OpenRouter API key required"):
            create_embedding_provider(
                provider_type=settings.embedding_provider,
                embedding_model=settings.EMBEDDING_MODEL,
                device=settings.device,
                openai_api_key=settings.openai_api_key,
                aliyun_api_key=settings.aliyun_api_key,
            )

    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "aliyun", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_startup_with_missing_aliyun_api_key(self):
        """T059: Service startup with missing Aliyun API key should raise ValueError."""
        # Create settings with aliyun but no API key
        settings = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",  # For LLM
            aliyun_api_key="",  # Missing Aliyun API key
            embedding_dim=1024,
        )

        # Factory should raise AssertionError when creating provider
        with pytest.raises(AssertionError, match="Aliyun API key required"):
            create_embedding_provider(
                provider_type=settings.embedding_provider,
                embedding_model=settings.EMBEDDING_MODEL,
                device=settings.device,
                openai_api_key=settings.openai_api_key,
                aliyun_api_key=settings.aliyun_api_key,
            )

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_startup_with_local_provider_no_api_key_needed(self, mock_tokenizer, mock_model):
        """T059: Local provider should not require cloud API keys."""
        # Create settings with local provider
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",  # For LLM only
            aliyun_api_key="",  # Not needed for local
            embedding_dim=1024,
        )

        # Factory should succeed (no cloud API keys needed)
        provider = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key,
        )

        # Verify local provider created
        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.get_provider_name() == "qwen3_local"

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    @patch("app.embeddings.openrouter_provider.openai.OpenAI")
    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    @patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "openrouter",
            "OPENAI_API_KEY": "sk-or-key",
            "EMBEDDING_DIM": "1024",
        },
    )
    def test_multiple_provider_switches_in_sequence(
        self, mock_aliyun_client, mock_or_client, mock_tokenizer, mock_model
    ):
        """T056-T059: Multiple sequential provider switches should work correctly."""
        # Switch sequence: local → openrouter → aliyun → local
        providers = []

        # 1. Local provider
        settings_local = Settings(
            embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
        )
        providers.append(
            create_embedding_provider(
                provider_type=settings_local.embedding_provider,
                embedding_model=settings_local.EMBEDDING_MODEL,
                device=settings_local.device,
                openai_api_key=settings_local.openai_api_key,
                aliyun_api_key=settings_local.aliyun_api_key,
            )
        )

        # 2. OpenRouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter", openai_api_key="sk-or-key", embedding_dim=1024
        )
        providers.append(
            create_embedding_provider(
                provider_type=settings_openrouter.embedding_provider,
                embedding_model=settings_openrouter.EMBEDDING_MODEL,
                device=settings_openrouter.device,
                openai_api_key=settings_openrouter.openai_api_key,
                aliyun_api_key=settings_openrouter.aliyun_api_key,
            )
        )

        # 3. Aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-key",
            embedding_dim=1024,
        )
        providers.append(
            create_embedding_provider(
                provider_type=settings_aliyun.embedding_provider,
                embedding_model=settings_aliyun.EMBEDDING_MODEL,
                device=settings_aliyun.device,
                openai_api_key=settings_aliyun.openai_api_key,
                aliyun_api_key=settings_aliyun.aliyun_api_key,
            )
        )

        # 4. Back to local provider
        settings_local2 = Settings(
            embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
        )
        providers.append(
            create_embedding_provider(
                provider_type=settings_local2.embedding_provider,
                embedding_model=settings_local2.EMBEDDING_MODEL,
                device=settings_local2.device,
                openai_api_key=settings_local2.openai_api_key,
                aliyun_api_key=settings_local2.aliyun_api_key,
            )
        )

        # Verify all providers created correctly
        assert isinstance(providers[0], LocalEmbeddingProvider)
        assert isinstance(providers[1], OpenRouterEmbeddingProvider)
        assert isinstance(providers[2], AliyunEmbeddingProvider)
        assert isinstance(providers[3], LocalEmbeddingProvider)

        # Verify provider names
        assert providers[0].get_provider_name() == "qwen3_local"
        assert providers[1].get_provider_name() == "openrouter"
        assert providers[2].get_provider_name() == "aliyun"
        assert providers[3].get_provider_name() == "qwen3_local"
