# Quick Start: SSE Streaming Development Guide

**Feature**: SSE Streaming for Real-Time Chat Responses
**Branch**: `003-sse-streaming`
**Date**: 2025-11-06

## Overview

This guide helps developers set up, test, and debug SSE streaming functionality locally. Follow these steps to quickly validate streaming behavior without deploying to production.

---

## Prerequisites

- Python 3.11+ installed
- FastAPI development environment set up (see root `QUICKSTART.md`)
- PostgreSQL + pgvector running (`docker-compose up -d`)
- Node.js 18+ for frontend development

---

## Backend Setup

### 1. Install Dependencies

No new dependencies required - SSE uses FastAPI's built-in `StreamingResponse`:

```bash
# Already installed from pyproject.toml:
# - fastapi >= 0.115.0
# - uvicorn >= 0.32.0
# - langgraph >= 0.6.0
# - httpx >= 0.27.0 (for testing)

# Optional: Install httpx-sse for testing
pip install httpx-sse
```

### 2. Run Backend Server

```bash
# Start server with auto-reload
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Expected output:
# INFO:     Application startup complete!
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Verify backend health**:
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"0.1.0"}
```

---

## Testing SSE Streaming

### Option 1: Using curl (Quick Test)

**Test token streaming**:

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the side effects of aripiprazole?",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Expected output** (real-time stream):
```
data: {"type":"retrieval_start","content":{"stage":"retrieval","status":"started"},"timestamp":"2025-11-06T10:30:40.000Z"}

data: {"type":"retrieval_complete","content":{"stage":"retrieval","status":"complete","doc_count":"unknown"},"timestamp":"2025-11-06T10:30:41.500Z"}

data: {"type":"reranking_start","content":{"stage":"reranking","status":"started"},"timestamp":"2025-11-06T10:30:41.501Z"}

data: {"type":"token","content":"Aripiprazole","timestamp":"2025-11-06T10:30:42.100Z"}

data: {"type":"token","content":" is","timestamp":"2025-11-06T10:30:42.150Z"}

data: {"type":"token","content":" an","timestamp":"2025-11-06T10:30:42.200Z"}

...

data: {"type":"done","content":{},"timestamp":"2025-11-06T10:30:45.500Z"}
```

**Note**: The `-N` flag disables buffering, essential for seeing real-time updates.

### Option 2: Using httpx (Python Script)

Create `test_streaming.py`:

```python
"""Quick test script for SSE streaming endpoint."""

import asyncio
import json
from httpx import AsyncClient, ASGITransport
from app.main import app

async def test_streaming():
    """Test SSE streaming with httpx."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        async with client.stream(
            "POST",
            "/chat",
            json={
                "message": "What are the side effects of aripiprazole?",
                "session_id": "550e8400-e29b-41d4-a716-446655440000"
            },
            timeout=30.0
        ) as response:
            print(f"Status: {response.status_code}\n")
            print("Streaming events:\n")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])  # Remove "data: " prefix
                    event_type = data["type"]

                    if event_type == "token":
                        print(data["content"], end="", flush=True)
                    elif event_type == "done":
                        print("\n\n✅ Stream completed")
                        break
                    elif event_type == "error":
                        print(f"\n\n❌ Error: {data['content']['message']}")
                        break
                    else:
                        print(f"\n📊 Stage: {data['content']['stage']} - {data['content']['status']}")

if __name__ == "__main__":
    asyncio.run(test_streaming())
```

**Run test**:
```bash
python test_streaming.py
```

### Option 3: Using pytest (Integration Test)

Create `tests/integration/test_sse_streaming.py`:

```python
"""Integration tests for SSE streaming endpoint."""

import pytest
import json
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_token_streaming():
    """Test that tokens are streamed progressively."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        tokens = []

        async with client.stream(
            "POST",
            "/chat",
            json={
                "message": "test query",
                "session_id": "test-session-123"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])

                    if data["type"] == "token":
                        tokens.append(data["content"])
                    elif data["type"] == "done":
                        break

        assert len(tokens) > 0, "No tokens received"
        assert "".join(tokens), "Response is empty"


@pytest.mark.asyncio
async def test_stage_indicators():
    """Test that processing stages are emitted."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        stages_seen = set()

        async with client.stream(
            "POST",
            "/chat",
            json={
                "message": "test query",
                "session_id": "test-session-456"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])

                    if data["type"] in ["retrieval_start", "retrieval_complete", "reranking_start", "reranking_complete"]:
                        stages_seen.add(data["type"])
                    elif data["type"] == "done":
                        break

        assert "retrieval_start" in stages_seen
        assert "retrieval_complete" in stages_seen


@pytest.mark.asyncio
async def test_error_handling():
    """Test that errors are emitted as events."""
    # This test requires injecting an error condition
    # Implementation depends on your error simulation strategy
    pass
```

**Run tests**:
```bash
pytest tests/integration/test_sse_streaming.py -v
```

---

## Frontend Setup

### 1. Start Frontend Development Server

```bash
cd frontend
npm install  # If not already installed
npm run dev
```

**Expected output**:
```
  VITE v5.0.0  ready in 500 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

### 2. Test in Browser

1. Open http://localhost:3000
2. Enter a test message (e.g., "What are the side effects of aripiprazole?")
3. Click "Send" button
4. **Expected behavior**:
   - Button changes to "Stop" (FR-017)
   - Stage indicator shows "Retrieval..." then "Reranking..." (FR-005)
   - Tokens appear progressively in chat bubble (FR-003)
   - After completion, button reverts to "Send" (FR-020)

### 3. Test Stop Button

1. Enter a message and click "Send"
2. **While streaming**, click "Stop" button
3. **Expected behavior**:
   - Stream stops immediately (FR-018)
   - Button reverts to "Send" (FR-020)
   - Input field re-enabled (FR-020)
   - Backend logs "Stream cancelled by client" (FR-019)
   - Next message works normally (FR-021)

---

## Development Workflow

### Hot Reload Setup

**Backend (automatic with uvicorn --reload)**:
```bash
uvicorn app.main:app --reload --log-level debug
```

Any changes to `app/api/streaming.py` automatically reload the server.

**Frontend (automatic with Vite)**:
```bash
cd frontend && npm run dev
```

Changes to `src/hooks/useStreamingChat.ts` or `src/components/ChatInterface.tsx` hot-reload instantly.

### Debugging Tips

**Enable debug logging**:

`.env` file:
```bash
LOG_LEVEL=DEBUG
```

**Backend logs**:
```bash
# Watch backend logs in real-time
tail -f logs/app.log  # Or check terminal output

# Filter for streaming events
tail -f logs/app.log | grep "Stream"
```

**Frontend console**:

Open browser DevTools (F12) → Console tab:
```javascript
// Enable verbose logging in useStreamingChat hook
localStorage.setItem('DEBUG_STREAMING', 'true')
```

**Network inspection**:

DevTools → Network tab → Filter: "stream" → Click request → "EventStream" tab shows live SSE events.

---

## Testing Scenarios

### Scenario 1: Normal Streaming Flow

**Steps**:
1. Send message: "What are the side effects of aripiprazole?"
2. Observe stage transitions: retrieval → reranking → generation
3. Verify tokens appear progressively
4. Confirm completion event

**Expected timing** (Success Criteria):
- First token: <1 second (SC-001)
- Token latency: <100ms each (SC-002)
- Stage transitions: <200ms (SC-003)

### Scenario 2: User Cancellation

**Steps**:
1. Send message
2. Click "Stop" button after 2-3 tokens
3. Verify stream stops immediately
4. Send another message
5. Confirm new stream works normally

**Expected**: Conversation context preserved (SC-007, FR-021)

### Scenario 3: Network Interruption

**Steps**:
1. Send message
2. During streaming, disable network (DevTools → Network → "Offline")
3. Observe error message

**Expected**: Error displayed within 2 seconds (SC-007)

### Scenario 4: Concurrent Sessions

**Steps**:
1. Open 3 browser tabs
2. Send different messages in each tab simultaneously
3. Verify all streams work without interference

**Expected**: All sessions stream correctly (SC-006)

---

## Troubleshooting

### Problem: Connection Refused

**Symptoms**: `curl` or frontend shows "Connection refused"

**Solutions**:
```bash
# Check backend is running
curl http://localhost:8000/health

# Check PostgreSQL is running
docker ps | grep postgres

# Restart backend with verbose logging
LOG_LEVEL=DEBUG python -m app.main
```

### Problem: No Tokens Appearing

**Symptoms**: Stage events work, but no tokens emitted

**Debugging**:
1. Check backend logs for "on_chat_model_stream" events:
   ```bash
   tail -f logs/app.log | grep "chat_model"
   ```

2. Verify LLM API key is set:
   ```bash
   echo $OPENAI_API_KEY  # or check .env file
   ```

3. Test non-streaming endpoint first:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"test","session_id":"test-123"}'
   ```

### Problem: Tokens Delayed/Buffered

**Symptoms**: Tokens appear in batches instead of real-time

**Solutions**:

**1. Nginx buffering (production)**:
```nginx
# /etc/nginx/sites-available/default
location /chat {
    proxy_pass http://localhost:8000;
    proxy_buffering off;          # Critical!
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
}
```

**2. uvicorn configuration**:
```bash
# Ensure --timeout-keep-alive is sufficient
uvicorn app.main:app --timeout-keep-alive 65
```

**3. Frontend buffering**:
```typescript
// Ensure ReadableStream is not buffered
const reader = response.body!.getReader();
const decoder = new TextDecoder();

// Process chunks immediately (no accumulation)
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  processChunkImmediately(decoder.decode(value));  // Don't buffer!
}
```

### Problem: Stop Button Not Working

**Symptoms**: Clicking stop doesn't cancel stream

**Debugging**:
1. Check `AbortController` is created:
   ```typescript
   console.log("AbortController:", abortControllerRef.current);
   ```

2. Verify `signal` is passed to `fetch()`:
   ```typescript
   await fetch("/chat", {
     signal: abortControllerRef.current.signal  // Required!
   });
   ```

3. Check backend detects cancellation:
   ```python
   # Should see this in logs
   logger.info("Stream cancelled by client")
   ```

### Problem: "Stream timeout" Errors

**Symptoms**: Requests fail after 30 seconds

**Solutions**:

**1. Adjust timeout** (if needed for long queries):
```python
# app/api/streaming.py
async with asyncio.timeout(60):  # Increase from 30 to 60 seconds
    async for event in graph.astream_events(...):
        ...
```

**2. Check LLM API latency**:
```bash
# Test raw LLM speed
time curl -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model":"qwen/qwen3-max","messages":[{"role":"user","content":"test"}]}'
```

---

## Performance Monitoring

### Latency Measurement

**Backend**:
```python
# app/api/streaming.py
import time

start_time = time.time()
first_token_sent = False

async for event in graph.astream_events(...):
    if event["event"] == "on_chat_model_stream" and not first_token_sent:
        first_token_latency = time.time() - start_time
        logger.info(f"⏱️ First token latency: {first_token_latency:.3f}s")
        first_token_sent = True
```

**Expected**: <1.0s (SC-001)

**Frontend**:
```typescript
const startTime = performance.now();

async for (const event of streamEvents()) {
  if (event.type === "token" && !firstTokenReceived) {
    const latency = performance.now() - startTime;
    console.log(`⏱️ First token latency: ${latency.toFixed(0)}ms`);
    firstTokenReceived = true;
  }
}
```

### Concurrent Session Testing

**Load test script** (`test_concurrent_streams.py`):

```python
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def stream_message(session_id: str, message: str):
    """Single streaming request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("POST", "/chat", json={"message": message, "session_id": session_id}) as response:
            async for line in response.aiter_lines():
                if '"type":"done"' in line:
                    break

async def test_concurrent_streams(num_sessions: int = 10):
    """Test multiple concurrent streams."""
    tasks = [
        stream_message(f"session-{i}", f"Query {i}")
        for i in range(num_sessions)
    ]

    start_time = asyncio.get_event_loop().time()
    await asyncio.gather(*tasks)
    duration = asyncio.get_event_loop().time() - start_time

    print(f"✅ {num_sessions} concurrent streams completed in {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_concurrent_streams(10))
```

**Expected**: All streams complete without errors (SC-006)

---

## Next Steps

1. ✅ Verify backend streaming works with curl
2. ✅ Test token latency meets <1s first token requirement
3. ✅ Validate frontend SSE consumption
4. ✅ Test stop button and cancellation
5. ✅ Run concurrent session load test
6. ⏳ Deploy to staging environment
7. ⏳ Monitor production metrics (latency, error rate)

---

## References

- **Spec**: `specs/003-sse-streaming/spec.md`
- **Data Model**: `specs/003-sse-streaming/data-model.md`
- **Contracts**: `specs/003-sse-streaming/contracts/`
- **Research**: `specs/003-sse-streaming/research.md`
- **Root Quick Start**: `QUICKSTART.md` (general setup)
