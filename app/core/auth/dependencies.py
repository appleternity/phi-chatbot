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

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.config import settings
from app.core.auth.bearer_token import validate_bearer_token
from app.core.auth.models import AuthError, ErrorCode
from app.core.auth.logging import log_auth_success, log_auth_failure


# Initialize HTTPBearer security scheme
# This extracts the Authorization header and validates the "Bearer" scheme
security = HTTPBearer(auto_error=False)


async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Verify Bearer token and return validated token on success.

    This dependency function:
    1. Extracts Authorization header using HTTPBearer
    2. Validates header format ("Bearer {token}")
    3. Compares token with expected value using constant-time comparison
    4. Logs authentication outcome (success/failure)
    5. Returns validated token on success, raises HTTPException on failure

    Args:
        credentials: HTTP Bearer credentials extracted from Authorization header

    Returns:
        str: The validated Bearer token (only if authentication succeeds)

    Raises:
        HTTPException: 401 Unauthorized with AuthError body for:
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
    # Case 1: Missing Authorization header
    if credentials is None:
        error = AuthError(
            detail="Missing Authorization header",
            error_code=ErrorCode.MISSING_TOKEN,
        )

        # Log authentication failure
        log_auth_failure(
            error_code=ErrorCode.MISSING_TOKEN,
            detail="No Authorization header provided",
        )

        raise HTTPException(
            status_code=401,
            detail=error.model_dump(),
        )

    # Case 2: Malformed header (HTTPBearer validates "Bearer" scheme, but check anyway)
    if not credentials.credentials:
        error = AuthError(
            detail="Invalid Authorization header format. Expected: Bearer {token}",
            error_code=ErrorCode.MALFORMED_HEADER,
        )

        # Log authentication failure
        log_auth_failure(
            error_code=ErrorCode.MALFORMED_HEADER,
            detail="Authorization header is malformed",
        )

        raise HTTPException(
            status_code=401,
            detail=error.model_dump(),
        )

    # Case 3: Validate token using constant-time comparison
    provided_token = credentials.credentials
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

        raise HTTPException(
            status_code=401,
            detail=error.model_dump(),
        )

    # Success: Log authentication success (do NOT log token values)
    log_auth_success()

    # Return validated token (can be used by endpoint if needed)
    return provided_token
