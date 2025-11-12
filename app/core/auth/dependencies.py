"""FastAPI dependency injection for Bearer token authentication.

This module provides a FastAPI dependency function that can be used
to protect endpoints with Bearer token authentication.

Usage:
    from fastapi import Depends
    from app.core.auth.dependencies import verify_bearer_token

    @app.post("/protected-endpoint")
    async def protected_endpoint(token: str = Depends(verify_bearer_token)):
        # Endpoint logic here
        # token parameter contains the validated token
        return {"status": "success"}

Security Considerations:
- Uses constant-time comparison to prevent timing attacks
- Logs authentication events (success/failure) but never token values
- Returns clear error codes for different failure scenarios
- Fails fast with appropriate HTTP 401 responses

Performance:
- Stateless validation (no database lookups)
- Expected latency: <5ms for typical requests
- Thread-safe (no shared state)
"""

from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.config import settings
from app.core.auth.bearer_token import validate_bearer_token
from app.core.auth.models import AuthError, ErrorCode
from app.core.auth.logging import log_auth_success, log_auth_failure


class AuthenticationException(HTTPException):
    """Custom exception for authentication failures.

    This exception is caught by a custom handler in main.py that returns
    the error in the expected format: {'detail': '...', 'error_code': '...'}
    instead of HTTPException's nested format.
    """
    def __init__(self, error: AuthError):
        """Initialize with AuthError model.

        Args:
            error: AuthError containing detail and error_code
        """
        self.error = error
        # Call parent with status_code only (detail will be handled by exception handler)
        super().__init__(status_code=401)


# Initialize HTTPBearer security scheme
# This extracts the Authorization header and validates the "Bearer" scheme
security = HTTPBearer(auto_error=False)


async def verify_bearer_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Verify Bearer token and return validated token on success.

    This dependency function:
    1. Manually checks Authorization header for malformed cases
    2. Uses HTTPBearer for well-formed headers
    3. Validates token using constant-time comparison
    4. Logs authentication outcome (success/failure)
    5. Returns validated token on success, raises AuthenticationException on failure

    Args:
        request: FastAPI Request object to access raw headers
        credentials: HTTP Bearer credentials extracted from Authorization header

    Returns:
        str: The validated Bearer token (only if authentication succeeds)

    Raises:
        AuthenticationException: 401 Unauthorized with AuthError body for:
            - Missing Authorization header (MISSING_TOKEN)
            - Malformed Authorization header (MALFORMED_HEADER)
            - Invalid token (INVALID_TOKEN)

    Security Notes:
        - Uses constant-time comparison to prevent timing attacks
        - Never logs token values (security best practice)
        - Logs authentication events for monitoring
        - Error messages are generic to avoid information leakage

    Examples:
        >>> # Protect an endpoint
        >>> @app.post("/protected")
        >>> async def protected_endpoint(token: str = Depends(verify_bearer_token)):
        >>>     return {"message": "Access granted"}
        >>>
        >>> # Request succeeds with valid token:
        >>> # Authorization: Bearer {valid_token} → 200 OK
        >>>
        >>> # Request fails without token:
        >>> # (no header) → 401 {error_code: "MISSING_TOKEN"}
        >>>
        >>> # Request fails with wrong token:
        >>> # Authorization: Bearer {wrong_token} → 401 {error_code: "INVALID_TOKEN"}
        >>>
        >>> # Request fails with malformed header:
        >>> # Authorization: {token} → 401 {error_code: "MALFORMED_HEADER"}
    """
    # Get raw Authorization header to detect malformed cases
    # HTTPBearer returns None for both missing AND malformed, so we need to check manually
    auth_header = request.headers.get("authorization")

    # Case 1: Missing Authorization header (None means header not present)
    if auth_header is None:
        error = AuthError(
            detail="Missing Authorization header",
            error_code=ErrorCode.MISSING_TOKEN,
        )

        log_auth_failure(
            error_code=ErrorCode.MISSING_TOKEN,
            detail="No Authorization header provided",
        )

        raise AuthenticationException(error=error)

    # Case 2: Malformed header - empty string or doesn't start with "Bearer "
    # Check for proper format before HTTPBearer processes it
    if not auth_header or not auth_header.startswith("Bearer "):
        error = AuthError(
            detail="Invalid Authorization header format. Expected: Bearer {token}",
            error_code=ErrorCode.MALFORMED_HEADER,
        )

        log_auth_failure(
            error_code=ErrorCode.MALFORMED_HEADER,
            detail="Authorization header is malformed",
        )

        raise AuthenticationException(error=error)

    # Case 3: Header is well-formed but HTTPBearer returned None (shouldn't happen, but defensive)
    if credentials is None:
        error = AuthError(
            detail="Invalid Authorization header format. Expected: Bearer {token}",
            error_code=ErrorCode.MALFORMED_HEADER,
        )

        log_auth_failure(
            error_code=ErrorCode.MALFORMED_HEADER,
            detail="Authorization header parsing failed",
        )

        raise AuthenticationException(error=error)

    # Case 4: Validate token using constant-time comparison
    # Strip whitespace from provided token (expected token already stripped by settings validator)
    provided_token = credentials.credentials.strip()
    expected_token = settings.API_BEARER_TOKEN

    if not validate_bearer_token(provided_token, expected_token):
        error = AuthError(
            detail="Invalid API token",
            error_code=ErrorCode.INVALID_TOKEN,
        )

        # Log authentication failure (do NOT log token values)
        log_auth_failure(
            error_code=ErrorCode.INVALID_TOKEN,
            detail="Token validation failed",
        )

        raise AuthenticationException(error=error)

    # Success: Log authentication success (do NOT log token values)
    log_auth_success()

    # Return validated token (can be used by endpoint if needed)
    return provided_token
