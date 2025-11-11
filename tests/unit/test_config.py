"""Unit tests for Settings validation (API_BEARER_TOKEN).

These tests verify that the Settings class properly validates the
API_BEARER_TOKEN field according to security requirements.

Test Coverage:
- Valid token (≥64 hex chars) → Accepted
- Too short token → ValueError
- Non-hexadecimal characters → ValueError
- Empty token → ValueError
- Whitespace handling (leading/trailing stripped)
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettingsValidation:
    """Unit tests for Settings API_BEARER_TOKEN validation."""

    def test_valid_token_64_chars_accepted(self, monkeypatch):
        """Verify valid 64-character hex token is accepted."""
        # Set valid token (64 hex chars)
        valid_token = "a" * 64
        monkeypatch.setenv("API_BEARER_TOKEN", valid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should create settings successfully
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token

    def test_valid_token_96_chars_accepted(self, monkeypatch):
        """Verify token longer than minimum (96 chars) is accepted."""
        # Set valid long token (96 hex chars = 384-bit entropy)
        valid_token = "a" * 96
        monkeypatch.setenv("API_BEARER_TOKEN", valid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should create settings successfully
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token

    def test_token_too_short_raises_value_error(self, monkeypatch):
        """Verify token shorter than 64 chars raises ValueError."""
        # Set invalid token (only 32 chars)
        invalid_token = "a" * 32
        monkeypatch.setenv("API_BEARER_TOKEN", invalid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error mentions token length requirement
        error_str = str(exc_info.value)
        assert "64" in error_str or "hexadecimal" in error_str.lower()

    def test_non_hex_characters_raise_value_error(self, monkeypatch):
        """Verify token with non-hexadecimal characters raises ValueError."""
        # Set invalid token (contains non-hex char 'g')
        invalid_token = "a" * 63 + "g"
        monkeypatch.setenv("API_BEARER_TOKEN", invalid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error mentions hexadecimal requirement
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "hex" in error_str

    def test_empty_token_raises_value_error(self, monkeypatch):
        """Verify empty token raises ValueError."""
        # Set empty token
        monkeypatch.setenv("API_BEARER_TOKEN", "")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error mentions empty token
        error_str = str(exc_info.value).lower()
        assert "empty" in error_str or "required" in error_str

    def test_whitespace_only_token_raises_value_error(self, monkeypatch):
        """Verify whitespace-only token raises ValueError after stripping."""
        # Set whitespace-only token
        monkeypatch.setenv("API_BEARER_TOKEN", "   ")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error (empty after strip)
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error mentions empty token
        error_str = str(exc_info.value).lower()
        assert "empty" in error_str or "required" in error_str

    def test_token_with_leading_whitespace_is_stripped(self, monkeypatch):
        """Verify token with leading whitespace is stripped and accepted."""
        # Set valid token with leading whitespace
        valid_token = "a" * 64
        token_with_whitespace = f"  {valid_token}"
        monkeypatch.setenv("API_BEARER_TOKEN", token_with_whitespace)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should strip whitespace and accept
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token
        assert settings.API_BEARER_TOKEN.strip() == settings.API_BEARER_TOKEN

    def test_token_with_trailing_whitespace_is_stripped(self, monkeypatch):
        """Verify token with trailing whitespace is stripped and accepted."""
        # Set valid token with trailing whitespace
        valid_token = "a" * 64
        token_with_whitespace = f"{valid_token}  "
        monkeypatch.setenv("API_BEARER_TOKEN", token_with_whitespace)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should strip whitespace and accept
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token

    def test_token_with_surrounding_whitespace_is_stripped(self, monkeypatch):
        """Verify token with surrounding whitespace is stripped."""
        # Set valid token with surrounding whitespace
        valid_token = "a" * 64
        token_with_whitespace = f"  {valid_token}  "
        monkeypatch.setenv("API_BEARER_TOKEN", token_with_whitespace)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should strip whitespace and accept
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token

    def test_mixed_case_hex_token_accepted(self, monkeypatch):
        """Verify mixed-case hexadecimal token is accepted."""
        # Set token with mixed case (valid hex)
        valid_token = "A" * 32 + "f" * 32  # 64 chars total
        monkeypatch.setenv("API_BEARER_TOKEN", valid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should accept (hex is case-insensitive)
        settings = Settings()
        assert settings.API_BEARER_TOKEN == valid_token

    @pytest.mark.parametrize(
        "token_length,should_pass",
        [
            (63, False),  # Too short by 1
            (64, True),  # Exact minimum
            (65, True),  # Above minimum
            (128, True),  # Double minimum
            (32, False),  # Half minimum
            (0, False),  # Empty
        ],
    )
    def test_various_token_lengths(self, monkeypatch, token_length, should_pass):
        """Verify various token lengths are handled correctly."""
        # Generate token of specified length
        token = "a" * token_length
        monkeypatch.setenv("API_BEARER_TOKEN", token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        if should_pass:
            # Should create settings successfully
            settings = Settings()
            assert len(settings.API_BEARER_TOKEN) == token_length
        else:
            # Should raise validation error
            with pytest.raises(ValidationError):
                Settings()

    def test_token_with_special_characters_rejected(self, monkeypatch):
        """Verify token with special characters is rejected."""
        # Set token with special characters (not hex)
        invalid_token = "a" * 62 + "!@"  # 64 chars but contains special chars
        monkeypatch.setenv("API_BEARER_TOKEN", invalid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error mentions hexadecimal requirement
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "hex" in error_str

    def test_token_validation_error_message_is_helpful(self, monkeypatch):
        """Verify validation error messages provide clear guidance."""
        # Set invalid token (too short)
        invalid_token = "a" * 32
        monkeypatch.setenv("API_BEARER_TOKEN", invalid_token)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Should raise validation error with helpful message
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)

        # Verify error message includes:
        # 1. The requirement (64 characters)
        assert "64" in error_str

        # 2. Guidance on how to generate valid token
        assert "openssl" in error_str.lower() or "generate" in error_str.lower()
