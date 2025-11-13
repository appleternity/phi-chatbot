"""Unit tests for Bearer token validation logic.

These tests verify the token validation function behaves correctly
for all input scenarios, including security requirements like
constant-time comparison.

Test Coverage:
- Valid token validation
- Invalid token rejection
- Empty/None token handling
- Whitespace handling
- Constant-time comparison behavior
"""

import pytest

from app.core.auth.bearer_token import validate_bearer_token


class TestValidateBearerToken:
    """Unit tests for validate_bearer_token function."""

    # Test fixture: a valid token for testing
    VALID_TOKEN = "abc123def456"
    EXPECTED_TOKEN = "abc123def456"

    def test_valid_token_returns_true(self):
        """Verify valid token returns True."""
        result = validate_bearer_token(self.VALID_TOKEN, self.EXPECTED_TOKEN)
        assert result is True

    def test_invalid_token_returns_false(self):
        """Verify invalid token returns False."""
        result = validate_bearer_token("wrong_token", self.EXPECTED_TOKEN)
        assert result is False

    def test_empty_provided_token_returns_false(self):
        """Verify empty provided token returns False."""
        result = validate_bearer_token("", self.EXPECTED_TOKEN)
        assert result is False

    def test_empty_expected_token_returns_false(self):
        """Verify empty expected token returns False."""
        result = validate_bearer_token(self.VALID_TOKEN, "")
        assert result is False

    def test_none_provided_token_returns_false(self):
        """Verify None provided token returns False."""
        result = validate_bearer_token(None, self.EXPECTED_TOKEN)  # type: ignore
        assert result is False

    def test_none_expected_token_returns_false(self):
        """Verify None expected token returns False."""
        result = validate_bearer_token(self.VALID_TOKEN, None)  # type: ignore
        assert result is False

    def test_whitespace_only_provided_token_returns_false(self):
        """Verify whitespace-only provided token returns False after stripping."""
        result = validate_bearer_token("   ", self.EXPECTED_TOKEN)
        assert result is False

    def test_whitespace_only_expected_token_returns_false(self):
        """Verify whitespace-only expected token returns False after stripping."""
        result = validate_bearer_token(self.VALID_TOKEN, "   ")
        assert result is False

    def test_provided_token_with_whitespace_is_stripped(self):
        """Verify provided token with leading/trailing whitespace is stripped."""
        result = validate_bearer_token(f"  {self.VALID_TOKEN}  ", self.EXPECTED_TOKEN)
        assert result is True

    def test_expected_token_with_whitespace_is_stripped(self):
        """Verify expected token with leading/trailing whitespace is stripped."""
        result = validate_bearer_token(self.VALID_TOKEN, f"  {self.EXPECTED_TOKEN}  ")
        assert result is True

    def test_case_sensitive_comparison(self):
        """Verify token comparison is case-sensitive."""
        # Uppercase version should not match lowercase
        result = validate_bearer_token("ABC123", "abc123")
        assert result is False

    def test_partial_match_returns_false(self):
        """Verify partial token match returns False."""
        # Substring should not match
        result = validate_bearer_token("abc123", "abc123def456")
        assert result is False

        # Superstring should not match
        result = validate_bearer_token("abc123def456", "abc123")
        assert result is False

    def test_constant_time_comparison(self):
        """Verify constant-time comparison is used (timing attack prevention).

        This test verifies that the function uses a constant-time comparison
        algorithm by checking that hmac.compare_digest is used internally.
        We can't directly measure timing in a unit test, but we can verify
        the correct function is called.
        """
        import hmac
        from unittest.mock import patch

        with patch.object(hmac, "compare_digest", return_value=True) as mock_compare:
            validate_bearer_token(self.VALID_TOKEN, self.EXPECTED_TOKEN)

            # Verify hmac.compare_digest was called
            assert mock_compare.called
            # Verify it was called with stripped tokens
            mock_compare.assert_called_once_with(self.VALID_TOKEN, self.EXPECTED_TOKEN)

    @pytest.mark.parametrize(
        "provided,expected,should_match",
        [
            ("token123", "token123", True),  # Exact match
            ("token123", "token456", False),  # Different tokens
            ("", "token123", False),  # Empty provided
            ("token123", "", False),  # Empty expected
            ("  token123  ", "token123", True),  # Whitespace stripped
            ("TOKEN123", "token123", False),  # Case sensitive
            ("token", "token123", False),  # Partial match
        ],
    )
    def test_token_validation_scenarios(
        self, provided: str, expected: str, should_match: bool
    ):
        """Verify token validation for various scenarios."""
        result = validate_bearer_token(provided, expected)
        assert result == should_match

    def test_long_token_validation(self):
        """Verify validation works with production-length tokens (64+ chars)."""
        # Generate a realistic 64-character hex token
        long_token = "a" * 64

        # Should match itself
        assert validate_bearer_token(long_token, long_token) is True

        # Should not match slightly different token
        wrong_token = "a" * 63 + "b"
        assert validate_bearer_token(wrong_token, long_token) is False
