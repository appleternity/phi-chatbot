"""Authentication module for API Bearer token authentication.

This module provides:
- Bearer token validation
- FastAPI dependency injection for protected endpoints
- Authentication event logging
- Error models for authentication failures

Public API:
- verify_bearer_token: FastAPI dependency for protecting endpoints
- ErrorCode: Enum of authentication error codes
- AuthError: Pydantic model for authentication error responses
"""

from app.core.auth.dependencies import verify_bearer_token
from app.core.auth.models import AuthError, ErrorCode

__all__ = [
    "verify_bearer_token",
    "AuthError",
    "ErrorCode",
]
