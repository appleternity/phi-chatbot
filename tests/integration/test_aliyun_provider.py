"""
Integration tests for Aliyun DashScope embedding provider.

Tests Aliyun API integration with mocked responses to verify:
- API authentication (valid/invalid keys)
- Dense embedding format validation (1024-dim)
- Batch processing with automatic splitting

All tests use mocked API responses - no real API calls made.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from openai import OpenAI, AuthenticationError, RateLimitError, APIError

from app.embeddings.aliyun_provider import AliyunEmbeddingProvider


class TestAliyunAuthentication:
    """T053: Test Aliyun API authentication with mocked responses."""

    def test_valid_api_key_authentication(self):
        """T053: Valid API key should initialize provider successfully."""
        # Valid API key initialization should succeed
        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key-123")

        assert provider.client is not None
        assert provider.model == "text-embedding-v4"
        assert provider.dimension == 1024
        assert provider.batch_size == 100

    def test_invalid_api_key_raises_error(self):
        """T053: Invalid/empty API key should raise ValueError."""
        # Empty API key should raise ValueError
        with pytest.raises(ValueError, match="Aliyun API key is required"):
            AliyunEmbeddingProvider(api_key="")

        # None API key should raise ValueError
        with pytest.raises(ValueError, match="Aliyun API key is required"):
            AliyunEmbeddingProvider(api_key=None)

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_authentication_failure_on_api_call(self, mock_openai_class):
        """T053: Authentication error should be raised and NOT retried on encode()."""
        # Setup mock to raise AuthenticationError (401)
        mock_client = MagicMock()
        mock_error = AuthenticationError(
            message="Invalid API key", response=Mock(status_code=401), body=None
        )
        mock_error.status_code = 401
        mock_client.embeddings.create.side_effect = mock_error
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-invalid-key")

        # Should raise RuntimeError (wrapping AuthenticationError) without retrying
        with pytest.raises(RuntimeError, match="Aliyun embedding generation failed"):
            provider.encode("test authentication")

        # Verify only called once (no retries for 401)
        assert mock_client.embeddings.create.call_count == 1


class TestAliyunDenseEmbeddingFormat:
    """T054: Test Aliyun dense embedding format validation (1024-dim)."""

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_dense_embedding_format_1024_dim(self, mock_openai_class):
        """T054: Aliyun API should return 1024-dimensional dense embeddings."""
        # Setup mock to return 1024-dim embedding
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key")

        # Encode should return 1024-dim embedding
        embedding = provider.encode("test dense format")

        # Verify API call includes dimensions=1024 parameter
        call_args = mock_client.embeddings.create.call_args
        assert call_args.kwargs["model"] == "text-embedding-v4"
        assert call_args.kwargs["dimensions"] == 1024

        # Verify output is 1024-dimensional
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1024,)

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_get_embedding_dimension_returns_1024(self, mock_openai_class):
        """T054: get_embedding_dimension() should return 1024 for dense format."""
        mock_openai_class.return_value = MagicMock()

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key")

        # Should return 1024 for dense embedding format
        assert provider.get_embedding_dimension() == 1024


class TestAliyunBatchProcessing:
    """T055: Test Aliyun batch processing with automatic splitting."""

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_single_batch_under_limit(self, mock_openai_class):
        """T055: Texts under batch_size should be processed in single API call."""
        # Setup mock response for single batch
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1 * i] * 1024) for i in range(50)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key", batch_size=100)

        # Process 50 texts (under batch_size=100)
        texts = [f"text {i}" for i in range(50)]
        embeddings = provider.encode(texts)

        # Should make only 1 API call
        assert mock_client.embeddings.create.call_count == 1

        # Verify call arguments include dimensions=1024
        call_args = mock_client.embeddings.create.call_args
        assert call_args.kwargs["model"] == "text-embedding-v4"
        assert call_args.kwargs["dimensions"] == 1024
        assert len(call_args.kwargs["input"]) == 50

        # Verify output
        assert len(embeddings) == 50
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
        assert all(emb.shape == (1024,) for emb in embeddings)

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_automatic_batch_splitting(self, mock_openai_class):
        """T055: Texts exceeding batch_size should be automatically split into multiple batches."""
        # Setup mock to return different embeddings for each batch
        mock_client = MagicMock()

        def create_batch_response(batch_size):
            """Create mock response for given batch size."""
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1 * i] * 1024) for i in range(batch_size)]
            return mock_response

        # Mock will be called 3 times: 100, 100, 50 texts
        mock_client.embeddings.create.side_effect = [
            create_batch_response(100),  # Batch 1: texts 0-99
            create_batch_response(100),  # Batch 2: texts 100-199
            create_batch_response(50),  # Batch 3: texts 200-249
        ]
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key", batch_size=100)

        # Process 250 texts (should split into 3 batches: 100, 100, 50)
        texts = [f"text {i}" for i in range(250)]
        embeddings = provider.encode(texts)

        # Should make 3 API calls (3 batches)
        assert mock_client.embeddings.create.call_count == 3

        # Verify batch sizes and dimensions parameter in each call
        calls = mock_client.embeddings.create.call_args_list
        assert len(calls[0].kwargs["input"]) == 100  # Batch 1
        assert calls[0].kwargs["dimensions"] == 1024
        assert len(calls[1].kwargs["input"]) == 100  # Batch 2
        assert calls[1].kwargs["dimensions"] == 1024
        assert len(calls[2].kwargs["input"]) == 50  # Batch 3
        assert calls[2].kwargs["dimensions"] == 1024

        # Verify total output
        assert len(embeddings) == 250
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
        assert all(emb.shape == (1024,) for emb in embeddings)

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_exact_batch_size_boundary(self, mock_openai_class):
        """T055: Exactly batch_size texts should be processed in single batch."""
        # Setup mock response for exact batch size
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1 * i] * 1024) for i in range(100)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key", batch_size=100)

        # Process exactly 100 texts (batch_size boundary)
        texts = [f"text {i}" for i in range(100)]
        embeddings = provider.encode(texts)

        # Should make only 1 API call (no split needed)
        assert mock_client.embeddings.create.call_count == 1
        assert len(embeddings) == 100

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_retry_on_server_error(self, mock_openai_class):
        """T055: HTTP 5xx errors should trigger retry with exponential backoff."""
        # Setup mock to fail once with 500, then succeed
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        # Create API error with status_code
        api_error = APIError(message="Internal server error", request=Mock(), body=None)
        api_error.status_code = 500

        mock_client.embeddings.create.side_effect = [
            api_error,  # First attempt: 500 error
            mock_response,  # Second attempt: success
        ]
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key")

        # Should succeed after retry
        with patch("time.sleep"):  # Mock sleep to speed up test
            embedding = provider.encode("test retry logic")

        # Verify 2 attempts were made (1 failure + 1 success)
        assert mock_client.embeddings.create.call_count == 2
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1024,)

    @patch("app.embeddings.aliyun_provider.openai.OpenAI")
    def test_rate_limit_error_triggers_retry(self, mock_openai_class):
        """T055: HTTP 429 rate limit should trigger retry (special 4xx case)."""
        # Setup mock to fail with 429, then succeed
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded", response=Mock(status_code=429), body=None
        )
        rate_limit_error.status_code = 429

        mock_client.embeddings.create.side_effect = [
            rate_limit_error,  # First attempt: 429 rate limit
            mock_response,  # Second attempt: success
        ]
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-valid-key")

        # Should succeed after retry
        with patch("time.sleep"):  # Mock sleep to speed up test
            embedding = provider.encode("test rate limit")

        # Verify 2 attempts were made
        assert mock_client.embeddings.create.call_count == 2
        assert isinstance(embedding, np.ndarray)
