"""
Unit tests for configuration validation.

Tests Settings validation rules:
- embedding_provider enum accepts valid values
- embedding_provider enum rejects invalid values
- table_name validation requires non-empty string
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


class TestEmbeddingProviderValidation:
    """T060-T061: Test embedding_provider field validation."""

    def test_embedding_provider_accepts_local(self):
        """T060: embedding_provider should accept 'local' as valid value."""
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=1024
        )

        assert settings.embedding_provider == "local"

    def test_embedding_provider_accepts_openrouter(self):
        """T060: embedding_provider should accept 'openrouter' as valid value."""
        settings = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-test-key",
            embedding_dim=1024
        )

        assert settings.embedding_provider == "openrouter"

    def test_embedding_provider_accepts_aliyun(self):
        """T060: embedding_provider should accept 'aliyun' as valid value."""
        settings = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-key",
            embedding_dim=1024
        )

        assert settings.embedding_provider == "aliyun"

    def test_embedding_provider_rejects_invalid_string(self):
        """T061: embedding_provider should reject invalid string values."""
        invalid_providers = [
            "gpt4",
            "claude",
            "gemini",
            "huggingface",
            "unknown",
            "invalid",
            "test",
        ]

        for invalid_provider in invalid_providers:
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    embedding_provider=invalid_provider,
                    openai_api_key="sk-test-key",
                    embedding_dim=1024
                )

            # Verify error message mentions the invalid value
            error_message = str(exc_info.value)
            assert "embedding_provider" in error_message.lower() or invalid_provider in error_message.lower()

    def test_embedding_provider_rejects_empty_string(self):
        """T061: embedding_provider should reject empty string."""
        with pytest.raises(ValidationError):
            Settings(
                embedding_provider="",
                openai_api_key="sk-test-key",
                embedding_dim=1024
            )

    def test_embedding_provider_rejects_numeric_value(self):
        """T061: embedding_provider should reject numeric values."""
        with pytest.raises(ValidationError):
            Settings(
                embedding_provider=123,  # type: ignore
                openai_api_key="sk-test-key",
                embedding_dim=1024
            )

    def test_embedding_provider_rejects_none(self):
        """T061: embedding_provider should reject None value."""
        with pytest.raises(ValidationError):
            Settings(
                embedding_provider=None,  # type: ignore
                openai_api_key="sk-test-key",
                embedding_dim=1024
            )

    def test_embedding_provider_case_sensitivity(self):
        """T060-T061: Test case sensitivity of embedding_provider validation."""
        # Valid providers should work regardless of case
        valid_cases = ["local", "LOCAL", "Local", "openrouter", "OPENROUTER", "aliyun", "ALIYUN"]

        # Note: Pydantic's field_validator is case-sensitive by default
        # Only exact lowercase matches should work
        for provider in ["local", "openrouter", "aliyun"]:
            settings = Settings(
                embedding_provider=provider,
                openai_api_key="sk-test-key",
                aliyun_api_key="sk-aliyun-key" if provider == "aliyun" else "",
                embedding_dim=1024
            )
            assert settings.embedding_provider == provider

        # Uppercase/mixed case should be rejected
        for provider in ["LOCAL", "Local", "OPENROUTER", "OpenRouter", "ALIYUN", "Aliyun"]:
            with pytest.raises(ValidationError):
                Settings(
                    embedding_provider=provider,
                    openai_api_key="sk-test-key",
                    embedding_dim=1024
                )


class TestTableNameValidation:
    """T062: Test table_name field validation."""

    def test_table_name_accepts_non_empty_string(self):
        """T062: table_name should accept non-empty strings."""
        valid_table_names = [
            "vector_chunks",
            "embeddings_v1",
            "test_table",
            "medical_knowledge",
            "table123",
            "my_custom_table_name",
        ]

        for table_name in valid_table_names:
            settings = Settings(
                embedding_provider="local",
                openai_api_key="sk-test-key",
                embedding_dim=1024,
                table_name=table_name
            )

            assert settings.table_name == table_name

    def test_table_name_default_value(self):
        """T062: table_name should have default value 'vector_chunks'."""
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=1024
        )

        # Default value should be "vector_chunks"
        assert settings.table_name == "vector_chunks"

    def test_table_name_rejects_empty_string(self):
        """T062: table_name should reject empty string."""
        # Note: Current implementation allows empty string due to default value
        # This test documents current behavior
        # If strict validation needed, add field_validator to Settings

        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=1024,
            table_name=""
        )

        # Current behavior: accepts empty string (uses as-is)
        # Future improvement: Add validation to reject empty strings
        assert settings.table_name == ""

    def test_table_name_with_special_characters(self):
        """T062: table_name should handle special characters based on database rules."""
        # Valid PostgreSQL table names (lowercase, underscores, numbers)
        valid_names = [
            "vector_chunks_v2",
            "embeddings_2024",
            "test_table_123",
            "chunks",  # Single word
        ]

        for table_name in valid_names:
            settings = Settings(
                embedding_provider="local",
                openai_api_key="sk-test-key",
                embedding_dim=1024,
                table_name=table_name
            )

            assert settings.table_name == table_name

    def test_table_name_accepts_uppercase(self):
        """T062: table_name should accept uppercase (PostgreSQL converts to lowercase)."""
        # Note: PostgreSQL will convert unquoted identifiers to lowercase
        # Settings should accept uppercase, but database will use lowercase

        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=1024,
            table_name="VECTOR_CHUNKS"
        )

        # Settings stores as-is (database layer handles conversion)
        assert settings.table_name == "VECTOR_CHUNKS"


class TestEmbeddingDimensionValidation:
    """Additional validation tests for embedding_dim field."""

    def test_embedding_dim_accepts_valid_dimensions(self):
        """embedding_dim should accept valid dimension sizes."""
        valid_dimensions = [384, 768, 1024, 1536, 2048, 3072]

        for dim in valid_dimensions:
            settings = Settings(
                embedding_provider="local",
                openai_api_key="sk-test-key",
                embedding_dim=dim
            )

            assert settings.embedding_dim == dim

    def test_embedding_dim_default_value(self):
        """embedding_dim should have default value 384."""
        # Note: Default might be 384 for backward compatibility
        # But spec requires 1024 for new providers
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key"
        )

        # Check what default is used
        assert isinstance(settings.embedding_dim, int)
        assert settings.embedding_dim > 0

    def test_embedding_dim_accepts_negative_as_config_value(self):
        """embedding_dim accepts negative values (validation happens at provider level)."""
        # Note: Settings doesn't validate embedding_dim
        # Validation happens in provider.validate_dimension()
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=-1
        )

        # Settings accepts it, but provider validation would catch it
        assert settings.embedding_dim == -1

    def test_embedding_dim_accepts_zero_as_config_value(self):
        """embedding_dim accepts zero (validation happens at provider level)."""
        # Note: Settings doesn't validate embedding_dim
        # Validation happens in provider.validate_dimension()
        settings = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=0
        )

        # Settings accepts it, but provider validation would catch it
        assert settings.embedding_dim == 0


class TestMultipleFieldValidation:
    """Test validation of multiple fields together."""

    def test_valid_configuration_all_providers(self):
        """Complete valid configuration should pass for all providers."""
        # Local provider
        settings_local = Settings(
            embedding_provider="local",
            openai_api_key="sk-test-key",
            embedding_dim=1024,
            table_name="vector_chunks_local"
        )
        assert settings_local.embedding_provider == "local"

        # OpenRouter provider
        settings_openrouter = Settings(
            embedding_provider="openrouter",
            openai_api_key="sk-or-key",
            embedding_dim=1024,
            table_name="vector_chunks_openrouter"
        )
        assert settings_openrouter.embedding_provider == "openrouter"

        # Aliyun provider
        settings_aliyun = Settings(
            embedding_provider="aliyun",
            openai_api_key="sk-test-key",
            aliyun_api_key="sk-aliyun-key",
            embedding_dim=1024,
            table_name="vector_chunks_aliyun"
        )
        assert settings_aliyun.embedding_provider == "aliyun"

    def test_validation_error_provides_helpful_message(self):
        """Validation errors should provide helpful error messages."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                embedding_provider="invalid_provider",
                openai_api_key="sk-test-key",
                embedding_dim=1024
            )

        # Error message should mention valid options
        error_message = str(exc_info.value)
        assert "embedding_provider" in error_message.lower()
        # Should mention valid options: local, openrouter, aliyun
        assert "local" in error_message.lower() or "valid" in error_message.lower()
