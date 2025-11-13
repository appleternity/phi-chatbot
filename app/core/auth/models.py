"""Data models for API authentication.

This module defines:
- ErrorCode: Enum of authentication error codes
- AuthError: Pydantic model for authentication error responses
"""

from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Machine-readable error codes for authentication failures.

    These codes allow clients to programmatically handle different
    authentication failure scenarios.
    """

    MISSING_TOKEN = "MISSING_TOKEN"  # No Authorization header present
    INVALID_TOKEN = "INVALID_TOKEN"  # Token doesn't match expected value
    MALFORMED_HEADER = "MALFORMED_HEADER"  # Header format is not "Bearer {token}"


class AuthError(BaseModel):
    """Standardized authentication error response.

    This model is returned as the response body when authentication fails.
    It provides both human-readable error messages and machine-readable
    error codes for programmatic handling.

    Attributes:
        detail: Human-readable error message explaining what went wrong
        error_code: Machine-readable error code from ErrorCode enum

    Examples:
        >>> error = AuthError(
        ...     detail="Missing Authorization header",
        ...     error_code=ErrorCode.MISSING_TOKEN
        ... )
        >>> error.model_dump()
        {'detail': 'Missing Authorization header', 'error_code': 'MISSING_TOKEN'}
    """

    detail: str = Field(
        ...,
        description="Human-readable error message",
        min_length=1,
    )
    error_code: ErrorCode = Field(
        ...,
        description="Machine-readable error code for programmatic handling",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Missing Authorization header",
                    "error_code": "MISSING_TOKEN",
                },
                {
                    "detail": "Invalid API token",
                    "error_code": "INVALID_TOKEN",
                },
                {
                    "detail": "Invalid Authorization header format. Expected: Bearer {token}",
                    "error_code": "MALFORMED_HEADER",
                },
            ]
        }
    }
