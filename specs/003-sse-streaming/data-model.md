# Data Model: SSE Streaming for Real-Time Chat Responses

**Date**: 2025-11-06
**Status**: Design Phase
**Branch**: `003-sse-streaming`

## Overview

This document defines the data entities and their relationships for implementing SSE streaming in the medical chatbot. All entities use Pydantic models for validation and type safety.

---

## Core Entities

### 1. StreamEvent

**Purpose**: Represents a single event in the SSE stream sent from backend to frontend.

**Fields**:

| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `type` | `Literal["retrieval_start", "retrieval_complete", "reranking_start", "reranking_complete", "token", "done", "error", "cancelled"]` | Yes | Event type discriminator | Must be one of the specified literal values |
| `content` | `str \| dict \| None` | No | Event payload (varies by type) | - For `token`: string (the token text)<br>- For `error`: dict with `message` key<br>- For stages: dict with `stage` and optional `metadata` |
| `timestamp` | `str` | Yes | ISO8601 timestamp of event emission | Must be valid ISO8601 format (e.g., `2025-11-06T10:30:45.123Z`) |

**Event Type Specifications**:

| Event Type | `content` Structure | Example | When Emitted |
|------------|-------------------|---------|--------------|
| `retrieval_start` | `{"stage": "retrieval", "status": "started"}` | Start of knowledge base search | When RAG agent begins retrieval |
| `retrieval_complete` | `{"stage": "retrieval", "status": "complete", "doc_count": int}` | End of retrieval with result count | After documents retrieved |
| `reranking_start` | `{"stage": "reranking", "status": "started", "candidates": int}` | Start of reranking | When reranker begins processing |
| `reranking_complete` | `{"stage": "reranking", "status": "complete", "selected": int}` | End of reranking | After reranking completes |
| `token` | `"word"` (plain string) | Each word/token from LLM | During LLM generation |
| `done` | `{}` (empty dict) | Stream completion | After all tokens sent |
| `error` | `{"message": "Error description", "code": "ERROR_CODE"}` | Error details | On any processing error |
| `cancelled` | `{}` (empty dict) | Stream cancellation acknowledged | When backend detects client disconnect |

**Pydantic Model**:

```python
from pydantic import BaseModel, Field
from typing import Literal, Union
from datetime import datetime

class StreamEvent(BaseModel):
    """Single event in SSE stream."""

    type: Literal[
        "retrieval_start",
        "retrieval_complete",
        "reranking_start",
        "reranking_complete",
        "token",
        "done",
        "error",
        "cancelled"
    ]
    content: Union[str, dict, None] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "token",
                    "content": "Aripiprazole",
                    "timestamp": "2025-11-06T10:30:45.123Z"
                },
                {
                    "type": "retrieval_complete",
                    "content": {"stage": "retrieval", "status": "complete", "doc_count": 5},
                    "timestamp": "2025-11-06T10:30:42.456Z"
                },
                {
                    "type": "error",
                    "content": {"message": "Failed to retrieve documents", "code": "RETRIEVAL_ERROR"},
                    "timestamp": "2025-11-06T10:30:40.789Z"
                }
            ]
        }
    }
```

---

### 2. StreamingSession

**Purpose**: Tracks the state of an active streaming connection on the backend.

**Fields**:

| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `session_id` | `str` | Yes | Unique session identifier (UUID) | Must be valid UUID format |
| `status` | `Literal["active", "cancelled", "completed", "error"]` | Yes | Current streaming status | Must be one of the specified values |
| `accumulated_tokens` | `list[str]` | Yes | Tokens received so far | Empty list at start, grows during streaming |
| `current_stage` | `str \| None` | No | Current processing stage | One of: `"classifying"`, `"retrieval"`, `"reranking"`, `"generation"`, or `None` |
| `start_time` | `float` | Yes | Unix timestamp of stream start | Must be positive float |
| `token_count` | `int` | Yes | Number of tokens emitted | Non-negative integer |
| `error_message` | `str \| None` | No | Error description if status is "error" | Only set when status is "error" |

**Pydantic Model**:

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
import time

class StreamingSession(BaseModel):
    """Tracks active streaming connection state."""

    session_id: str = Field(..., pattern=r"^[a-f0-9-]{36}$")  # UUID format
    status: Literal["active", "cancelled", "completed", "error"]
    accumulated_tokens: list[str] = Field(default_factory=list)
    current_stage: Optional[str] = None
    start_time: float = Field(default_factory=time.time)
    token_count: int = Field(default=0, ge=0)
    error_message: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "active",
                    "accumulated_tokens": ["Aripiprazole", " is", " an"],
                    "current_stage": "generation",
                    "start_time": 1730892645.123,
                    "token_count": 3,
                    "error_message": None
                }
            ]
        }
    }
```

**Usage**: Backend maintains this state temporarily during active streaming (in-memory only, not persisted to database).

---

### 3. ChatStreamRequest

**Purpose**: Request payload for initiating SSE streaming endpoint.

**Fields**:

| Field | Type | Required | Description | Validation Rules |
|-------|------|----------|-------------|------------------|
| `message` | `str` | Yes | User's chat message/query | Min length: 1, Max length: 5000 characters |
| `session_id` | `str` | Yes | Session identifier for conversation context | Must be valid UUID format |

**Pydantic Model**:

```python
from pydantic import BaseModel, Field

class ChatStreamRequest(BaseModel):
    """Request to initiate SSE streaming."""

    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str = Field(..., pattern=r"^[a-f0-9-]{36}$")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "What are the side effects of aripiprazole?",
                    "session_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }
```

---

### 4. CancellationRequest (Future Enhancement)

**Purpose**: Explicit cancellation request (not required for MVP - client disconnect is sufficient).

**Status**: Deferred to post-MVP (FR-018, FR-019 use client disconnect detection instead).

**Fields** (for future reference):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `str` | Yes | Session to cancel |
| `reason` | `Literal["user_initiated", "timeout", "error"]` | Yes | Cancellation reason |

**Note**: MVP implementation uses `AbortController` on frontend + `asyncio.CancelledError` detection on backend. Explicit cancellation endpoint not needed.

---

## Entity Relationships

```
ChatStreamRequest (1) ──initiates──> StreamingSession (1)
StreamingSession (1) ──emits──> StreamEvent (0..*)

Existing Entities (unchanged):
SessionData (1) ──persisted_via──> LangGraph Checkpointer
MedicalChatState ──snapshot_of──> Current Graph State
```

**Key Points**:
- `StreamingSession` is ephemeral (exists only during active stream)
- `SessionData` (existing entity) persists conversation context via checkpointing
- `StreamEvent` is stateless (emitted and immediately sent via SSE, not stored)

---

## Data Flow

### 1. Stream Initiation

```
Client                   Backend                     StreamingSession
  |                         |                               |
  |-- ChatStreamRequest --->|                               |
  |                         |-- Create ----------------->  |
  |                         |   (status: "active",          |
  |                         |    current_stage: None)       |
  |                         |                               |
  |<-- SSE: retrieval_start-|<-- Update stage --------------|
```

### 2. Token Streaming

```
LangGraph                Backend                   StreamingSession       Client
  |                         |                            |                   |
  |-- on_chat_model_stream->|                            |                   |
  |   (token: "word")       |-- Append token -------->   |                   |
  |                         |   accumulated_tokens       |                   |
  |                         |-- Increment ------------->  |                   |
  |                         |   token_count              |                   |
  |                         |-- Create StreamEvent ----->|                   |
  |                         |-- SSE: token --------------------------------------->|
```

### 3. Stream Completion

```
Backend                   StreamingSession          Client
  |                            |                        |
  |-- Update status ---------->|                        |
  |   ("completed")            |                        |
  |-- Create StreamEvent ----->|                        |
  |-- SSE: done ---------------------------------------->|
  |-- Destroy session -------->X                        |
```

### 4. Error Handling

```
LangGraph/Backend         StreamingSession          Client
  |                            |                        |
  |-- Exception/Error -------->|                        |
  |-- Update status ---------->|                        |
  |   ("error")                |                        |
  |-- Set error_message ------>|                        |
  |-- Create StreamEvent ----->|                        |
  |-- SSE: error -------------------------------------->|
  |-- Destroy session -------->X                        |
```

---

## Validation Rules Summary

### Backend Validation

1. **Request Validation** (FastAPI automatic):
   - `message` not empty and ≤5000 chars
   - `session_id` is valid UUID format

2. **Event Validation** (Pydantic):
   - `type` must be one of allowed event types
   - `timestamp` is valid ISO8601 format
   - `content` matches expected structure for event type

3. **Session Validation**:
   - `session_id` exists in session store before streaming
   - Only one active stream per session (concurrent streams rejected)

### Frontend Validation

1. **Event Parsing**:
   - SSE `data:` line is valid JSON
   - `type` field exists in parsed JSON
   - Handle unknown event types gracefully (log warning, continue)

2. **State Consistency**:
   - Tokens accumulated in order
   - Stage transitions are monotonic (retrieval → reranking → generation)
   - `done` or `error` event marks final state

---

## Storage Considerations

### In-Memory (Backend)

**Stored during active streaming**:
- `StreamingSession` objects in dictionary keyed by `session_id`
- Cleared after stream completion/error/cancellation
- No persistence required

**Memory limit**: Max 100 concurrent sessions (configurable via `MAX_CONCURRENT_STREAMS` setting).

### Not Stored

**Ephemeral data**:
- `StreamEvent` objects (emitted and immediately forgotten)
- Individual tokens (accumulated in frontend state, not backend after sending)

### Persisted (Existing Mechanisms)

**Unchanged storage**:
- `SessionData` → In-memory session store (existing)
- Graph state → LangGraph checkpointer (MemorySaver)
- Final messages → Checkpointer after node completion

---

## Example Scenarios

### Scenario 1: Successful Streaming

**Event Sequence**:

```json
{"type": "retrieval_start", "content": {"stage": "retrieval", "status": "started"}, "timestamp": "2025-11-06T10:30:40.000Z"}
{"type": "retrieval_complete", "content": {"stage": "retrieval", "status": "complete", "doc_count": 5}, "timestamp": "2025-11-06T10:30:41.500Z"}
{"type": "reranking_start", "content": {"stage": "reranking", "status": "started", "candidates": 5}, "timestamp": "2025-11-06T10:30:41.501Z"}
{"type": "reranking_complete", "content": {"stage": "reranking", "status": "complete", "selected": 3}, "timestamp": "2025-11-06T10:30:42.000Z"}
{"type": "token", "content": "Aripiprazole", "timestamp": "2025-11-06T10:30:42.100Z"}
{"type": "token", "content": " is", "timestamp": "2025-11-06T10:30:42.150Z"}
{"type": "token", "content": " an", "timestamp": "2025-11-06T10:30:42.200Z"}
...
{"type": "done", "content": {}, "timestamp": "2025-11-06T10:30:45.500Z"}
```

### Scenario 2: User Cancellation

**Event Sequence**:

```json
{"type": "retrieval_start", "content": {"stage": "retrieval", "status": "started"}, "timestamp": "2025-11-06T10:30:40.000Z"}
{"type": "token", "content": "Aripiprazole", "timestamp": "2025-11-06T10:30:42.100Z"}
{"type": "token", "content": " is", "timestamp": "2025-11-06T10:30:42.150Z"}
[User clicks stop button]
{"type": "cancelled", "content": {}, "timestamp": "2025-11-06T10:30:42.300Z"}
[Stream closes]
```

### Scenario 3: Backend Error

**Event Sequence**:

```json
{"type": "retrieval_start", "content": {"stage": "retrieval", "status": "started"}, "timestamp": "2025-11-06T10:30:40.000Z"}
{"type": "error", "content": {"message": "Failed to retrieve documents", "code": "RETRIEVAL_ERROR"}, "timestamp": "2025-11-06T10:30:40.500Z"}
[Stream closes]
```

---

## Migration Notes

### Existing Schema Impact

**No database migrations required** - all streaming entities are in-memory only.

**Existing entities unchanged**:
- `app/models.py::ChatRequest` - Preserved for non-streaming `/chat` endpoint
- `app/models.py::ChatResponse` - Preserved for non-streaming `/chat` endpoint
- `app/core/session_store.py::SessionData` - No changes needed

**New schema file**: `app/models.py` extended with:
- `StreamEvent`
- `StreamingSession`
- `ChatStreamRequest`

---

## Testing Considerations

### Unit Tests

**Test cases**:
1. `StreamEvent` validation with valid/invalid event types
2. `StreamEvent` timestamp format validation
3. `ChatStreamRequest` message length validation
4. `StreamingSession` status transitions (active → completed/cancelled/error)
5. `StreamingSession` token accumulation

### Integration Tests

**Test cases**:
1. Full streaming lifecycle (request → events → completion)
2. Error event emission and stream termination
3. Cancellation event handling
4. Concurrent session limits
5. Session state cleanup after completion

---

## Next Steps

1. ✅ Data model defined
2. ⏳ Implement Pydantic models in `specs/003-sse-streaming/contracts/sse_events.py`
3. ⏳ Implement FastAPI endpoint contracts in `specs/003-sse-streaming/contracts/streaming_api.py`
4. ⏳ Generate `quickstart.md` for developer testing
5. ⏳ Update agent context (CLAUDE.md) with new technologies
