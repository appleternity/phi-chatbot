"""
Contract tests for EmbeddingProvider protocol compliance.

These tests verify that all provider implementations adhere to the
EmbeddingProvider protocol specification.

CRITICAL TDD REQUIREMENT:
- These tests MUST be written FIRST
- These tests MUST FAIL before implementation
- Run: pytest tests/contract/test_embedding_provider_interface.py -v
- Verify failures before proceeding with implementation
"""

import pytest
from typing import Protocol, runtime_checkable

from app.embeddings.base import EmbeddingProvider
from app.embeddings.local_encoder import Qwen3EmbeddingProvider


# T025: Contract test - Qwen3EmbeddingProvider implements EmbeddingProvider protocol
class TestQwen3EmbeddingProviderProtocolCompliance:
    """Verify Qwen3EmbeddingProvider implements EmbeddingProvider protocol."""

    def test_local_provider_is_embedding_provider(self):
        """T025: Qwen3EmbeddingProvider must implement EmbeddingProvider protocol."""
        from unittest.mock import patch

        # Mock model loading to avoid HuggingFace downloads in contract tests
        with patch("app.embeddings.local_encoder.AutoModel"), \
             patch("app.embeddings.local_encoder.AutoTokenizer"):
            provider = Qwen3EmbeddingProvider(
                model_name="Qwen/Qwen3-Embedding-0.6B", device="cpu", max_length=1024
            )

            # Protocol check
            assert isinstance(
                provider, EmbeddingProvider
            ), "Qwen3EmbeddingProvider must implement EmbeddingProvider protocol"


# T026: Contract test - All providers implement encode() with correct signature
class TestEncodeMethodSignature:
    """Verify all providers implement encode() with correct signature."""

    @pytest.fixture
    def local_provider(self):
        """Create Qwen3EmbeddingProvider instance."""
        from unittest.mock import patch

        # Mock model loading to avoid HuggingFace downloads in contract tests
        with patch("app.embeddings.local_encoder.AutoModel"), \
             patch("app.embeddings.local_encoder.AutoTokenizer"):
            return Qwen3EmbeddingProvider(
                model_name="Qwen/Qwen3-Embedding-0.6B", device="cpu", max_length=1024
            )

    def test_local_provider_has_encode_method(self, local_provider):
        """T026: Qwen3EmbeddingProvider must have encode() method."""
        assert hasattr(local_provider, "encode"), "Qwen3EmbeddingProvider must have encode() method"
        assert callable(getattr(local_provider, "encode")), "encode() must be callable"

    def test_openrouter_provider_has_encode_method(self):
        """T026: OpenRouterEmbeddingProvider must have encode() method."""
        # This will fail until OpenRouterEmbeddingProvider is implemented
        from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider

        provider = OpenRouterEmbeddingProvider(api_key="test-key")

        assert hasattr(provider, "encode"), "OpenRouterEmbeddingProvider must have encode() method"
        assert callable(getattr(provider, "encode")), "encode() must be callable"

    def test_aliyun_provider_has_encode_method(self):
        """T026: AliyunEmbeddingProvider must have encode() method."""
        # This will fail until AliyunEmbeddingProvider is implemented
        from app.embeddings.aliyun_provider import AliyunEmbeddingProvider

        provider = AliyunEmbeddingProvider(api_key="test-key")

        assert hasattr(provider, "encode"), "AliyunEmbeddingProvider must have encode() method"
        assert callable(getattr(provider, "encode")), "encode() must be callable"


# T028: Contract test - Provider names match specification
class TestProviderNames:
    """Verify provider names match specification."""

    def test_local_provider_name(self):
        """T028: Qwen3EmbeddingProvider must return 'qwen3_local' as provider name."""
        # Skip model loading in contract test (requires large download)
        # Just verify method exists and returns correct value
        # This is sufficient for protocol compliance verification
        from unittest.mock import MagicMock, patch

        with patch("app.embeddings.local_encoder.AutoModel"), \
             patch("app.embeddings.local_encoder.AutoTokenizer"):
            provider = Qwen3EmbeddingProvider(
                model_name="Qwen/Qwen3-Embedding-0.6B", device="cpu", max_length=1024
            )

            assert (
                provider.get_provider_name() == "qwen3_local"
            ), "Qwen3EmbeddingProvider must return 'qwen3_local' as provider name"

    def test_openrouter_provider_name(self):
        """T028: OpenRouterEmbeddingProvider must return 'openrouter' as provider name."""
        # This will fail until OpenRouterEmbeddingProvider is implemented
        from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider

        provider = OpenRouterEmbeddingProvider(api_key="test-key")

        assert (
            provider.get_provider_name() == "openrouter"
        ), "OpenRouterEmbeddingProvider must return 'openrouter' as provider name"

    def test_aliyun_provider_name(self):
        """T028: AliyunEmbeddingProvider must return 'aliyun' as provider name."""
        # This will fail until AliyunEmbeddingProvider is implemented
        from app.embeddings.aliyun_provider import AliyunEmbeddingProvider

        provider = AliyunEmbeddingProvider(api_key="test-key")

        assert (
            provider.get_provider_name() == "aliyun"
        ), "AliyunEmbeddingProvider must return 'aliyun' as provider name"
