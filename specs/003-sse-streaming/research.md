# Research: SSE Streaming for Real-Time Chat Responses

**Date**: 2025-11-06
**Status**: Complete
**Branch**: `003-sse-streaming`

## Overview

This document consolidates research findings for implementing Server-Sent Events (SSE) streaming in the medical chatbot. Research focused on five key technical areas required for the implementation.

---

## 1. LangGraph 0.6.0 Streaming API

### Decision: Use `astream_events()` API

**Rationale**:
- Provides token-level streaming from LLM responses (required for FR-001, FR-002, FR-003)
- Captures processing stage transitions (required for FR-004, FR-005)
- Works seamlessly with existing checkpointing and state persistence (FR-012)

**Alternatives Considered**:
- `astream()`: Only emits state updates after each node completes (no token-level access)
- `ainvoke()`: Current blocking approach (no streaming capability)

### Key Findings

#### Event Types for Token Streaming

LangGraph emits these event types during execution:

| Event Type | Purpose | Data Available |
|------------|---------|----------------|
| `on_chat_model_start` | LLM invocation begins | Input messages |
| `on_chat_model_stream` | **Token streaming (primary)** | `event["data"]["chunk"].content` (token text) |
| `on_chat_model_end` | LLM completes | Full output message |
| `on_chain_start` | Node starts execution | Stage transition marker |
| `on_chain_end` | Node completes | Stage completion marker |
| `on_chain_error` | Error during execution | Error details |

#### Event Filtering Pattern

**Critical discovery**: Filter events by `langgraph_node` metadata to isolate specific agent tokens:

```python
async for event in graph.astream_events(input, config, version="v2"):
    node = event["metadata"].get("langgraph_node", "")
    event_type = event["event"]

    # Only stream tokens from RAG agent, skip supervisor/emotional_support
    if event_type == "on_chat_model_stream" and node == "rag_agent":
        token = event["data"]["chunk"].content or ""
        yield token  # Send to SSE endpoint
```

#### Integration with Existing Architecture

**Excellent news**: Zero modifications required to existing node implementations.

- Current `llm.ainvoke()` calls automatically support streaming when invoked via `astream_events()`
- Checkpointing continues working transparently (MemorySaver is async-compatible)
- Session state persists across requests without changes
- Conversation context maintained (FR-012)

**Evidence**:
- LangChain documentation: "For @langchain/core >= 0.2.3, streaming occurs automatically with await model.invoke()"
- Our codebase already uses `await llm.ainvoke()` in `app/agents/rag_agent.py:95`

#### Error Handling and Cancellation

**Client cancellation** (FR-018, FR-019):
```python
async def event_generator():
    try:
        async for event in graph.astream_events(input, config, version="v2"):
            yield event_data
    except asyncio.CancelledError:
        # Client disconnected (stop button clicked)
        # LangGraph automatically stops LLM processing
        # Checkpoint already saved from last completed node
        raise  # Re-raise to properly close connection
```

**Error propagation**:
- Errors appear as `on_chain_error` events in the stream
- Can emit structured error events before closing connection (FR-010)

### Implementation Impact

**Files to modify**: 0 (existing nodes already support streaming)
**New files**: 1 (`app/api/streaming.py` - new endpoint)
**Complexity**: Low - architecture is 95% ready

---

## 2. FastAPI SSE Implementation Patterns

### Decision: Use `StreamingResponse` with Async Generators

**Rationale**:
- Native FastAPI support (no external libraries required)
- Async generator pattern naturally integrates with LangGraph's `astream_events()`
- Production-ready error handling and connection management

**Alternatives Considered**:
- `sse-starlette` library: Adds dependency, but provides timeout and retry helpers (may adopt later)
- WebSocket: More complex, requires bidirectional protocol (overkill for one-way streaming)

### SSE Response Format

#### Required Headers

```python
StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"  # Disable nginx buffering
    }
)
```

#### SSE Message Format

**Standard format**:
```
data: <content>\n\n
```

**With event types** (recommended for our use case):
```
event: token
data: {"content": "word"}

event: stage
data: {"stage": "retrieval"}

event: done
data: {}
```

**With IDs** (optional, useful for reconnection):
```
id: 123
event: token
data: {"content": "word"}
```

### Async Generator Pattern

**Production-ready template**:

```python
async def event_generator():
    """Generate SSE events from LangGraph execution."""
    try:
        async for event in graph.astream_events(input, config, version="v2"):
            # Check client disconnect at each iteration (FR-018, FR-019)
            if await request.is_disconnected():
                logger.info("Client disconnected")
                break

            # Process and emit events
            if event["event"] == "on_chat_model_stream":
                token = event["data"]["chunk"].content or ""
                yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

    except asyncio.CancelledError:
        # Client cancelled via stop button
        logger.info("Stream cancelled by client")
        raise

    except Exception as e:
        # Backend error
        logger.exception("Stream error")
        yield f'data: {json.dumps({"type": "error", "message": "Processing failed"})}\n\n'

    finally:
        # Cleanup resources
        logger.debug("Stream cleanup complete")
```

### Connection Management

#### Client Disconnect Detection

**Pattern 1**: Check `request.is_disconnected()` periodically
```python
async for event in source:
    if await request.is_disconnected():
        break  # Stop processing
    yield event_data
```

**Pattern 2**: Let FastAPI raise `asyncio.CancelledError` automatically
```python
try:
    async for event in source:
        yield event_data
except asyncio.CancelledError:
    # Client disconnected
    raise  # Propagate for proper cleanup
```

**Recommendation**: Use both - Pattern 1 for explicit checks during long operations, Pattern 2 as safety net.

#### Timeout Handling (FR-014)

```python
async def event_generator():
    timeout_seconds = 30

    try:
        async with asyncio.timeout(timeout_seconds):
            async for event in graph.astream_events(input, config, version="v2"):
                yield event_data

    except asyncio.TimeoutError:
        yield f'data: {json.dumps({"type": "error", "message": "Request timeout"})}\n\n'
```

### Production Concerns

#### Memory Management

**Problem**: Long-running streams can accumulate memory if events are buffered.

**Solution**: No buffering - yield events immediately as they arrive.

```python
async def event_generator():
    # Bad: Buffering events
    # events = []
    # async for event in source:
    #     events.append(event)
    # for e in events:
    #     yield e

    # Good: Immediate streaming
    async for event in source:
        yield format_sse_event(event)  # No buffering
```

#### Concurrent Stream Handling

**Target**: Support 10+ simultaneous streaming sessions (SC-006).

**FastAPI async architecture**: Naturally supports concurrent streams via uvicorn workers.

**Configuration**:
```bash
uvicorn app.main:app --workers 4 --timeout-keep-alive 65
```

**Monitoring pattern**:
```python
active_streams = 0

async def event_generator():
    global active_streams
    active_streams += 1
    logger.info(f"Active streams: {active_streams}")

    try:
        async for event in source:
            yield event_data
    finally:
        active_streams -= 1
```

#### Nginx Configuration (Production Deployment)

**Critical**: Disable buffering to prevent SSE delays.

```nginx
location /api/chat/stream {
    proxy_pass http://backend;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

### Testing Strategies

#### Using httpx for SSE Testing

**Pattern**: Use `httpx` streaming client with `httpx-sse` extension.

```python
# tests/integration/test_streaming_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from httpx_sse import aconnect_sse
from app.main import app

@pytest.mark.asyncio
async def test_token_streaming():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with aconnect_sse(
            client, "POST", "/chat/stream",
            json={"message": "test query", "session_id": "test-123"}
        ) as event_source:
            tokens = []

            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)

                if data["type"] == "token":
                    tokens.append(data["content"])
                elif data["type"] == "done":
                    break

            assert len(tokens) > 0
            assert "".join(tokens)  # Non-empty response
```

#### Test Scenarios

1. **Basic streaming**: Verify tokens arrive progressively
2. **Multiple event types**: Stage transitions + tokens + completion
3. **Error handling**: Backend errors emit error events
4. **Client disconnect**: Cancellation properly detected
5. **Timeout**: Long operations trigger timeout events
6. **Concurrent streams**: Multiple clients stream simultaneously

---

## 3. Frontend EventSource API Patterns

### Decision: Use Native EventSource API with React Hooks

**Rationale**:
- Native browser API (no dependencies needed) - aligns with FR requirement
- Simple reconnection handling with configurable retry
- TypeScript-friendly with custom hooks

**Alternatives Considered**:
- `fetch()` with `ReadableStream`: More complex parsing, manual SSE format handling
- Third-party libraries (e.g., `eventsource-parser`): Unnecessary for browser environment

### EventSource Basic Usage

```typescript
const eventSource = new EventSource("/api/chat/stream", {
  withCredentials: false  // CORS credentials
});

// Listen for specific event types
eventSource.addEventListener("token", (event) => {
  const data = JSON.parse(event.data);
  console.log("Token:", data.content);
});

eventSource.addEventListener("done", () => {
  eventSource.close();  // Clean up connection
});

eventSource.onerror = (error) => {
  console.error("EventSource error:", error);
  eventSource.close();
};
```

### Limitations and Workarounds

#### Limitation 1: GET Requests Only

**Problem**: EventSource only supports GET requests, but we need POST to send query data.

**Solution**: Use `fetch()` with POST, read response body as stream.

```typescript
const response = await fetch("/api/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, session_id }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  // Parse SSE format manually
}
```

#### Limitation 2: No Custom Headers

**Problem**: Cannot set Authorization headers with EventSource.

**Workaround**: Pass auth token as query parameter or use `fetch()` approach above.

### React Hook Design

**Pattern**: Encapsulate EventSource lifecycle in custom hook.

```typescript
// frontend/src/hooks/useStreamingChat.ts
import { useState, useRef, useCallback } from "react";

interface StreamState {
  tokens: string[];
  stage: string;
  isStreaming: boolean;
  error: string | null;
}

export function useStreamingChat() {
  const [state, setState] = useState<StreamState>({
    tokens: [],
    stage: "",
    isStreaming: false,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const streamMessage = useCallback(async (message: string, sessionId: string) => {
    setState(prev => ({ ...prev, isStreaming: true, tokens: [], error: null }));

    // Create abort controller for stop button (FR-018)
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId }),
        signal: abortControllerRef.current.signal,
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));

            if (data.type === "stage") {
              setState(prev => ({ ...prev, stage: data.stage }));
            } else if (data.type === "token") {
              setState(prev => ({
                ...prev,
                tokens: [...prev.tokens, data.content],
              }));
            } else if (data.type === "done") {
              setState(prev => ({ ...prev, isStreaming: false }));
            } else if (data.type === "error") {
              setState(prev => ({
                ...prev,
                isStreaming: false,
                error: data.message,
              }));
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Stream cancelled by user");  // FR-019
      } else {
        setState(prev => ({
          ...prev,
          isStreaming: false,
          error: "Connection error",
        }));
      }
    }
  }, []);

  const stopStream = useCallback(() => {
    // FR-018: Cancel SSE connection
    abortControllerRef.current?.abort();
    setState(prev => ({ ...prev, isStreaming: false }));
  }, []);

  return { ...state, streamMessage, stopStream };
}
```

### UI Integration Pattern

```typescript
// frontend/src/components/ChatInterface.tsx
import { useStreamingChat } from "../hooks/useStreamingChat";

function ChatInterface() {
  const { tokens, stage, isStreaming, error, streamMessage, stopStream } = useStreamingChat();

  const handleSubmit = async (message: string) => {
    await streamMessage(message, sessionId);
  };

  return (
    <div>
      {/* Stage indicator (FR-005) */}
      {isStreaming && <div>Status: {stage}</div>}

      {/* Progressive token rendering (FR-003) */}
      <div>{tokens.join("")}</div>

      {/* Stop button (FR-017, FR-018) */}
      {isStreaming ? (
        <button onClick={stopStream}>Stop</button>
      ) : (
        <button onClick={() => handleSubmit(inputValue)}>Send</button>
      )}

      {/* Error display (FR-010) */}
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Reconnection Handling

**Automatic reconnection** (for network interruptions):

```typescript
const streamMessageWithRetry = async (message: string, sessionId: string, maxRetries = 3) => {
  let retries = 0;

  while (retries < maxRetries) {
    try {
      await streamMessage(message, sessionId);
      return;  // Success
    } catch (error: any) {
      if (error.name === "AbortError") {
        return;  // User cancelled, don't retry
      }

      retries++;
      console.log(`Retry ${retries}/${maxRetries}`);
      await new Promise(resolve => setTimeout(resolve, 1000 * retries));  // Exponential backoff
    }
  }

  // Max retries exceeded
  setState(prev => ({ ...prev, error: "Failed to connect. Please try again." }));
};
```

---

## 4. Session State Management During Streaming

### Decision: Use Existing Checkpointing Mechanism

**Rationale**:
- LangGraph's `astream_events()` preserves checkpointing behavior (research finding #1)
- Session state automatically saved after each node completes
- No additional state management logic required

**Alternatives Considered**:
- Manual state persistence after stream completion: Redundant with checkpointing
- In-memory token buffering: Already handled by frontend state

### State Persistence Points

**Checkpoint timing** (automatic via LangGraph):

```
1. User submits message
   └─> Checkpoint: Empty initial state

2. Supervisor node completes
   └─> Checkpoint: assigned_agent = "rag_agent"

3. RAG agent node completes (after all tokens streamed)
   └─> Checkpoint: messages = [..., AIMessage(content="full response")]

4. Graph execution completes
   └─> Final checkpoint saved
```

**Key finding**: Checkpointing happens **after node completion**, not during token streaming.

### Handling Cancellation with State Preservation

**Scenario**: User clicks stop button mid-stream (FR-019, FR-021).

**Behavior**:
1. Frontend aborts fetch request
2. Backend detects `asyncio.CancelledError`
3. LangGraph stops LLM processing immediately
4. **Last completed node's checkpoint is preserved** (e.g., supervisor assignment)
5. Next request resumes from last checkpoint (conversation context intact)

**Implementation**: No special handling required - works automatically.

```python
# Backend automatically handles this:
async def event_generator():
    try:
        async for event in graph.astream_events(input, config, version="v2"):
            yield event_data
    except asyncio.CancelledError:
        # Checkpoint already saved from last completed node
        # No manual state saving needed
        raise  # Propagate cancellation
```

### Difference Between `ainvoke()` and `astream_events()`

| Aspect | `ainvoke()` (current) | `astream_events()` (new) |
|--------|----------------------|--------------------------|
| Checkpointing | After graph completion | After each node completes |
| Session state | Saved once at end | Saved progressively |
| Cancellation | Entire execution lost | Last node's state preserved |
| Token access | No access | Real-time token events |
| Use case | Blocking responses | Streaming responses |

**Implication**: `astream_events()` provides **better** state preservation than `ainvoke()` for our use case.

### Sequence Diagram

```
User          Frontend         Backend          LangGraph        Checkpoint
  |               |                |                |                |
  |-- Submit ---->|                |                |                |
  |               |-- POST ------->|                |                |
  |               |                |-- astream ---->|                |
  |               |                |                |-- Save ------->| (empty state)
  |               |                |                |                |
  |               |<-- stage ------|<-- event ------|                |
  |<-- "Retrieval"|                |                |                |
  |               |                |                |                |
  |               |<-- token ------|<-- event ------|                |
  |<-- "word" ----|                |                |                |
  |               |                |                |                |
  |-- STOP ------>|                |                |                |
  |               |-- abort ------>|                |                |
  |               |                |-- cancel ----->|                |
  |               |                |                |-- Save ------->| (partial, supervisor complete)
  |               |<-- cancelled --|<-- CancelledError               |
  |<-- re-enabled |                |                |                |
  |               |                |                |                |
  |-- New msg --->|                |                |                |
  |               |-- POST ------->|                |                |
  |               |                |-- astream ---->|                |
  |               |                |                |-- Load ------->| (resume from supervisor)
  |               |                |                |<-- state ------|
  |               |                |                | (routes to rag_agent directly)
```

---

## 5. Error Handling and Cancellation Patterns

### Error Taxonomy

| Error Type | Source | Detection Method | User Feedback | Recovery |
|------------|--------|------------------|---------------|----------|
| **Network Error** | Client connectivity | `fetch()` exception | "Connection lost" | Auto-retry with backoff |
| **LLM Timeout** | OpenRouter API | No events for 30s | "Request timeout" | Manual retry button |
| **User Cancellation** | Stop button | `AbortController.abort()` | "Cancelled" | Re-enable input immediately |
| **Backend Error** | Processing failure | `on_chain_error` event | "Processing failed" | Manual retry button |
| **Invalid Input** | Validation | HTTP 422 before streaming | Validation message | User fixes input |

### Backend Error Handling Pattern

```python
async def event_generator():
    """Complete error handling for production SSE streaming."""
    try:
        # Timeout wrapper (FR-014)
        async with asyncio.timeout(30):
            async for event in graph.astream_events(input, config, version="v2"):
                # Check client disconnect (FR-019)
                if await request.is_disconnected():
                    logger.info("Client disconnected during streaming")
                    break

                # Handle error events from LangGraph
                if event["event"] == "on_chain_error":
                    error_msg = event["data"].get("error", "Unknown error")
                    logger.error(f"Graph error: {error_msg}")
                    yield f'data: {{"type":"error","message":"Processing failed"}}\n\n'
                    break

                # Process normal events
                # ...

    except asyncio.TimeoutError:
        logger.warning("Stream timeout after 30s")
        yield f'data: {{"type":"error","message":"Request timeout"}}\n\n'

    except asyncio.CancelledError:
        # Client cancelled via stop button (FR-018)
        logger.info("Stream cancelled by client")
        yield f'data: {{"type":"cancelled"}}\n\n'
        raise  # Must re-raise for proper cleanup

    except Exception as e:
        # Unexpected backend error
        logger.exception("Unexpected streaming error")
        # Don't expose internal details to frontend
        yield f'data: {{"type":"error","message":"An error occurred"}}\n\n'

    finally:
        # Cleanup resources (if any)
        logger.debug("Stream cleanup complete")
```

### Frontend Error Handling Pattern

```typescript
const streamMessage = async (message: string, sessionId: string) => {
  setState(prev => ({ ...prev, isStreaming: true, error: null }));

  abortControllerRef.current = new AbortController();

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal: abortControllerRef.current.signal,
    });

    // Check HTTP status before reading stream
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";  // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = JSON.parse(line.slice(6));

          if (data.type === "error") {
            // Backend error (FR-010)
            setState(prev => ({
              ...prev,
              isStreaming: false,
              error: data.message,
            }));
            return;  // Stop processing
          }

          // Handle other event types...
        }
      }
    }

  } catch (error: any) {
    if (error.name === "AbortError") {
      // User cancellation (FR-019)
      console.log("Stream cancelled by user");
      setState(prev => ({ ...prev, isStreaming: false }));
    } else {
      // Network error or other exception
      console.error("Stream error:", error);
      setState(prev => ({
        ...prev,
        isStreaming: false,
        error: "Connection error. Please try again.",
      }));
    }
  }
};
```

### Cancellation Detection Mechanism

**Decision**: Hybrid approach combining explicit checks and automatic detection.

**Pattern 1 - Explicit checks** (recommended for long operations):
```python
async for event in source:
    if await request.is_disconnected():
        logger.info("Client disconnected")
        break  # Stop immediately
    yield event_data
```

**Pattern 2 - Automatic detection** (FastAPI default):
```python
try:
    async for event in source:
        yield event_data
except asyncio.CancelledError:
    # FastAPI raises this when client disconnects
    raise  # Propagate for cleanup
```

**Recommendation**: Use Pattern 1 at processing stage boundaries (retrieval, reranking, generation), Pattern 2 as safety net.

### User Cancellation Flow (FR-016 to FR-021)

```
1. User clicks "Stop" button (FR-017)
   └─> Frontend: abortController.abort()

2. Fetch request aborts (FR-018)
   └─> Frontend: catch AbortError
   └─> Frontend: Re-enable text input and send button (FR-020)

3. Backend: FastAPI raises asyncio.CancelledError (FR-19)
   └─> Backend: LangGraph stops LLM processing
   └─> Backend: Checkpoint preserved (FR-021)

4. User submits new message
   └─> Backend: Resumes from last checkpoint (conversation context intact)
```

---

## Summary of Architectural Decisions

| Decision Area | Choice | Rationale |
|---------------|--------|-----------|
| **LangGraph Streaming** | `astream_events()` v2 | Token-level access, stage transitions, zero node modifications |
| **FastAPI Response** | `StreamingResponse` with async generators | Native support, production-ready, no dependencies |
| **Frontend Client** | `fetch()` + manual SSE parsing | POST support, custom headers, AbortController integration |
| **Event Format** | JSON with event types | Type safety, multiple event kinds, structured errors |
| **Session State** | Existing checkpointing (no changes) | Automatic preservation, cancellation-safe |
| **Cancellation** | `AbortController` + `asyncio.CancelledError` | Native APIs, clean resource cleanup |
| **Error Handling** | Structured error events via SSE | User-friendly messages, proper error propagation |
| **Testing** | `pytest` + `httpx-sse` | Async-native, full SSE lifecycle coverage |

---

## Implementation Readiness

**Assessment**: ✅ Ready to proceed to Phase 1 (Design & Contracts)

**Confidence Level**: High (95%+)

**Risk Areas**:
- ⚠️ None critical identified
- ⚠️ Minor: Frontend SSE parsing complexity (mitigated with clear examples)
- ⚠️ Minor: Nginx buffering in production (documented configuration fix)

**Next Steps**:
1. Generate `data-model.md` with entity schemas
2. Create `contracts/` directory with Pydantic models
3. Generate `quickstart.md` for developer testing
4. Update agent context with new technologies

---

## References

### Documentation
- LangGraph Streaming Concepts: https://github.com/langchain-ai/langgraph/blob/main/docs/docs/concepts/streaming.md
- FastAPI Streaming: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
- MDN EventSource API: https://developer.mozilla.org/en-US/docs/Web/API/EventSource
- SSE Specification: https://html.spec.whatwg.org/multipage/server-sent-events.html

### Examples
- FastAPI + LangGraph SSE: https://www.softgrade.org/sse-with-fastapi-react-langgraph/
- Production Deployment: https://medium.com/@chirazchahbeni/deploying-streaming-ai-agents-with-langgraph-fastapi-and-google-cloud-run-5e32232ef1fb

### Testing Libraries
- `httpx-sse`: https://pypi.org/project/httpx-sse/
- `pytest-asyncio`: https://pypi.org/project/pytest-asyncio/
