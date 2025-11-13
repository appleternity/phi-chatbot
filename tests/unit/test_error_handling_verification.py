"""
Verification tests for error handling implementation.

These tests verify that error handling is correctly implemented in:
- OpenRouter provider (HTTP 401/403, 429, 5xx)
- Aliyun provider (HTTP 401/403, 429, 5xx)
- All providers (dimension mismatch validation)

All error handling logic is implemented in app/embeddings/utils.py retry_with_backoff()
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from openai import AuthenticationError, RateLimitError, APIError

from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider
from app.embeddings.utils import retry_with_backoff


class TestOpenRouterErrorHandling:
    """T068-T069: Verify HTTP error detection in OpenRouter provider."""

    @patch('app.embeddings.openrouter_provider.openai.OpenAI')
    def test_http_401_detection_not_retried(self, mock_openai_class):
        """T068: HTTP 401 authentication error should NOT be retried."""
        mock_client = MagicMock()

        # Create 401 error
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=Mock(status_code=401),
            body=None
        )
        auth_error.status_code = 401

        mock_client.embeddings.create.side_effect = auth_error
        mock_openai_class.return_value = mock_client

        provider = OpenRouterEmbeddingProvider(api_key="sk-or-invalid-key")

        # Should raise RuntimeError (wrapping auth error) immediately without retrying
        with pytest.raises(RuntimeError):
            provider.encode("test")

        # Verify only called once (no retries)
        assert mock_client.embeddings.create.call_count == 1

    @patch('app.embeddings.openrouter_provider.openai.OpenAI')
    def test_http_403_detection_not_retried(self, mock_openai_class):
        """T068: HTTP 403 forbidden error should NOT be retried."""
        mock_client = MagicMock()

        # Create 403 error with status_code attribute
        forbidden_error = APIError(
            message="Forbidden",
            request=Mock(),
            body=None
        )
        forbidden_error.status_code = 403

        mock_client.embeddings.create.side_effect = forbidden_error
        mock_openai_class.return_value = mock_client

        provider = OpenRouterEmbeddingProvider(api_key="sk-or-key")

        # Should raise RuntimeError (wrapping APIError) immediately without retrying
        with pytest.raises(RuntimeError):
            provider.encode("test")

        # Verify only called once (no retries for 403)
        assert mock_client.embeddings.create.call_count == 1

    @patch('app.embeddings.openrouter_provider.openai.OpenAI')
    def test_http_429_rate_limit_triggers_retry(self, mock_openai_class):
        """T069: HTTP 429 rate limit should trigger retry."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        # Create 429 rate limit error
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body=None
        )
        rate_limit_error.status_code = 429

        # Fail once with 429, then succeed
        mock_client.embeddings.create.side_effect = [
            rate_limit_error,
            mock_response
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenRouterEmbeddingProvider(api_key="sk-or-key")

        # Should succeed after retry
        with patch('time.sleep'):
            result = provider.encode("test")

        # Verify retried (2 calls: 1 fail + 1 success)
        assert mock_client.embeddings.create.call_count == 2

    @patch('app.embeddings.openrouter_provider.openai.OpenAI')
    def test_http_5xx_triggers_retry(self, mock_openai_class):
        """T069: HTTP 5xx errors should trigger retry with exponential backoff."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        # Create 500 server error
        server_error = APIError(
            message="Internal server error",
            request=Mock(),
            body=None
        )
        server_error.status_code = 500

        # Fail twice with 500, then succeed
        mock_client.embeddings.create.side_effect = [
            server_error,
            server_error,
            mock_response
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenRouterEmbeddingProvider(api_key="sk-or-key")

        # Should succeed after retries
        with patch('time.sleep'):
            result = provider.encode("test")

        # Verify retried (3 calls: 2 fails + 1 success)
        assert mock_client.embeddings.create.call_count == 3


class TestAliyunErrorHandling:
    """T071-T072: Verify HTTP error detection in Aliyun provider."""

    @patch('app.embeddings.aliyun_provider.openai.OpenAI')
    def test_http_401_detection_not_retried(self, mock_openai_class):
        """T071: HTTP 401 authentication error should NOT be retried."""
        mock_client = MagicMock()

        # Create 401 error
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=Mock(status_code=401),
            body=None
        )
        auth_error.status_code = 401

        mock_client.embeddings.create.side_effect = auth_error
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-invalid-key")

        # Should raise RuntimeError (wrapping auth error) immediately without retrying
        with pytest.raises(RuntimeError):
            provider.encode("test")

        # Verify only called once (no retries)
        assert mock_client.embeddings.create.call_count == 1

    @patch('app.embeddings.aliyun_provider.openai.OpenAI')
    def test_http_403_detection_not_retried(self, mock_openai_class):
        """T071: HTTP 403 forbidden error should NOT be retried."""
        mock_client = MagicMock()

        # Create 403 error with status_code attribute
        forbidden_error = APIError(
            message="Forbidden",
            request=Mock(),
            body=None
        )
        forbidden_error.status_code = 403

        mock_client.embeddings.create.side_effect = forbidden_error
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-key")

        # Should raise RuntimeError (wrapping APIError) immediately without retrying
        with pytest.raises(RuntimeError):
            provider.encode("test")

        # Verify only called once (no retries for 403)
        assert mock_client.embeddings.create.call_count == 1

    @patch('app.embeddings.aliyun_provider.openai.OpenAI')
    def test_http_429_rate_limit_triggers_retry(self, mock_openai_class):
        """T072: HTTP 429 rate limit should trigger retry."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        # Create 429 rate limit error
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body=None
        )
        rate_limit_error.status_code = 429

        # Fail once with 429, then succeed
        mock_client.embeddings.create.side_effect = [
            rate_limit_error,
            mock_response
        ]
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-key")

        # Should succeed after retry
        with patch('time.sleep'):
            result = provider.encode("test")

        # Verify retried (2 calls: 1 fail + 1 success)
        assert mock_client.embeddings.create.call_count == 2

    @patch('app.embeddings.aliyun_provider.openai.OpenAI')
    def test_http_5xx_triggers_retry(self, mock_openai_class):
        """T072: HTTP 5xx errors should trigger retry with exponential backoff."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]

        # Create 503 service unavailable error
        server_error = APIError(
            message="Service unavailable",
            request=Mock(),
            body=None
        )
        server_error.status_code = 503

        # Fail twice with 503, then succeed
        mock_client.embeddings.create.side_effect = [
            server_error,
            server_error,
            mock_response
        ]
        mock_openai_class.return_value = mock_client

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-key")

        # Should succeed after retries
        with patch('time.sleep'):
            result = provider.encode("test")

        # Verify retried (3 calls: 2 fails + 1 success)
        assert mock_client.embeddings.create.call_count == 3


class TestDimensionMismatchErrorHandling:
    """T070: Verify dimension mismatch error in all providers."""

    @patch('app.embeddings.openrouter_provider.openai.OpenAI')
    def test_openrouter_dimension_mismatch_error(self, mock_openai_class):
        """T070: OpenRouter validate_dimension() should raise clear error for dimension mismatch."""
        mock_openai_class.return_value = MagicMock()

        provider = OpenRouterEmbeddingProvider(api_key="sk-or-key")

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            provider.validate_dimension(768)

        error_message = str(exc_info.value)
        assert "openrouter" in error_message
        assert "1024-dim" in error_message
        assert "768-dim" in error_message
        assert "re-indexing" in error_message.lower()

    @patch('app.embeddings.aliyun_provider.openai.OpenAI')
    def test_aliyun_dimension_mismatch_error(self, mock_openai_class):
        """T070: Aliyun validate_dimension() should raise clear error for dimension mismatch."""
        mock_openai_class.return_value = MagicMock()

        provider = AliyunEmbeddingProvider(api_key="sk-aliyun-key")

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            provider.validate_dimension(384)

        error_message = str(exc_info.value)
        assert "aliyun" in error_message
        assert "1024-dim" in error_message
        assert "384-dim" in error_message
        assert "re-indexing" in error_message.lower()

    @patch('app.embeddings.local_encoder.Qwen3EmbeddingEncoder')
    def test_local_dimension_mismatch_error(self, mock_encoder):
        """T070: Local validate_dimension() should raise clear error for dimension mismatch."""
        from app.embeddings.local_encoder import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(
            model_name="Qwen/Qwen3-Embedding-0.6B",
            device="cpu",
            max_length=1024
        )

        # Should raise ValueError with clear message
        with pytest.raises(ValueError) as exc_info:
            provider.validate_dimension(768)

        error_message = str(exc_info.value)
        assert "local_qwen3" in error_message
        assert "1024-dim" in error_message
        assert "768-dim" in error_message
        assert "re-indexing" in error_message.lower()


class TestRetryUtilityFunction:
    """Verify retry_with_backoff utility function behavior."""

    def test_retry_utility_succeeds_immediately(self):
        """retry_with_backoff should return immediately on success."""
        def successful_call():
            return "success"

        result = retry_with_backoff(successful_call, max_retries=3)

        assert result == "success"

    def test_retry_utility_retries_transient_errors(self):
        """retry_with_backoff should retry transient errors."""
        call_count = 0

        def transient_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                error = APIError(
                    message="Temporary error",
                    request=Mock(),
                    body=None
                )
                error.status_code = 500
                raise error
            return "success"

        with patch('time.sleep'):
            result = retry_with_backoff(transient_failure, max_retries=3)

        assert result == "success"
        assert call_count == 3  # 2 failures + 1 success

    def test_retry_utility_does_not_retry_permanent_errors(self):
        """retry_with_backoff should NOT retry 4xx errors (except 429)."""
        call_count = 0

        def permanent_failure():
            nonlocal call_count
            call_count += 1
            error = AuthenticationError(
                message="Invalid credentials",
                response=Mock(status_code=401),
                body=None
            )
            error.status_code = 401
            raise error

        with pytest.raises(AuthenticationError):
            retry_with_backoff(permanent_failure, max_retries=3)

        # Should only be called once (no retries for 401)
        assert call_count == 1

    def test_retry_utility_exhausts_retries(self):
        """retry_with_backoff should raise after exhausting all retries."""
        def always_fail():
            error = APIError(
                message="Always fails",
                request=Mock(),
                body=None
            )
            error.status_code = 500
            raise error

        with patch('time.sleep'):
            with pytest.raises(APIError):
                retry_with_backoff(always_fail, max_retries=3)

    def test_retry_utility_retries_429_despite_being_4xx(self):
        """retry_with_backoff should retry 429 even though it's a 4xx error."""
        call_count = 0

        def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                error = RateLimitError(
                    message="Rate limit",
                    response=Mock(status_code=429),
                    body=None
                )
                error.status_code = 429
                raise error
            return "success"

        with patch('time.sleep'):
            result = retry_with_backoff(rate_limited, max_retries=3)

        assert result == "success"
        assert call_count == 2  # 1 failure + 1 success
