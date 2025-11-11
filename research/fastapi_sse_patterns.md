# FastAPI SSE (Server-Sent Events) Implementation Patterns

**Research compiled**: 2025-11-06
**FastAPI version**: 0.115+
**Key libraries**: `sse-starlette`, `httpx-sse`

## Table of Contents

1. [SSE Response Format](#1-sse-response-format)
2. [Async Generator Patterns](#2-async-generator-patterns)
3. [Connection Management](#3-connection-management)
4. [Production Concerns](#4-production-concerns)
5. [Testing Strategies](#5-testing-strategies)

---

## 1. SSE Response Format

### Proper Headers

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.get("/stream")
async def stream_events():
    async def event_generator():
        for i in range(10):
            yield f"data: Message {i}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

**Key headers:**
- `Content-Type: text/event-stream` (set by `media_type` parameter)
- `Cache-Control: no-cache` - prevent caching of SSE stream
- `Connection: keep-alive` - maintain persistent connection
- `X-Accel-Buffering: no` - disable nginx proxy buffering if behind nginx

### SSE Message Format

SSE messages follow this structure:
```
event: <event-type>\n
data: <message-content>\n
id: <event-id>\n
retry: <reconnect-time-ms>\n
\n
```

**Basic format** (data only):
```python
yield f"data: {message}\n\n"  # Two newlines mark end of event
```

**With event type**:
```python
yield f"event: token\ndata: {token}\n\n"
```

**Complete format** (all fields):
```python
yield f"event: update\nid: {event_id}\ndata: {json_data}\nretry: 5000\n\n"
```

### Multiple Event Types Example

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json
import asyncio

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(query: str):
    async def generate():
        # Stage 1: Retrieval
        yield f"event: stage\ndata: {json.dumps({'stage': 'retrieval', 'status': 'started'})}\n\n"
        await asyncio.sleep(0.5)
        yield f"event: stage\ndata: {json.dumps({'stage': 'retrieval', 'status': 'completed', 'docs_found': 5})}\n\n"

        # Stage 2: Reranking
        yield f"event: stage\ndata: {json.dumps({'stage': 'reranking', 'status': 'started'})}\n\n"
        await asyncio.sleep(0.3)
        yield f"event: stage\ndata: {json.dumps({'stage': 'reranking', 'status': 'completed', 'top_docs': 3})}\n\n"

        # Stage 3: LLM Response (streaming tokens)
        yield f"event: stage\ndata: {json.dumps({'stage': 'generation', 'status': 'started'})}\n\n"

        tokens = ["The", "answer", "is", "42"]
        for token in tokens:
            yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"
            await asyncio.sleep(0.1)

        # Done
        yield f"event: done\ndata: {json.dumps({'total_tokens': len(tokens)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 2. Async Generator Patterns

### Basic Async Generator

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

@app.get("/stream")
async def stream_endpoint(request: Request):
    async def event_generator():
        try:
            for i in range(100):
                # Check for client disconnect
                if await request.is_disconnected():
                    print(f"Client disconnected at event {i}")
                    break

                # Generate event
                yield f"data: Event {i}\n\n"
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            # Handle cancellation (client disconnect)
            print("Generator cancelled - performing cleanup")
            raise

        finally:
            # Cleanup code always runs
            print("Generator cleanup complete")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Error Handling Pattern

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.get("/stream-with-errors")
async def stream_with_error_handling():
    async def generator():
        try:
            for i in range(10):
                if i == 5:
                    raise ValueError("Simulated error at event 5")

                yield f"data: {json.dumps({'index': i})}\n\n"
                await asyncio.sleep(0.2)

        except ValueError as e:
            # Send error as SSE event
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

        except Exception as e:
            # Handle unexpected errors
            error_data = json.dumps({"error": f"Unexpected error: {str(e)}"})
            yield f"event: error\ndata: {error_data}\n\n"

        finally:
            # Always send completion event
            yield f"event: done\ndata: {json.dumps({'completed': True})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
```

### LLM Streaming Pattern (OpenAI Example)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
import json

app = FastAPI()
client = AsyncOpenAI()

@app.post("/chat")
async def chat_stream(messages: list[dict]):
    async def generate():
        try:
            stream = await client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                stream=True
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    # Send token event
                    yield f"event: token\ndata: {json.dumps({'content': delta.content})}\n\n"

            # Send completion event
            yield f"event: done\ndata: {json.dumps({'finished': True})}\n\n"

        except Exception as e:
            # Send error event
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 3. Connection Management

### Client Disconnect Detection

**Primary method**: Use `await request.is_disconnected()` in your generator loop.

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

@app.get("/monitored-stream")
async def monitored_stream(request: Request):
    async def event_generator():
        events_sent = 0
        max_events = 100

        while events_sent < max_events:
            # Check if client disconnected
            if await request.is_disconnected():
                print(f"Client disconnected after {events_sent} events")
                break

            yield f"data: Event {events_sent}\n\n"
            events_sent += 1
            await asyncio.sleep(0.5)

        print(f"Stream completed. Total events sent: {events_sent}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Important notes:**
- `await request.is_disconnected()` returns `True` when client closes connection
- Not all disconnects are detected immediately (network failures may delay detection)
- Always check in loops to prevent infinite streams to disconnected clients

### Timeout Handling

Using `sse-starlette` library (recommended for production):

```python
from sse_starlette import EventSourceResponse
from fastapi import FastAPI, Request
import asyncio

app = FastAPI()

@app.get("/stream-with-timeout")
async def stream_with_timeout(request: Request):
    async def event_generator():
        for i in range(100):
            if await request.is_disconnected():
                break

            yield {"data": f"Event {i}"}
            await asyncio.sleep(0.5)

    return EventSourceResponse(
        event_generator(),
        send_timeout=30,  # Timeout after 30s of no send activity
        headers={"Cache-Control": "no-cache"}
    )
```

### Resource Cleanup Pattern

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

# Simulated resource (e.g., database connection, file handle)
class Resource:
    def __init__(self, name: str):
        self.name = name
        print(f"Resource {name} acquired")

    def close(self):
        print(f"Resource {self.name} released")

@app.get("/stream-with-resources")
async def stream_with_resources(request: Request):
    async def event_generator():
        resource = Resource("stream-resource")

        try:
            for i in range(100):
                if await request.is_disconnected():
                    print("Client disconnected - cleaning up")
                    break

                yield f"data: Event {i}\n\n"
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            print("Stream cancelled - cleaning up")
            raise

        finally:
            # Always cleanup resources
            resource.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

---

## 4. Production Concerns

### Memory Management

**Problem**: Each SSE connection maintains a buffer in memory. With many concurrent connections, this can cause memory issues.

**Solution**: Implement connection limiting with semaphore:

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

# Global semaphore to limit concurrent SSE connections
MAX_CONNECTIONS = 100
connection_semaphore = asyncio.Semaphore(MAX_CONNECTIONS)

@app.get("/limited-stream")
async def limited_stream(request: Request):
    # Try to acquire connection slot
    if connection_semaphore.locked():
        raise HTTPException(status_code=503, detail="Too many active connections")

    async def event_generator():
        async with connection_semaphore:
            print(f"Active connections: {MAX_CONNECTIONS - connection_semaphore._value}")

            try:
                for i in range(100):
                    if await request.is_disconnected():
                        break

                    yield f"data: Event {i}\n\n"
                    await asyncio.sleep(0.5)

            finally:
                print(f"Connection released. Active: {MAX_CONNECTIONS - connection_semaphore._value}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Concurrent Stream Handling

**Best practices for 10+ simultaneous connections:**

1. **Use ASGI server with async support** (Uvicorn, Hypercorn):
   ```bash
   uvicorn main:app --workers 4 --loop uvloop
   ```

2. **Monitor active connections**:
   ```python
   from collections import Counter

   # Track active streams
   active_streams = Counter()

   @app.get("/stream")
   async def stream(request: Request):
       stream_id = id(request)

       async def generator():
           active_streams[stream_id] += 1
           print(f"Active streams: {sum(active_streams.values())}")

           try:
               for i in range(100):
                   if await request.is_disconnected():
                       break
                   yield f"data: Event {i}\n\n"
                   await asyncio.sleep(0.5)
           finally:
               active_streams[stream_id] -= 1

       return StreamingResponse(generator(), media_type="text/event-stream")
   ```

3. **Use HTTP/2** for better connection multiplexing:
   - HTTP/1.1: ~6 connections per origin (browser limit)
   - HTTP/2: Hundreds of streams over single connection

### Production Deployment Checklist

```python
from sse_starlette import EventSourceResponse
from fastapi import FastAPI, Request
import asyncio

app = FastAPI()

@app.get("/production-stream")
async def production_stream(request: Request):
    async def event_generator():
        try:
            event_count = 0
            max_events = 1000
            idle_timeout = 30  # seconds

            while event_count < max_events:
                # Disconnect check
                if await request.is_disconnected():
                    break

                # Your event generation logic here
                yield {"data": f"Event {event_count}"}
                event_count += 1

                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            # Client disconnect or timeout
            raise

        except Exception as e:
            # Log error but don't crash
            print(f"Error in stream: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(
        event_generator(),
        send_timeout=30,  # Timeout idle sends
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx compatibility
        }
    )
```

**Nginx configuration** (if using nginx as reverse proxy):

```nginx
location /stream {
    proxy_pass http://localhost:8000;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
}
```

---

## 5. Testing Strategies

### Test Setup with httpx

**Install dependencies:**
```bash
pip install httpx httpx-sse pytest pytest-asyncio
```

**pytest.ini configuration:**
```ini
[pytest]
asyncio_mode = auto
```

### Basic Test Example

```python
# test_sse.py
import pytest
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from main import app  # Your FastAPI app

@pytest.mark.asyncio
async def test_basic_sse_stream():
    """Test basic SSE streaming endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/stream") as event_source:
            events = []
            async for sse in event_source.aiter_sse():
                events.append(sse.data)
                if len(events) >= 3:
                    break

            assert len(events) == 3
            assert "Event 0" in events[0]
```

### Test Multiple Event Types

```python
import pytest
import json
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from main import app

@pytest.mark.asyncio
async def test_multiple_event_types():
    """Test endpoint that sends different event types"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(
            client,
            "POST",
            "http://test/chat/stream",
            json={"query": "test question"}
        ) as event_source:
            events_by_type = {"stage": [], "token": [], "done": []}

            async for sse in event_source.aiter_sse():
                event_type = sse.event or "message"
                data = json.loads(sse.data)
                events_by_type[event_type].append(data)

                # Stop after done event
                if event_type == "done":
                    break

            # Verify we received all expected event types
            assert len(events_by_type["stage"]) > 0, "Should receive stage events"
            assert len(events_by_type["token"]) > 0, "Should receive token events"
            assert len(events_by_type["done"]) == 1, "Should receive one done event"
```

### Test Error Handling

```python
import pytest
import json
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from main import app

@pytest.mark.asyncio
async def test_error_in_stream():
    """Test that errors are properly sent as SSE events"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/stream-with-errors") as event_source:
            error_received = False

            async for sse in event_source.aiter_sse():
                if sse.event == "error":
                    error_received = True
                    error_data = json.loads(sse.data)
                    assert "error" in error_data
                    break

            assert error_received, "Should receive error event"
```

### Test Client Disconnect

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from main import app

@pytest.mark.asyncio
async def test_client_disconnect():
    """Test that server detects client disconnect"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/monitored-stream") as event_source:
            # Receive a few events
            event_count = 0
            async for sse in event_source.aiter_sse():
                event_count += 1
                if event_count >= 3:
                    break

            # Disconnect by breaking out of context manager
            assert event_count == 3

        # Wait a bit for server cleanup
        await asyncio.sleep(0.5)
```

### Test Timeout Behavior

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_stream_timeout():
    """Test that stream times out on idle connection"""
    timeout = 2  # seconds

    async with AsyncClient(
        transport=ASGITransport(app=app),
        timeout=timeout + 1
    ) as client:
        start_time = asyncio.get_event_loop().time()

        try:
            async with client.stream("GET", "http://test/stream-with-timeout") as response:
                async for line in response.aiter_lines():
                    # Don't process lines, just wait for timeout
                    pass
        except Exception as e:
            # Timeout or connection closed
            elapsed = asyncio.get_event_loop().time() - start_time
            assert elapsed >= timeout, f"Should timeout after {timeout}s"
```

### Complete Test Suite Example

```python
# test_sse_complete.py
import pytest
import json
import asyncio
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

# Test app
app = FastAPI()

@app.get("/stream")
async def stream():
    async def generate():
        for i in range(5):
            yield f"event: message\ndata: {json.dumps({'id': i})}\n\n"
            await asyncio.sleep(0.1)
        yield f"event: done\ndata: {json.dumps({'total': 5})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# Tests
@pytest.mark.asyncio
async def test_stream_all_events():
    """Test receiving all events from stream"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/stream") as event_source:
            events = [sse async for sse in event_source.aiter_sse()]

            assert len(events) == 6  # 5 messages + 1 done
            assert events[-1].event == "done"

@pytest.mark.asyncio
async def test_stream_partial_read():
    """Test reading only part of stream"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/stream") as event_source:
            events = []
            async for sse in event_source.aiter_sse():
                events.append(sse)
                if len(events) >= 2:
                    break

            assert len(events) == 2

@pytest.mark.asyncio
async def test_stream_json_parsing():
    """Test parsing JSON data from events"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(client, "GET", "http://test/stream") as event_source:
            first_event = await event_source.aiter_sse().__anext__()
            data = json.loads(first_event.data)

            assert "id" in data
            assert data["id"] == 0
```

### Running Tests

```bash
# Run all tests
pytest test_sse.py -v

# Run specific test
pytest test_sse.py::test_basic_sse_stream -v

# Run with coverage
pytest test_sse.py --cov=main --cov-report=html
```

---

## Summary of Best Practices

### ✅ DO:
1. **Always use `await request.is_disconnected()`** in generator loops
2. **Implement proper error handling** with try/except in generators
3. **Use `sse-starlette`** for production (handles edge cases)
4. **Set appropriate timeouts** to prevent hanging connections
5. **Limit concurrent connections** with semaphore
6. **Test with `httpx-sse`** instead of TestClient
7. **Include cleanup code in `finally` blocks**
8. **Send completion/error events** to signal stream end
9. **Use proper SSE format**: `event: type\ndata: content\n\n`
10. **Disable nginx buffering** for SSE endpoints

### ❌ DON'T:
1. **Don't use `TestClient`** for SSE testing (use `httpx.AsyncClient`)
2. **Don't forget `\n\n`** after each SSE message
3. **Don't skip disconnect checks** in infinite loops
4. **Don't hold resources** without cleanup
5. **Don't enable caching** on SSE endpoints
6. **Don't use sync generators** for I/O operations
7. **Don't ignore `asyncio.CancelledError`** exceptions
8. **Don't send binary data** (SSE is text-based)

---

## Additional Resources

- **sse-starlette**: https://github.com/sysid/sse-starlette
- **httpx-sse**: https://github.com/florimondmanca/httpx-sse
- **W3C SSE Specification**: https://html.spec.whatwg.org/multipage/server-sent-events.html
- **FastAPI Advanced Response**: https://fastapi.tiangolo.com/advanced/custom-response/

---

## Real-World Example: RAG Chat with Streaming

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import asyncio

app = FastAPI()

async def retrieve_documents(query: str) -> list[dict]:
    """Simulate document retrieval"""
    await asyncio.sleep(0.5)
    return [{"id": i, "content": f"Doc {i}"} for i in range(5)]

async def rerank_documents(docs: list[dict]) -> list[dict]:
    """Simulate reranking"""
    await asyncio.sleep(0.3)
    return docs[:3]  # Top 3

async def generate_llm_response(query: str, docs: list[dict]) -> AsyncGenerator[str, None]:
    """Simulate LLM token generation"""
    tokens = ["The", "answer", "based", "on", "documents", "is", "..."]
    for token in tokens:
        yield token
        await asyncio.sleep(0.1)

@app.post("/chat/stream")
async def chat_stream(request: Request, query: str):
    async def event_generator():
        try:
            # Stage 1: Retrieval
            yield f"event: stage\ndata: {json.dumps({'stage': 'retrieval', 'status': 'started'})}\n\n"

            docs = await retrieve_documents(query)

            yield f"event: stage\ndata: {json.dumps({
                'stage': 'retrieval',
                'status': 'completed',
                'doc_count': len(docs)
            })}\n\n"

            # Check disconnect
            if await request.is_disconnected():
                return

            # Stage 2: Reranking
            yield f"event: stage\ndata: {json.dumps({'stage': 'reranking', 'status': 'started'})}\n\n"

            top_docs = await rerank_documents(docs)

            yield f"event: stage\ndata: {json.dumps({
                'stage': 'reranking',
                'status': 'completed',
                'top_docs': len(top_docs)
            })}\n\n"

            if await request.is_disconnected():
                return

            # Stage 3: Generation
            yield f"event: stage\ndata: {json.dumps({'stage': 'generation', 'status': 'started'})}\n\n"

            token_count = 0
            async for token in generate_llm_response(query, top_docs):
                if await request.is_disconnected():
                    return

                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"
                token_count += 1

            # Done
            yield f"event: done\ndata: {json.dumps({
                'total_tokens': token_count,
                'sources': [doc['id'] for doc in top_docs]
            })}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

# Test for the RAG example
import pytest
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse

@pytest.mark.asyncio
async def test_rag_chat_stream():
    """Test complete RAG streaming workflow"""
    async with AsyncClient(transport=ASGITransport(app=app)) as client:
        async with aconnect_sse(
            client,
            "POST",
            "http://test/chat/stream",
            params={"query": "What is the answer?"}
        ) as event_source:
            stages_seen = set()
            tokens = []
            done_data = None

            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)

                if sse.event == "stage":
                    if data["status"] == "completed":
                        stages_seen.add(data["stage"])

                elif sse.event == "token":
                    tokens.append(data["content"])

                elif sse.event == "done":
                    done_data = data
                    break

            # Assertions
            assert "retrieval" in stages_seen
            assert "reranking" in stages_seen
            assert "generation" in stages_seen
            assert len(tokens) > 0
            assert done_data is not None
            assert "sources" in done_data
```

This example demonstrates a complete RAG (Retrieval-Augmented Generation) pipeline with:
- ✅ Multiple event types (stage, token, done, error)
- ✅ Client disconnect detection at each stage
- ✅ Error handling
- ✅ Complete test coverage
- ✅ Production-ready patterns
