# Data Model: API Bearer Token Authentication

**Feature**: API Bearer Token Authentication | **Date**: 2025-11-11

This document defines all data entities, validation rules, and state transitions for the authentication feature.

---

## Entities

### 1. BearerToken (Runtime)

**Description**: Represents a Bearer token extracted from an HTTP Authorization header. This is a runtime entity that exists only during request processing - not persisted.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `token_value` | `str` | Yes | The raw token string extracted from "Authorization: Bearer {token}" header |
| `is_valid` | `bool` | Yes | Result of validation against expected token |

**Validation Rules**:
- `token_value` must not be None
- `token_value` must not be empty string after `.strip()`
- `is_valid` is computed via constant-time comparison using `secrets.compare_digest()`

**Lifecycle**:
1. Created when Authorization header is parsed
2. Validated against `settings.API_BEARER_TOKEN`
3. Discarded after request completes (no persistence)

**Example**:
```python
# Valid token
BearerToken(
    token_value="abc123def456...",
    is_valid=True
)

# Invalid token
BearerToken(
    token_value="wrong-token",
    is_valid=False
)
```

---

### 2. ConfiguredToken (Configuration)

**Description**: The expected API token loaded from environment variable at application startup. Singleton instance stored in application settings.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | `str` | Yes | The expected token value from `API_BEARER_TOKEN` env var |

**Validation Rules**:
- Must be present in environment variables (app fails to start if missing)
- Must be at least 32 characters long (enforces 128-bit entropy minimum)
- Leading/trailing whitespace is automatically trimmed during validation
- Cannot be empty string after trimming

**Lifecycle**:
1. Loaded from environment when `Settings()` is instantiated
2. Validated by Pydantic validator
3. Stored in `settings.API_BEARER_TOKEN` for lifetime of application
4. Never modified after startup (immutable)

**Security Constraints**:
- Must be kept secret (never logged, never returned in responses)
- Must be generated using cryptographically secure random source (e.g., `openssl rand -hex 32`)
- Should be rotated periodically (requires service restart)

---

### 3. AuthError (Response Model)

**Description**: Standardized error response returned when authentication fails. Part of the API contract.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `detail` | `str` | Yes | Human-readable error message explaining what went wrong |
| `error_code` | `ErrorCode` | Yes | Machine-readable error code for programmatic handling |

**ErrorCode Enum**:
```python
class ErrorCode(str, Enum):
    MISSING_TOKEN = "MISSING_TOKEN"       # No Authorization header
    INVALID_TOKEN = "INVALID_TOKEN"       # Token doesn't match expected value
    MALFORMED_HEADER = "MALFORMED_HEADER" # Header format is not "Bearer {token}"
```

**Validation Rules**:
- `detail` must be non-empty string
- `error_code` must be one of the enum values
- Response must be JSON-serializable

**Error Code Mapping**:

| Error Code | HTTP Status | Trigger Condition | Example Detail Message |
|------------|-------------|-------------------|------------------------|
| `MISSING_TOKEN` | 401 | No Authorization header in request | "Missing Authorization header" |
| `INVALID_TOKEN` | 401 | Token doesn't match `settings.API_BEARER_TOKEN` | "Invalid API token" |
| `MALFORMED_HEADER` | 401 | Header is not "Bearer {token}" format | "Invalid Authorization header format. Expected: Bearer {token}" |

**Example**:
```json
{
  "detail": "Missing Authorization header",
  "error_code": "MISSING_TOKEN"
}
```

---

## Validation Rules Summary

### Token Format Validation

**Authorization Header**:
- Must be present in request headers
- Must follow format: `Authorization: Bearer {token}`
- Prefix "Bearer " is case-sensitive (must be exact)
- Token portion can contain any characters except whitespace

**Token Value**:
- Minimum length: 32 characters (enforced at configuration)
- Recommended length: 64 characters (256-bit entropy)
- Allowed characters: Any printable ASCII (typically hex or base64)
- Whitespace handling: Trimmed during configuration validation

### Validation Flow

```
1. Request arrives at /chat endpoint
   ↓
2. Extract Authorization header
   ↓
3. Check header exists
   - NO → Return AuthError(MISSING_TOKEN)
   - YES → Continue
   ↓
4. Parse header format "Bearer {token}"
   - INVALID FORMAT → Return AuthError(MALFORMED_HEADER)
   - VALID FORMAT → Extract token
   ↓
5. Compare token with settings.API_BEARER_TOKEN
   - Use secrets.compare_digest() (constant-time)
   - MISMATCH → Return AuthError(INVALID_TOKEN)
   - MATCH → Allow request
   ↓
6. Execute /chat business logic
```

---

## State Transitions

**Note**: This feature is stateless - no persistent state transitions occur.

### Request Lifecycle States

```
[Unauthenticated Request]
        ↓
  Parse Header
        ↓
    ┌───┴───┐
    ↓       ↓
[Valid]  [Invalid]
    ↓       ↓
 Process  Reject (401)
    ↓
[Complete]
```

**States**:
1. **Unauthenticated Request**: Initial state, token not yet validated
2. **Valid**: Token matches expected value, proceed to business logic
3. **Invalid**: Token missing/malformed/incorrect, return 401 error
4. **Complete**: Request processing finished, response sent

**No Persistent State**:
- No "logged in" sessions
- No token revocation tracking
- No usage statistics
- Each request is independently validated

---

## Relationships

```
┌─────────────────────┐
│  HTTP Request       │
│  Authorization:     │
│  Bearer {token}     │
└──────────┬──────────┘
           │ extracts
           ↓
    ┌──────────────┐
    │ BearerToken  │
    │ token_value  │
    │ is_valid     │
    └──────┬───────┘
           │ compares against
           ↓
    ┌──────────────────┐
    │ ConfiguredToken  │
    │ (from env var)   │
    └──────┬───────────┘
           │ result
           ↓
    ┌──────────────┐
    │ AuthError    │  (if invalid)
    │ detail       │
    │ error_code   │
    └──────────────┘
```

**Key Relationships**:
- **BearerToken ← HTTP Request**: One-to-one (each request has zero or one token)
- **BearerToken → ConfiguredToken**: Many-to-one comparison (all requests compare to same config token)
- **BearerToken → AuthError**: One-to-one (each invalid token produces exactly one error)

---

## Implementation Notes

### Pydantic Models

```python
from pydantic import BaseModel, Field
from enum import Enum

class ErrorCode(str, Enum):
    """Machine-readable error codes for authentication failures."""
    MISSING_TOKEN = "MISSING_TOKEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    MALFORMED_HEADER = "MALFORMED_HEADER"

class AuthError(BaseModel):
    """Standardized authentication error response."""
    detail: str = Field(..., description="Human-readable error message")
    error_code: ErrorCode = Field(..., description="Machine-readable error code")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "detail": "Missing Authorization header",
                    "error_code": "MISSING_TOKEN"
                },
                {
                    "detail": "Invalid API token",
                    "error_code": "INVALID_TOKEN"
                }
            ]
        }
```

### Settings Model

```python
from pydantic_settings import BaseSettings
from pydantic import Field, validator

class Settings(BaseSettings):
    API_BEARER_TOKEN: str = Field(
        ...,
        min_length=32,
        description="Bearer token for API authentication"
    )

    @validator('API_BEARER_TOKEN')
    def validate_token(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("API_BEARER_TOKEN cannot be empty")
        if len(v) < 32:
            raise ValueError("API_BEARER_TOKEN must be at least 32 characters")
        return v
```

---

## Security Considerations

1. **Constant-Time Comparison**: Always use `secrets.compare_digest()` to prevent timing attacks
2. **No Token Logging**: Never log token values (neither provided nor expected)
3. **Clear Error Messages**: Error messages help legitimate users but don't leak security info
4. **Fail-Fast Configuration**: App refuses to start without valid token configuration
5. **Stateless Design**: No session state = no session hijacking vulnerabilities

---

## Summary

This data model defines three core entities:
1. **BearerToken** (runtime): Token extracted from request
2. **ConfiguredToken** (config): Expected token from environment
3. **AuthError** (response): Standardized error format

All validation rules enforce security best practices while maintaining simplicity. The stateless design eliminates complexity and potential vulnerabilities from session management.
