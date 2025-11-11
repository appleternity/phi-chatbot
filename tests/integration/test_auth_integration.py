"""Integration tests for /chat endpoint authentication flow.

These tests verify end-to-end authentication behavior when protecting
the /chat endpoint with Bearer token authentication.

Test Coverage:
- Valid token → 200 OK (successful request)
- Missing token → 401 MISSING_TOKEN
- Invalid token → 401 INVALID_TOKEN
- Malformed header → 401 MALFORMED_HEADER
- Error response format matches AuthError schema

Note: These tests will fail until the authentication dependency
is implemented and added to the /chat endpoint (T011-T012).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture
def test_token():
    """Valid test token for authentication."""
    # Generate a 64-character hex token (minimum required length)
    return "a" * 64


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestChatAuthenticationFlow:
    """Integration tests for /chat endpoint authentication."""

    def test_valid_token_returns_200_ok(self, client, test_token):
        """Verify request with valid Bearer token succeeds.

        Expected behavior:
        - Status: 200 OK
        - Response: Normal chat response
        - No authentication error
        """
        # Mock the settings to use test token
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Make request with valid Bearer token
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {test_token}"},
            )

            # Verify authentication succeeded
            assert response.status_code == 200

            # Verify response is not an auth error
            # (it should be a ChatResponse or error, but not auth error)
            response_data = response.json()
            assert "error_code" not in response_data or response_data.get(
                "error_code"
            ) not in ["MISSING_TOKEN", "INVALID_TOKEN", "MALFORMED_HEADER"]

    def test_missing_token_returns_401_missing_token(self, client, test_token):
        """Verify request without Authorization header returns 401 MISSING_TOKEN.

        Expected behavior:
        - Status: 401 Unauthorized
        - Response body: AuthError with MISSING_TOKEN error code
        - detail: Explains missing Authorization header
        """
        # Mock the settings to use test token
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Make request without Authorization header
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
            )

            # Verify authentication failed with correct status
            assert response.status_code == 401

            # Verify error response format
            error_data = response.json()
            assert "detail" in error_data
            assert "error_code" in error_data
            assert error_data["error_code"] == "MISSING_TOKEN"

            # Verify detail message is meaningful
            assert len(error_data["detail"]) > 0

    def test_invalid_token_returns_401_invalid_token(self, client, test_token):
        """Verify request with wrong token returns 401 INVALID_TOKEN.

        Expected behavior:
        - Status: 401 Unauthorized
        - Response body: AuthError with INVALID_TOKEN error code
        - detail: Explains token validation failed
        """
        # Mock the settings to use test token
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Make request with WRONG token
            wrong_token = "b" * 64  # Different token
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {wrong_token}"},
            )

            # Verify authentication failed
            assert response.status_code == 401

            # Verify error response format
            error_data = response.json()
            assert "detail" in error_data
            assert "error_code" in error_data
            assert error_data["error_code"] == "INVALID_TOKEN"

    def test_malformed_header_returns_401_malformed_header(self, client, test_token):
        """Verify request with malformed Authorization header returns 401 MALFORMED_HEADER.

        Expected behavior:
        - Status: 401 Unauthorized
        - Response body: AuthError with MALFORMED_HEADER error code
        - detail: Explains correct header format
        """
        # Mock the settings to use test token
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Make request with malformed header (missing "Bearer" prefix)
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": test_token},  # Missing "Bearer " prefix
            )

            # Verify authentication failed
            assert response.status_code == 401

            # Verify error response format
            error_data = response.json()
            assert "detail" in error_data
            assert "error_code" in error_data
            assert error_data["error_code"] == "MALFORMED_HEADER"

    @pytest.mark.parametrize(
        "header_value,expected_error_code",
        [
            (None, "MISSING_TOKEN"),  # No header
            ("", "MALFORMED_HEADER"),  # Empty header
            ("Basic abc123", "MALFORMED_HEADER"),  # Wrong scheme
            ("Bearer", "MALFORMED_HEADER"),  # Missing token part
            ("bearer token123", "MALFORMED_HEADER"),  # Lowercase "bearer"
        ],
    )
    def test_various_malformed_headers(
        self, client, test_token, header_value, expected_error_code
    ):
        """Verify various malformed header formats return appropriate errors."""
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            headers = {}
            if header_value is not None:
                headers["Authorization"] = header_value

            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers=headers,
            )

            # Verify authentication failed
            assert response.status_code == 401

            # Verify correct error code
            error_data = response.json()
            assert error_data["error_code"] == expected_error_code

    def test_token_with_whitespace_is_stripped(self, client, test_token):
        """Verify token with leading/trailing whitespace is handled correctly."""
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Token with extra whitespace
            token_with_whitespace = f"  {test_token}  "

            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_with_whitespace}"},
            )

            # Should succeed (whitespace is stripped)
            assert response.status_code == 200

    def test_streaming_mode_requires_authentication(self, client, test_token):
        """Verify streaming mode also requires authentication."""
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Try streaming without token
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": True,  # Streaming mode
                },
            )

            # Should fail with auth error
            assert response.status_code == 401

            error_data = response.json()
            assert error_data["error_code"] == "MISSING_TOKEN"

    def test_authentication_logs_are_not_exposed(self, client, test_token):
        """Verify authentication errors don't expose sensitive information.

        This test ensures error messages don't leak:
        - Token values (neither provided nor expected)
        - Internal system details
        - Timing information that could aid attacks
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            # Make request with wrong token
            wrong_token = "b" * 64
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {wrong_token}"},
            )

            # Verify error response doesn't contain tokens
            response_text = response.text.lower()
            assert test_token.lower() not in response_text
            assert wrong_token.lower() not in response_text

            # Verify error message is generic (doesn't reveal why validation failed)
            error_data = response.json()
            detail = error_data["detail"].lower()

            # Should not reveal specifics like:
            # - "Expected token: ..." (leaks expected token)
            # - "Your token: ..." (confirms token format)
            # - "Token differs at position..." (timing attack info)
            assert "expected token" not in detail
            assert "your token" not in detail
            assert "position" not in detail
