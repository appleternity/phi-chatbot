# Quick Start Guide: API Bearer Token Authentication

**Feature**: API Bearer Token Authentication | **Date**: 2025-11-11

This guide walks you through setting up and using Bearer token authentication for the medical chatbot API.

---

## For Administrators

### Step 1: Generate a Secure Token

Use OpenSSL to generate a cryptographically secure random token:

```bash
# Generate 32-byte (256-bit) token in hexadecimal format
openssl rand -hex 32
```

**Example output**:
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

**Alternative methods**:

```bash
# Using Python (64 character hex string)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Using Node.js (64 character hex string)
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Generate 48-byte (384-bit) token for extra security
openssl rand -hex 48
```

**⚠️ Security Note**:
- Save this token securely (password manager, secrets vault)
- Never commit tokens to version control
- Treat tokens like passwords - share only through secure channels

---

### Step 2: Configure Environment Variable

Set the `API_BEARER_TOKEN` environment variable with your generated token.

**Option 1: Export in terminal** (temporary, current session only):
```bash
export API_BEARER_TOKEN="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"
```

**Option 2: Add to `.env` file** (persistent, local development):
```bash
# Create or edit .env file in project root
echo 'API_BEARER_TOKEN="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"' >> .env
```

**Option 3: System environment** (persistent, production):
```bash
# Add to ~/.bashrc or ~/.zshrc for permanent setup
echo 'export API_BEARER_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc
```

**⚠️ Important**:
- Ensure `.env` is in `.gitignore` (should already be)
- For production: Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Token must be at least 64 hexadecimal characters (validation will fail otherwise)

---

### Step 3: Start the Service

Start the FastAPI application:

```bash
# Standard startup
python -m app.main

# Or with Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     🚀 Starting Medical Chatbot application...
INFO:     ✅ Session store initialized
INFO:     ✅ PostgreSQL connection established
INFO:     🎉 Application startup complete!
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**❌ Failure scenarios**:

If `API_BEARER_TOKEN` is missing or invalid, the app will fail to start:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
API_BEARER_TOKEN
  Field required [type=missing, input_value={}, input_type=dict]
```

Or if token is too short:

```
ValueError: API_BEARER_TOKEN must be at least 64 hexadecimal characters
```

**✅ Success indicator**: App starts without validation errors and displays startup messages.

---

### Step 4: Verify Authentication

Test that authentication is working:

**Test 1: Valid token** (should succeed):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin-test",
    "message": "What is aspirin used for?"
  }'
```

**Expected response** (200 OK):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Aspirin is used for...",
  "agent": "medical_rag",
  "metadata": {}
}
```

**Test 2: Missing token** (should fail):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin-test",
    "message": "What is aspirin used for?"
  }'
```

**Expected response** (401 Unauthorized):
```json
{
  "detail": "Missing Authorization header",
  "error_code": "MISSING_TOKEN"
}
```

**Test 3: Invalid token** (should fail):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer wrong-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin-test",
    "message": "What is aspirin used for?"
  }'
```

**Expected response** (401 Unauthorized):
```json
{
  "detail": "Invalid API token",
  "error_code": "INVALID_TOKEN"
}
```

---

### Step 5: Share Token with Client

Securely share the token with the API client (your backend service):

**✅ Secure methods**:
- 1Password / LastPass shared vault
- AWS Secrets Manager / Parameter Store
- HashiCorp Vault
- Encrypted email (PGP/GPG)
- In-person / secure video call

**❌ Insecure methods** (DO NOT USE):
- Slack/Teams messages (not end-to-end encrypted)
- Unencrypted email
- GitHub issues / pull requests
- Wiki pages / documentation
- Version control commits

---

## For API Clients

### Using the API

Once you receive the API token from your administrator, include it in all requests:

**HTTP Request Format**:
```
POST /chat HTTP/1.1
Host: api.example.com
Authorization: Bearer a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
Content-Type: application/json

{
  "user_id": "user123",
  "message": "What are the side effects of aspirin?"
}
```

**Key requirements**:
- ✅ Authorization header must start with "Bearer " (case-sensitive, with space)
- ✅ Token follows immediately after "Bearer "
- ✅ No extra whitespace or formatting
- ✅ Use HTTPS in production (tokens over HTTP are insecure)

---

### Language-Specific Examples

#### Python (requests)

```python
import requests

API_URL = "http://localhost:8000/chat"
API_TOKEN = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"

response = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    },
    json={
        "user_id": "user123",
        "message": "What are the side effects of aspirin?"
    }
)

if response.status_code == 200:
    print("Success:", response.json())
elif response.status_code == 401:
    error = response.json()
    print(f"Authentication failed: {error['detail']}")
    print(f"Error code: {error['error_code']}")
else:
    print(f"Unexpected error: {response.status_code}")
```

#### JavaScript (fetch)

```javascript
const API_URL = "http://localhost:8000/chat";
const API_TOKEN = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2";

async function sendChatMessage(userId, message) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      user_id: userId,
      message: message
    })
  });

  if (response.status === 200) {
    const data = await response.json();
    console.log("Success:", data);
    return data;
  } else if (response.status === 401) {
    const error = await response.json();
    console.error("Authentication failed:", error.detail);
    console.error("Error code:", error.error_code);
    throw new Error(error.detail);
  } else {
    throw new Error(`Unexpected error: ${response.status}`);
  }
}

// Usage
sendChatMessage("user123", "What are the side effects of aspirin?")
  .then(result => console.log(result))
  .catch(error => console.error(error));
```

#### cURL

```bash
# Store token in variable for reuse
export API_TOKEN="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"

# Make authenticated request
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "What are the side effects of aspirin?"
  }'
```

---

### Error Handling

Implement proper error handling for authentication failures:

```python
def handle_api_response(response):
    """Handle API response with proper error handling."""
    if response.status_code == 200:
        return response.json()

    elif response.status_code == 401:
        error = response.json()
        error_code = error.get("error_code")

        if error_code == "MISSING_TOKEN":
            # Token not included in request
            raise AuthenticationError("API token is required")

        elif error_code == "INVALID_TOKEN":
            # Token is incorrect
            raise AuthenticationError("API token is invalid - check configuration")

        elif error_code == "MALFORMED_HEADER":
            # Header format is wrong
            raise AuthenticationError("Authorization header format is incorrect")

        else:
            raise AuthenticationError(f"Unknown auth error: {error.get('detail')}")

    else:
        raise APIError(f"Unexpected status code: {response.status_code}")
```

---

## Token Rotation

### When to Rotate

Rotate the API token when:
- ✅ Token is potentially compromised (leaked in logs, exposed in code, etc.)
- ✅ Employee with token access leaves the team
- ✅ Regular security policy (e.g., every 90 days)
- ✅ Moving from development to production

### How to Rotate

1. **Generate new token**:
   ```bash
   openssl rand -hex 32
   ```

2. **Update server environment variable**:
   ```bash
   export API_BEARER_TOKEN="new-token-here"
   ```

3. **Restart the service**:
   ```bash
   # The service must restart to load the new token
   # Old token becomes invalid immediately after restart
   ```

4. **Update client configuration**:
   - Update client's environment variable or config
   - Restart client application

**⚠️ Downtime**: There will be brief downtime during restart (typically <30 seconds)

**🎯 Zero-downtime rotation** (future enhancement):
- Support for multiple active tokens
- Gradual rollover period
- Currently not supported in this implementation

---

## Troubleshooting

### Problem: "API_BEARER_TOKEN field required" error

**Cause**: Environment variable is not set

**Solution**:
```bash
# Verify variable is set
echo $API_BEARER_TOKEN

# If empty, set it
export API_BEARER_TOKEN="your-token-here"
```

---

### Problem: "API_BEARER_TOKEN must be at least 64 hexadecimal characters"

**Cause**: Token is too short or contains non-hexadecimal characters

**Solution**: Generate a new token with minimum 64 hexadecimal characters:
```bash
openssl rand -hex 32  # Generates 64-character hex string (32 bytes = 64 hex chars)
```

---

### Problem: 401 "Invalid API token" for known-valid token

**Possible causes**:
1. Token has leading/trailing whitespace
2. Token was copied incorrectly (missing characters)
3. Server was restarted with different token
4. Environment variable not loaded properly

**Solution**:
```bash
# Check exact token value (ensure no whitespace)
echo "$API_BEARER_TOKEN" | cat -A

# Verify length
echo "$API_BEARER_TOKEN" | wc -c

# Re-export without quotes (in case of quote issues)
export API_BEARER_TOKEN=a1b2c3d4e5f6g7h8...
```

---

### Problem: 401 "Malformed Authorization header"

**Cause**: Header format is incorrect

**Common mistakes**:
- ❌ `Authorization: a1b2c3d4...` (missing "Bearer ")
- ❌ `Authorization: bearer a1b2c3d4...` (lowercase "bearer")
- ❌ `Authorization: Token a1b2c3d4...` (wrong prefix)
- ❌ `Authorization:Bearer a1b2c3d4...` (missing space after colon)

**Correct format**:
- ✅ `Authorization: Bearer a1b2c3d4...` (exact format)

---

## Security Best Practices

1. **Use HTTPS in production** - Bearer tokens over HTTP can be intercepted
2. **Store tokens securely** - Use environment variables, never hard-code
3. **Rotate regularly** - Follow your security policy for token rotation
4. **Monitor for leaks** - Check logs for accidentally logged tokens
5. **Minimum token length** - Use at least 64 hexadecimal characters (256-bit entropy)
6. **Secure distribution** - Share tokens only through encrypted channels

---

## Next Steps

- ✅ Authentication is now configured and working
- 📖 See `contracts/auth-api.yaml` for full API specification
- 📊 Check application logs for authentication events
- 🔐 Set up monitoring for failed authentication attempts
- 🎯 Implement token rotation schedule (recommended: every 90 days)

---

## Support

For issues or questions:
- Check troubleshooting section above
- Review application logs: `tail -f logs/app.log`
- Verify token configuration: Test with curl examples
- Contact your system administrator for token issues
