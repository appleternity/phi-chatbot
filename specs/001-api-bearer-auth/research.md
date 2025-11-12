# Research: API Bearer Token Authentication

**Feature**: API Bearer Token Authentication | **Date**: 2025-11-11

This document resolves all NEEDS CLARIFICATION items from the Technical Context and provides research findings for implementation decisions.

---

## 1. FastAPI Security Best Practices

### Decision
Use FastAPI `Depends()` with a custom dependency function for Bearer token validation.

### Rationale
- **Dependency Injection**: FastAPI's dependency system provides clean separation of authentication logic from business logic
- **Automatic OpenAPI Documentation**: `HTTPBearer` from `fastapi.security` auto-generates security schema in OpenAPI docs
- **Testability**: Dependencies can be overridden in tests using `app.dependency_overrides`
- **Reusability**: Single `verify_bearer_token` dependency can protect multiple endpoints
- **Error Handling**: Raising `HTTPException(401)` in dependency automatically returns proper error response

### Alternatives Considered

**Middleware Approach**:
- **Pros**: Runs before all requests, global protection
- **Cons**:
  - Less granular control (all-or-nothing for entire app)
  - Harder to exclude specific endpoints (e.g., /health)
  - More complex testing (requires full app setup)
  - Violates principle of explicit dependencies

**Decorator Pattern**:
- **Pros**: Python-native pattern
- **Cons**:
  - Not idiomatic FastAPI
  - Doesn't integrate with OpenAPI documentation
  - Harder to test and override

### Implementation Pattern

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Validate Bearer token and return token value if valid."""
    # Validation logic here
    pass

@app.post("/chat")
async def chat(
    request: ChatRequest,
    token: str = Depends(verify_bearer_token)  # Auth happens here
):
    # Business logic only runs if auth succeeds
    pass
```

**Key Findings**:
- `HTTPBearer` automatically extracts token from `Authorization: Bearer {token}` header
- Returns `HTTPAuthorizationCredentials` with `.credentials` containing token string
- Automatically raises 403 if header format is invalid (we'll customize to 401)
- Dependency runs before endpoint logic, ensuring authentication-first execution

---

## 2. Constant-Time Comparison

### Decision
Use Python's `secrets.compare_digest()` for token comparison.

### Rationale
- **Timing Attack Prevention**: Normal string equality (`==`) short-circuits on first mismatch, leaking timing information
- **Constant Time**: `compare_digest()` always compares full strings regardless of match/mismatch position
- **Standard Library**: No external dependencies required
- **Minimal Performance Cost**: ~0.1-0.5 microseconds overhead vs regular comparison (negligible for our <5ms budget)

### Alternatives Considered

**Regular String Comparison (`==`)**:
- **Pros**: Faster, simpler
- **Cons**:
  - Vulnerable to timing attacks (attacker can guess token byte-by-byte)
  - Not acceptable for security-sensitive comparisons
  - Industry best practice mandates constant-time for secrets

**Third-party Libraries (e.g., `cryptography`)**:
- **Pros**: Additional security utilities
- **Cons**:
  - Unnecessary dependency for simple token comparison
  - `secrets` module is sufficient and stdlib

### Implementation Pattern

```python
import secrets

def validate_token(provided_token: str, expected_token: str) -> bool:
    """
    Validate token using constant-time comparison.

    Returns True if tokens match, False otherwise.
    Prevents timing attacks by comparing all bytes regardless of match.
    """
    # Both tokens must be non-empty strings
    if not provided_token or not expected_token:
        return False

    # Constant-time comparison
    return secrets.compare_digest(provided_token, expected_token)
```

**Key Findings**:
- Works with any string type (bytes or str)
- Returns `bool` (True if equal, False otherwise)
- Performance: ~500 nanoseconds for 64-character token (well under 5ms budget)
- Security: Immune to timing analysis attacks

**Timing Attack Explanation**:
Without constant-time comparison, an attacker can:
1. Try token "AAAA..." - fails at position 0 (100μs)
2. Try token "BAAA..." - fails at position 0 (100μs)
3. Try token "xAAA..." - fails at position 1 (110μs) ← First byte correct!
4. Repeat to guess entire token byte-by-byte

With `compare_digest()`: All comparisons take same time regardless of match position.

---

## 3. Environment Variable Loading

### Decision
Load `API_BEARER_TOKEN` at application startup using Pydantic Settings with fail-fast validation.

### Rationale
- **Fail-Fast**: App refuses to start if token is missing or invalid (prevents accidental deployment without auth)
- **Pydantic Validation**: Automatic type checking, trimming, and validation
- **Single Load**: Token loaded once at startup, stored in app settings (no repeated env reads)
- **Existing Pattern**: Project already uses Pydantic Settings in `app/config.py`
- **Testability**: Easy to override settings in tests

### Alternatives Considered

**Loading on Each Request**:
- **Pros**: Could detect env changes without restart
- **Cons**:
  - Performance overhead (os.getenv() on every request)
  - Violates stateless design principle
  - Inconsistent behavior if env changes mid-operation
  - No validation until first request

**Configuration File**:
- **Pros**: More structured configuration
- **Cons**:
  - Secrets in version control (unless .gitignored, but then deployment complexity)
  - Environment variables are industry standard for secrets
  - Adds unnecessary complexity

### Implementation Pattern

```python
# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field, validator

class Settings(BaseSettings):
    # Existing settings...

    API_BEARER_TOKEN: str = Field(
        ...,  # Required field
        min_length=32,  # Enforce minimum security
        description="Bearer token for API authentication"
    )

    @validator('API_BEARER_TOKEN')
    def validate_token(cls, v):
        """Trim whitespace and validate token."""
        v = v.strip()
        if not v:
            raise ValueError("API_BEARER_TOKEN cannot be empty")
        if len(v) < 32:
            raise ValueError("API_BEARER_TOKEN must be at least 32 characters")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()  # Fails immediately if validation fails
```

**Startup Sequence**:
1. Application imports `app.config`
2. `Settings()` instantiation reads environment variables
3. Pydantic validates `API_BEARER_TOKEN` (required, min_length, trimmed)
4. If validation fails → immediate exception, app doesn't start
5. If validation succeeds → token available in `settings.API_BEARER_TOKEN`

**Key Findings**:
- FastAPI lifespan manager is not needed for env loading (happens at import time)
- Pydantic validators run automatically on Settings instantiation
- `.strip()` in validator handles whitespace edge case from spec
- `min_length=32` enforces security best practice (128-bit entropy minimum)

---

## 4. Testing Strategy for Security Features

### Decision
Three-tier testing approach: Unit → Integration → Contract tests.

### Rationale
- **Unit Tests**: Fast, isolated testing of token validation logic
- **Integration Tests**: Full HTTP request/response cycle with FastAPI TestClient
- **Contract Tests**: Verify API contract compliance (error response formats)
- **Security-Specific Tests**: Cover edge cases, timing attacks, concurrent requests

### Testing Layers

#### Layer 1: Unit Tests (`tests/unit/test_bearer_auth.py`)

**Purpose**: Test token validation logic in isolation without HTTP layer.

**Test Cases**:
- ✅ Valid token matches expected token
- ✅ Invalid token rejected
- ✅ Empty token rejected
- ✅ Whitespace-only token rejected
- ✅ None/null token rejected
- ✅ Token with leading/trailing whitespace (after trim) validates correctly
- ✅ Constant-time comparison (verify `secrets.compare_digest` is used)

**Example**:
```python
def test_valid_token_passes():
    expected = "abc123"
    provided = "abc123"
    assert validate_token(provided, expected) is True

def test_invalid_token_fails():
    expected = "abc123"
    provided = "wrong"
    assert validate_token(provided, expected) is False
```

#### Layer 2: Integration Tests (`tests/integration/test_chat_auth.py`)

**Purpose**: Test full authentication flow through FastAPI application.

**Test Cases**:
- ✅ Valid token → 200 OK with chat response
- ✅ Missing Authorization header → 401 with "Missing Authorization header"
- ✅ Invalid token → 401 with "Invalid API token"
- ✅ Malformed header ("Token {token}") → 401 with format error
- ✅ Malformed header (just "{token}") → 401 with format error
- ✅ Empty Bearer token ("Bearer ") → 401 with invalid token
- ✅ Concurrent requests with same token → all succeed
- ✅ Token with whitespace → 401 (after trim, doesn't match)

**Example**:
```python
from fastapi.testclient import TestClient

def test_valid_token_authenticates(client: TestClient):
    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer valid-test-token"},
        json={"user_id": "test", "message": "hello"}
    )
    assert response.status_code == 200

def test_missing_token_returns_401(client: TestClient):
    response = client.post(
        "/chat",
        json={"user_id": "test", "message": "hello"}
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "MISSING_TOKEN"
```

#### Layer 3: Contract Tests (`tests/contract/test_auth_contract.py`)

**Purpose**: Verify error response formats match OpenAPI contract.

**Test Cases**:
- ✅ 401 response has `detail` field (string)
- ✅ 401 response has `error_code` field (enum: MISSING_TOKEN, INVALID_TOKEN, MALFORMED_HEADER)
- ✅ Error codes match expected values for each scenario
- ✅ Response Content-Type is application/json

**Example**:
```python
def test_auth_error_response_schema(client: TestClient):
    response = client.post("/chat", json={"user_id": "test", "message": "hi"})
    assert response.status_code == 401
    data = response.json()

    # Contract validation
    assert "detail" in data
    assert "error_code" in data
    assert isinstance(data["detail"], str)
    assert data["error_code"] in ["MISSING_TOKEN", "INVALID_TOKEN", "MALFORMED_HEADER"]
```

### Security-Specific Test Cases

**Concurrent Requests**:
- Send 100 simultaneous requests with valid token
- Verify all succeed (no race conditions)
- Verify response times remain under 5ms p99

**Performance Validation**:
- Measure token validation overhead
- Ensure <5ms p99 latency (as per success criteria)

**Timing Attack Resistance** (documentation test):
- Document that `secrets.compare_digest()` is used
- No explicit timing measurement needed (stdlib guarantees constant-time)

### Test Fixtures

```python
# conftest.py
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def valid_token():
    return "test-token-1234567890abcdef1234567890abcdef"

@pytest.fixture
def app_with_auth(valid_token):
    """App instance with test token configured."""
    from app.main import app
    from app.config import settings

    # Override settings for testing
    original_token = settings.API_BEARER_TOKEN
    settings.API_BEARER_TOKEN = valid_token

    yield app

    # Restore original
    settings.API_BEARER_TOKEN = original_token

@pytest.fixture
def client(app_with_auth):
    return TestClient(app_with_auth)
```

### Coverage Goals
- **Unit Tests**: 100% coverage of auth module
- **Integration Tests**: All user stories + edge cases from spec
- **Contract Tests**: All error response formats

---

## Summary

All research tasks complete. Key decisions:

1. **Authentication Pattern**: FastAPI `Depends()` with `HTTPBearer` security scheme
2. **Token Comparison**: `secrets.compare_digest()` for constant-time validation
3. **Configuration**: Pydantic Settings with fail-fast validation at startup
4. **Testing**: Three-tier approach (unit/integration/contract) with security-specific tests

All NEEDS CLARIFICATION items resolved. Ready for Phase 1 (Design & Contracts).
