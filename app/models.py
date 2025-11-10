"""Pydantic models for API requests and responses."""

from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., min_length=1, description="User message")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Agent response")
    agent: str = Field(..., description="Agent that handled the message")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"


# ============================================================================
# SSE Streaming Models (specs/003-sse-streaming/contracts/sse_events.py)
# ============================================================================


class StreamEvent(BaseModel):
    """Single event in SSE stream.

    Represents any event emitted during streaming: stage transitions, tokens,
    completion, errors, or cancellation.

    Functional Requirements:
    - FR-008: Multiple event types (retrieval, reranking, token, completion, error)
    - FR-004: Processing stage events
    - FR-010: Error event handling

    Attributes:
        type: Event type discriminator (retrieval_start, token, done, error, etc.)
        content: Event payload (varies by type: string for tokens, dict for stages)
        timestamp: ISO8601 timestamp of event emission (auto-generated)
    """

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
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO8601 timestamp (e.g., 2025-11-06T10:30:45.123Z)"
    )

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
                    "content": {
                        "stage": "retrieval",
                        "status": "complete",
                        "doc_count": 5
                    },
                    "timestamp": "2025-11-06T10:30:42.456Z"
                },
                {
                    "type": "error",
                    "content": {
                        "message": "Failed to retrieve documents",
                        "code": "RETRIEVAL_ERROR"
                    },
                    "timestamp": "2025-11-06T10:30:40.789Z"
                }
            ]
        }
    }

    def to_sse_format(self) -> str:
        """Convert event to SSE wire format.

        Returns:
            SSE-formatted string with 'data:' prefix and double newline suffix.

        Example:
            >>> event = StreamEvent(type="token", content="word")
            >>> event.to_sse_format()
            'data: {"type":"token","content":"word","timestamp":"2025-11-06T10:30:45.123Z"}\\n\\n'
        """
        import json
        return f"data: {json.dumps(self.model_dump())}\n\n"


class StreamingSession(BaseModel):
    """Tracks active streaming connection state.

    Backend maintains this in-memory during active streaming to track progress,
    accumulated tokens, and current processing stage. Destroyed after completion.

    Not persisted to database - ephemeral session tracking only.

    Attributes:
        session_id: UUID identifying the conversation session
        status: Current stream status (active, cancelled, completed, error)
        accumulated_tokens: List of tokens received so far
        current_stage: Current processing stage (classifying, retrieval, reranking, generation)
        start_time: Unix timestamp when stream started
        token_count: Number of tokens emitted
        error_message: Error description if status is "error"
    """

    session_id: str = Field(..., pattern=r"^[a-f0-9-]{36}$", description="UUID format")
    status: Literal["active", "cancelled", "completed", "error"]
    accumulated_tokens: list[str] = Field(default_factory=list)
    current_stage: Optional[str] = Field(
        default=None,
        description="One of: classifying, retrieval, reranking, generation"
    )
    start_time: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
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

    def update_stage(self, stage: str) -> None:
        """Update current processing stage."""
        self.current_stage = stage

    def add_token(self, token: str) -> None:
        """Append token to accumulated tokens and increment count."""
        self.accumulated_tokens.append(token)
        self.token_count += 1

    def mark_completed(self) -> None:
        """Mark stream as successfully completed."""
        self.status = "completed"

    def mark_cancelled(self) -> None:
        """Mark stream as cancelled by client."""
        self.status = "cancelled"

    def mark_error(self, error_message: str) -> None:
        """Mark stream as failed with error message."""
        self.status = "error"
        self.error_message = error_message


class ChatStreamRequest(BaseModel):
    """Request to initiate SSE streaming.

    Functional Requirements:
    - FR-006: SSE endpoint request format
    - FR-012: Session-aware streaming

    Attributes:
        message: User's chat message/query
        session_id: Session identifier for conversation context
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's question or message"
    )
    session_id: str = Field(
        ...,
        pattern=r"^[a-f0-9-]{36}$",
        description="UUID session identifier"
    )

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


# Event type helpers for type-safe event creation

def create_stage_event(
    stage: Literal["retrieval", "reranking"],
    status: Literal["started", "complete"],
    metadata: Optional[dict] = None
) -> StreamEvent:
    """Create a stage transition event.

    Args:
        stage: Processing stage name
        status: Stage status (started or complete)
        metadata: Optional additional data (e.g., doc_count, candidates)

    Returns:
        StreamEvent with appropriate type and content

    Example:
        >>> event = create_stage_event("retrieval", "started")
        >>> event.type
        'retrieval_start'
    """
    # Map "started" -> "start", keep "complete" as is
    status_suffix = "start" if status == "started" else status
    event_type = f"{stage}_{status_suffix}"
    content = {"stage": stage, "status": status}
    if metadata:
        content.update(metadata)

    return StreamEvent(type=event_type, content=content)  # type: ignore


def create_token_event(token: str) -> StreamEvent:
    """Create a token streaming event.

    Args:
        token: Text token from LLM

    Returns:
        StreamEvent with type="token" and content=token
    """
    return StreamEvent(type="token", content=token)


def create_done_event() -> StreamEvent:
    """Create a stream completion event.

    Returns:
        StreamEvent with type="done"
    """
    return StreamEvent(type="done", content={})


def create_error_event(message: str, code: str = "UNKNOWN_ERROR") -> StreamEvent:
    """Create an error event.

    Args:
        message: Human-readable error description
        code: Error code for programmatic handling

    Returns:
        StreamEvent with type="error" and structured content
    """
    return StreamEvent(
        type="error",
        content={"message": message, "code": code}
    )


def create_cancelled_event() -> StreamEvent:
    """Create a cancellation acknowledgment event.

    Returns:
        StreamEvent with type="cancelled"
    """
    return StreamEvent(type="cancelled", content={})
