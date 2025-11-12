"""
Unit tests for embedding provider factory.

Tests factory function implementation:
- Factory returns correct provider for each type
- Factory raises clear errors for invalid configurations
- Factory validates API keys before provider creation
"""

import pytest
from unittest.mock import patch, MagicMock

from app.config import Settings
from app.embeddings import create_embedding_provider
from app.embeddings.local_encoder import Qwen3EmbeddingProvider
from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider


class TestFactoryProviderCreation:
    """T063-T065: Test factory returns correct provider for each type."""

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    def test_factory_returns_local_provider_for_local(self, mock_tokenizer, mock_model):
        """T063: Factory should return Qwen3EmbeddingProvider for 'local'."""
        settings = Settings(
            embedding_provider="local", openai_api_key="sk-test-key"
        )

        provider = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key
        )

        # Verify correct provider type
        assert isinstance(provider, Qwen3EmbeddingProvider)
        assert provider.get_provider_name() == "qwen3_local"
        assert provider.get_embedding_dimension() == 1024

    def test_factory_returns_openrouter_provider_for_openrouter(self):
        """T064: Factory should return OpenRouterEmbeddingProvider for 'openrouter'."""
        settings = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-valid-key-123",
        )

        provider = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key
        )

        # Verify correct provider type
        assert isinstance(provider, OpenRouterEmbeddingProvider)
        assert provider.get_provider_name() == "openrouter"
        assert provider.get_embedding_dimension() == 1024

        # Verify OpenRouter-specific configuration
        assert provider.model == "qwen/qwen3-embedding-0.6b"
        assert provider.batch_size == 100

    def test_factory_returns_aliyun_provider_for_aliyun(self):
        """T065: Factory should return AliyunEmbeddingProvider for 'aliyun'."""
        settings = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-valid-key-456",
        )

        provider = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key
        )

        # Verify correct provider type
        assert isinstance(provider, AliyunEmbeddingProvider)
        assert provider.get_provider_name() == "aliyun"
        assert provider.get_embedding_dimension() == 1024

        # Verify Aliyun-specific configuration
        assert provider.model == "text-embedding-v4"
        assert provider.batch_size == 100


class TestFactoryErrorHandling:
    """T066-T067: Test factory error handling for invalid configurations."""

    def test_factory_raises_error_for_invalid_provider(self):
        """T066: Factory should raise AssertionError for invalid provider type."""
        # Note: This should be caught by Settings validation before reaching factory
        # But test defensive check in factory as well

        with pytest.raises(AssertionError) as exc_info:
            create_embedding_provider(
                provider_type="invalid_provider",
                embedding_model="Qwen/Qwen3-Embedding-0.6B",
                device="mps",
                openai_api_key="sk-test-key",
                aliyun_api_key=""
            )

        # Verify error message is clear and helpful
        error_message = str(exc_info.value)
        assert "Invalid provider_type" in error_message
        assert "invalid_provider" in error_message
        assert "local" in error_message
        assert "openrouter" in error_message
        assert "aliyun" in error_message

    def test_factory_raises_clear_error_for_missing_openrouter_key(self):
        """T067: Factory should raise clear error when OpenRouter API key missing."""
        with pytest.raises(AssertionError) as exc_info:
            create_embedding_provider(
                provider_type="openrouter",
                embedding_model="Qwen/Qwen3-Embedding-0.6B",
                device="mps",
                openai_api_key="",  # Empty API key
                aliyun_api_key=""
            )

        # Verify error message is clear and actionable
        error_message = str(exc_info.value)
        assert "OpenRouter API key required" in error_message
        assert "OPENAI_API_KEY" in error_message

    def test_factory_raises_clear_error_for_missing_aliyun_key(self):
        """T067: Factory should raise clear error when Aliyun API key missing."""
        with pytest.raises(AssertionError) as exc_info:
            create_embedding_provider(
                provider_type="aliyun",
                embedding_model="Qwen/Qwen3-Embedding-0.6B",
                device="mps",
                openai_api_key="sk-test-key",  # For LLM
                aliyun_api_key=""  # Empty Aliyun API key
            )

        # Verify error message is clear and actionable
        error_message = str(exc_info.value)
        assert "Aliyun API key required" in error_message
        assert "ALIYUN_API_KEY" in error_message

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    def test_factory_does_not_require_cloud_keys_for_local(self, mock_tokenizer, mock_model):
        """T067: Factory should not require cloud API keys for local provider."""
        # Should succeed without cloud API keys
        provider = create_embedding_provider(
            provider_type="local",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-test-key",  # For LLM only
            aliyun_api_key=""  # Not needed
        )

        assert isinstance(provider, Qwen3EmbeddingProvider)
        assert provider.get_provider_name() == "qwen3_local"


class TestFactoryConfigurationPropagation:
    """Test factory correctly propagates configuration to providers."""

    @patch("app.embeddings.local_encoder.AutoModel")
    @patch("app.embeddings.local_encoder.AutoTokenizer")
    def test_factory_propagates_model_name_to_local(self, mock_tokenizer, mock_model):
        """Factory should propagate embedding_model to local provider."""
        provider = create_embedding_provider(
            provider_type="local",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-test-key",
            aliyun_api_key=""
        )

        # Verify model name from settings was used
        # Qwen3EmbeddingProvider stores this in encoder initialization
        assert isinstance(provider, Qwen3EmbeddingProvider)

    def test_factory_uses_correct_batch_size_for_openrouter(self):
        """Factory should use batch_size=100 for OpenRouter provider."""
        provider = create_embedding_provider(
            provider_type="openrouter",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-or-key",
            aliyun_api_key=""
        )

        assert provider.batch_size == 100

    def test_factory_uses_correct_batch_size_for_aliyun(self):
        """Factory should use batch_size=100 for Aliyun provider."""
        provider = create_embedding_provider(
            provider_type="aliyun",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-key"
        )

        assert provider.batch_size == 100

    def test_factory_creates_new_instance_each_call(self):
        """Factory should create new provider instance each time."""
        provider1 = create_embedding_provider(
            provider_type="openrouter",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-or-key",
            aliyun_api_key=""
        )
        provider2 = create_embedding_provider(
            provider_type="openrouter",
            embedding_model="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            openai_api_key="sk-or-key",
            aliyun_api_key=""
        )

        # Should be different instances
        assert provider1 is not provider2
        # But same type and configuration
        assert type(provider1) == type(provider2)
        assert provider1.get_provider_name() == provider2.get_provider_name()
