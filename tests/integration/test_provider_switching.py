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
from app.embeddings.factory import EmbeddingProviderFactory
from app.embeddings.local_encoder import LocalEmbeddingProvider
from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider


class TestProviderSwitching:
    """T056-T057: Test configuration changes between providers."""

    @patch("app.embeddings.local_encoder.LocalEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.openrouter_provider.OpenRouterEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.local_encoder.Qwen3EmbeddingEncoder")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_switch_from_local_to_openrouter(
        self, mock_encoder, mock_or_validate, mock_local_validate
    ):
        """T056: Config change from local to openrouter should create OpenRouter provider."""
        # Start with local provider
        settings_local = Settings(
            embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
        )

        provider_local = EmbeddingProviderFactory.create_provider(settings_local)

        # Verify local provider created
        assert isinstance(provider_local, LocalEmbeddingProvider)
        assert provider_local.get_provider_name() == "local_qwen3"

        # Switch to openrouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-valid-key-123",
            embedding_dim=1024,
        )

        provider_openrouter = EmbeddingProviderFactory.create_provider(settings_openrouter)

        # Verify openrouter provider created
        assert isinstance(provider_openrouter, OpenRouterEmbeddingProvider)
        assert provider_openrouter.get_provider_name() == "openrouter"
        assert provider_openrouter.get_embedding_dimension() == 1024

    @patch("app.embeddings.openrouter_provider.OpenRouterEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.aliyun_provider.AliyunEmbeddingProvider.validate_dimension")
    @patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "openrouter",
            "OPENAI_API_KEY": "sk-or-key",
            "EMBEDDING_DIM": "1024",
        },
    )
    def test_switch_from_openrouter_to_aliyun(self, mock_aliyun_validate, mock_or_validate):
        """T057: Config change from openrouter to aliyun should create Aliyun provider."""
        # Start with openrouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-valid-key-123",
            aliyun_api_key="",
            embedding_dim=1024,
        )

        provider_openrouter = EmbeddingProviderFactory.create_provider(settings_openrouter)

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

        provider_aliyun = EmbeddingProviderFactory.create_provider(settings_aliyun)

        # Verify aliyun provider created
        assert isinstance(provider_aliyun, AliyunEmbeddingProvider)
        assert provider_aliyun.get_provider_name() == "aliyun"
        assert provider_aliyun.get_embedding_dimension() == 1024

    @patch("app.embeddings.local_encoder.LocalEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.aliyun_provider.AliyunEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.local_encoder.Qwen3EmbeddingEncoder")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_switch_from_aliyun_to_local(
        self, mock_encoder, mock_aliyun_validate, mock_local_validate
    ):
        """T056-T057: Config change from aliyun to local should create Local provider."""
        # Start with aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-valid-key",
            embedding_dim=1024,
        )

        provider_aliyun = EmbeddingProviderFactory.create_provider(settings_aliyun)

        # Verify aliyun provider created
        assert isinstance(provider_aliyun, AliyunEmbeddingProvider)

        # Switch back to local provider
        settings_local = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            aliyun_api_key="",
            embedding_dim=1024,
        )

        provider_local = EmbeddingProviderFactory.create_provider(settings_local)

        # Verify local provider created
        assert isinstance(provider_local, LocalEmbeddingProvider)
        assert provider_local.get_provider_name() == "local_qwen3"


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

        # Factory should raise ValueError when creating provider
        with pytest.raises(ValueError, match="OpenRouter API key required"):
            EmbeddingProviderFactory.create_provider(settings)

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

        # Factory should raise ValueError when creating provider
        with pytest.raises(ValueError, match="Aliyun API key required"):
            EmbeddingProviderFactory.create_provider(settings)

    @patch("app.embeddings.local_encoder.Qwen3EmbeddingEncoder")
    @patch.dict(
        "os.environ",
        {"EMBEDDING_PROVIDER": "local", "OPENAI_API_KEY": "sk-test-key", "EMBEDDING_DIM": "1024"},
    )
    def test_startup_with_local_provider_no_api_key_needed(self, mock_encoder):
        """T059: Local provider should not require cloud API keys."""
        # Create settings with local provider
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",  # For LLM only
            aliyun_api_key="",  # Not needed for local
            embedding_dim=1024,
        )

        # Factory should succeed (no cloud API keys needed)
        provider = EmbeddingProviderFactory.create_provider(settings)

        # Verify local provider created
        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.get_provider_name() == "local_qwen3"

    @patch("app.embeddings.local_encoder.LocalEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.openrouter_provider.OpenRouterEmbeddingProvider.validate_dimension")
    @patch("app.embeddings.aliyun_provider.AliyunEmbeddingProvider.validate_dimension")
    @patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "openrouter",
            "OPENAI_API_KEY": "sk-or-key",
            "EMBEDDING_DIM": "1024",
        },
    )
    def test_multiple_provider_switches_in_sequence(
        self, mock_aliyun_validate, mock_or_validate, mock_local_validate
    ):
        """T056-T059: Multiple sequential provider switches should work correctly."""
        # Switch sequence: local → openrouter → aliyun → local
        providers = []

        # 1. Local provider
        with patch("app.embeddings.local_encoder.Qwen3EmbeddingEncoder"):
            settings_local = Settings(
                embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
            )
            providers.append(EmbeddingProviderFactory.create_provider(settings_local))

        # 2. OpenRouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter", openai_api_key="sk-or-key", embedding_dim=1024
        )
        providers.append(EmbeddingProviderFactory.create_provider(settings_openrouter))

        # 3. Aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-key",
            embedding_dim=1024,
        )
        providers.append(EmbeddingProviderFactory.create_provider(settings_aliyun))

        # 4. Back to local provider
        with patch("app.embeddings.local_encoder.Qwen3EmbeddingEncoder"):
            settings_local2 = Settings(
                embedding_provider="local", openai_api_key="sk-test-key", embedding_dim=1024
            )
            providers.append(EmbeddingProviderFactory.create_provider(settings_local2))

        # Verify all providers created correctly
        assert isinstance(providers[0], LocalEmbeddingProvider)
        assert isinstance(providers[1], OpenRouterEmbeddingProvider)
        assert isinstance(providers[2], AliyunEmbeddingProvider)
        assert isinstance(providers[3], LocalEmbeddingProvider)

        # Verify provider names
        assert providers[0].get_provider_name() == "local_qwen3"
        assert providers[1].get_provider_name() == "openrouter"
        assert providers[2].get_provider_name() == "aliyun"
        assert providers[3].get_provider_name() == "local_qwen3"
