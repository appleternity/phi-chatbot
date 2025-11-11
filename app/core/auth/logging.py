"""Authentication event logging utilities.

This module provides structured logging for authentication events with
security best practices:

- Logs authentication successes and failures
- NEVER logs token values (security requirement)
- Includes client information for audit trails
- Uses structured logging for cloud monitoring integration

Security Considerations:
- Token values are NEVER logged (neither provided nor expected)
- Only logs authentication outcomes (success/failure)
- Includes minimal client information for auditing
- Designed for integration with cloud monitoring (CloudWatch, Stackdriver, etc.)

Usage:
    from app.core.auth.logging import log_auth_success, log_auth_failure
    from app.core.auth.models import ErrorCode

    # Log successful authentication
    log_auth_success(client_ip="192.168.1.1", endpoint="/chat")

    # Log authentication failure
    log_auth_failure(
        error_code=ErrorCode.INVALID_TOKEN,
        client_ip="192.168.1.1",
        endpoint="/chat"
    )
"""

import logging
from typing import Optional

from app.core.auth.models import ErrorCode

# Use module-level logger for authentication events
logger = logging.getLogger(__name__)


def log_auth_success(
    client_ip: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> None:
    """Log successful authentication event.

    This function logs authentication successes for audit trails and
    security monitoring. It does NOT log token values.

    Args:
        client_ip: Client IP address (for audit trail)
        endpoint: Requested endpoint (for context)

    Examples:
        >>> log_auth_success(client_ip="192.168.1.1", endpoint="/chat")
        # Logs: INFO - Authentication successful client_ip=192.168.1.1 endpoint=/chat

    Security Notes:
        - Does NOT log token values (security requirement)
        - Logs only authentication outcome and context
        - Suitable for cloud monitoring integration
    """
    logger.info(
        "Authentication successful",
        extra={
            "event_type": "auth_success",
            "client_ip": client_ip,
            "endpoint": endpoint,
        },
    )


def log_auth_failure(
    error_code: ErrorCode,
    client_ip: Optional[str] = None,
    endpoint: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Log authentication failure event.

    This function logs authentication failures for security monitoring
    and incident response. It does NOT log token values.

    Args:
        error_code: The specific error code (MISSING_TOKEN, INVALID_TOKEN, etc.)
        client_ip: Client IP address (for audit trail)
        endpoint: Requested endpoint (for context)
        detail: Additional error details (optional, for debugging)

    Examples:
        >>> log_auth_failure(
        ...     error_code=ErrorCode.INVALID_TOKEN,
        ...     client_ip="192.168.1.1",
        ...     endpoint="/chat",
        ...     detail="Token validation failed"
        ... )
        # Logs: WARNING - Authentication failed error_code=INVALID_TOKEN
        #                 client_ip=192.168.1.1 endpoint=/chat

    Security Notes:
        - Does NOT log token values (security requirement)
        - Logs error codes for programmatic monitoring
        - Suitable for alerting on repeated failures
        - Compatible with cloud monitoring systems
    """
    logger.warning(
        "Authentication failed",
        extra={
            "event_type": "auth_failure",
            "error_code": error_code.value,
            "client_ip": client_ip,
            "endpoint": endpoint,
            "detail": detail,
        },
    )
