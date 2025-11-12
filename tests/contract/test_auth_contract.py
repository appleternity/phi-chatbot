"""Contract tests for authentication error response format.

These tests verify that authentication error responses conform to the
documented AuthError schema, ensuring API contract consistency for clients.

Test Coverage:
- Error response structure (detail, error_code fields)
- Error code values (MISSING_TOKEN, INVALID_TOKEN, MALFORMED_HEADER)
- JSON serialization format
- Field types and constraints
"""

import pytest
from pydantic import ValidationError

from app.core.auth.models import AuthError, ErrorCode


class TestAuthErrorContract:
    """Contract tests for AuthError response model."""

    def test_auth_error_has_required_fields(self):
        """Verify AuthError has required 'detail' and 'error_code' fields."""
        # Create valid AuthError
        error = AuthError(
            detail="Missing Authorization header",
            error_code=ErrorCode.MISSING_TOKEN,
        )

        # Verify required fields are present
        assert hasattr(error, "detail")
        assert hasattr(error, "error_code")

        # Verify values are correct
        assert error.detail == "Missing Authorization header"
        assert error.error_code == ErrorCode.MISSING_TOKEN

    def test_auth_error_detail_must_be_non_empty_string(self):
        """Verify 'detail' field must be a non-empty string."""
        # Empty string should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            AuthError(
                detail="",
                error_code=ErrorCode.MISSING_TOKEN,
            )

        # Verify error mentions 'detail' field
        errors = exc_info.value.errors()
        assert any("detail" in str(error) for error in errors)

    def test_auth_error_code_must_be_valid_enum(self):
        """Verify 'error_code' must be a valid ErrorCode enum value."""
        # Invalid error code should raise validation error
        with pytest.raises(ValidationError):
            AuthError(
                detail="Test error",
                error_code="INVALID_CODE",  # type: ignore
            )

    def test_error_code_enum_values(self):
        """Verify ErrorCode enum has expected values."""
        # Verify all expected error codes exist
        assert hasattr(ErrorCode, "MISSING_TOKEN")
        assert hasattr(ErrorCode, "INVALID_TOKEN")
        assert hasattr(ErrorCode, "MALFORMED_HEADER")

        # Verify enum values are strings
        assert ErrorCode.MISSING_TOKEN.value == "MISSING_TOKEN"
        assert ErrorCode.INVALID_TOKEN.value == "INVALID_TOKEN"
        assert ErrorCode.MALFORMED_HEADER.value == "MALFORMED_HEADER"

    def test_auth_error_json_serialization(self):
        """Verify AuthError serializes to correct JSON format."""
        error = AuthError(
            detail="Invalid API token",
            error_code=ErrorCode.INVALID_TOKEN,
        )

        # Serialize to dict (JSON format)
        error_dict = error.model_dump()

        # Verify structure matches contract
        assert "detail" in error_dict
        assert "error_code" in error_dict

        # Verify values
        assert error_dict["detail"] == "Invalid API token"
        assert error_dict["error_code"] == "INVALID_TOKEN"

        # Verify error_code is string (not enum object)
        assert isinstance(error_dict["error_code"], str)

    @pytest.mark.parametrize(
        "error_code,detail",
        [
            (ErrorCode.MISSING_TOKEN, "Missing Authorization header"),
            (ErrorCode.INVALID_TOKEN, "Invalid API token"),
            (
                ErrorCode.MALFORMED_HEADER,
                "Invalid Authorization header format. Expected: Bearer {token}",
            ),
        ],
    )
    def test_auth_error_all_error_codes(self, error_code: ErrorCode, detail: str):
        """Verify AuthError works with all defined error codes."""
        error = AuthError(detail=detail, error_code=error_code)

        # Verify error can be created and serialized
        assert error.error_code == error_code
        assert error.detail == detail

        # Verify serialization works
        error_dict = error.model_dump()
        assert error_dict["error_code"] == error_code.value
        assert error_dict["detail"] == detail

    def test_auth_error_examples_match_schema(self):
        """Verify AuthError examples in schema are valid."""
        # Get examples from schema
        schema = AuthError.model_config.get("json_schema_extra", {})
        examples = schema.get("examples", [])

        # Verify examples exist
        assert len(examples) > 0, "AuthError schema should have examples"

        # Verify each example is valid
        for example in examples:
            # Should be able to create AuthError from example
            error = AuthError(**example)

            # Verify it serializes back to same format
            error_dict = error.model_dump()
            assert error_dict["detail"] == example["detail"]
            assert error_dict["error_code"] == example["error_code"]
