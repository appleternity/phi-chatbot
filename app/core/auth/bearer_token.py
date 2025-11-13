"""Bearer token validation using constant-time comparison.

This module provides secure token validation that prevents timing attacks
by using secrets.compare_digest() for constant-time string comparison.

Security Considerations:
- Uses secrets.compare_digest() to prevent timing attacks
- Never logs token values (neither provided nor expected)
- Validates token format before comparison
- Fails fast on invalid input

Performance:
- Constant-time comparison: O(n) where n is token length
- No database lookups (stateless validation)
- Expected latency: <1ms for typical 64-character tokens
"""

import hmac


def validate_bearer_token(provided_token: str, expected_token: str) -> bool:
    """Validate a Bearer token using constant-time comparison.

    This function uses hmac.compare_digest() (equivalent to secrets.compare_digest())
    to prevent timing attacks. The comparison time is constant regardless of
    where the strings differ.

    Args:
        provided_token: The token extracted from the Authorization header
        expected_token: The expected token from application settings

    Returns:
        bool: True if tokens match exactly, False otherwise

    Security Notes:
        - Uses constant-time comparison to prevent timing attacks
        - Does NOT log token values (security best practice)
        - Strips whitespace before comparison (defensive programming)
        - Returns False for None or empty tokens

    Examples:
        >>> validate_bearer_token("abc123", "abc123")
        True
        >>> validate_bearer_token("wrong", "abc123")
        False
        >>> validate_bearer_token("", "abc123")
        False
        >>> validate_bearer_token("  abc123  ", "abc123")
        True

    Performance:
        - Time complexity: O(n) where n is token length
        - Typical execution time: <1ms for 64-character tokens
        - No I/O operations (pure computation)
    """
    # Handle None or empty tokens
    if not provided_token or not expected_token:
        return False

    # Strip whitespace for defensive programming
    # (settings validation should already strip, but be defensive)
    provided_token = provided_token.strip()
    expected_token = expected_token.strip()

    # Return False if either token is empty after stripping
    if not provided_token or not expected_token:
        return False

    # Use hmac.compare_digest for constant-time comparison
    # This prevents timing attacks by ensuring comparison time
    # is independent of where the strings differ
    return hmac.compare_digest(provided_token, expected_token)
