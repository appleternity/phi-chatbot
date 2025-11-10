"""FastAPI SSE Streaming Endpoint.

This module implements Server-Sent Events (SSE) streaming for real-time chat responses.
Provides token-by-token streaming with processing stage indicators.

Spec Reference: specs/003-sse-streaming/data-model.md
Source: specs/003-sse-streaming/contracts/streaming_api.py
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
from datetime import datetime
import asyncio
import logging

from app.models import (
    ChatStreamRequest,
    StreamEvent,
    StreamingSession,
    create_stage_event,
    create_token_event,
    create_done_event,
    create_error_event,
    create_cancelled_event,
)

logger = logging.getLogger(__name__)

# Create router for streaming endpoints
router = APIRouter(prefix="/chat", tags=["streaming"])


# Dependency injection
def get_graph():
    """Get compiled LangGraph instance.

    Returns:
        Compiled LangGraph instance from application state.

    Raises:
        RuntimeError: If graph is not initialized.
    """
    # TODO: this probably should not be from main. if we need it, it should be moved out of main.py
    # TODO: import should be at top
    from app.main import app_state

    graph = app_state.get("graph")
    if graph is None:
        raise RuntimeError("Graph not initialized. Check application startup.")
    return graph


# Core streaming implementation

async def stream_chat_events(
    request: ChatStreamRequest,
    graph,
    request_obj: Request,
    session_store,
    user_id: str,
) -> AsyncIterator[str]:
    """Generate SSE events from LangGraph execution.

    This is the core streaming generator that:
    1. Creates or loads session using shared utilities
    2. Emits metadata event with session_id
    3. Invokes LangGraph with astream_events()
    4. Filters and converts events to SSE format
    5. Persists session after successful completion
    6. Handles errors and cancellation

    Functional Requirements:
    - FR-001: Real-time token streaming
    - FR-002: <100ms token delivery latency
    - FR-004, FR-005: Stage indicators
    - FR-010: Error handling
    - FR-018, FR-019: Cancellation detection

    Args:
        request: Chat stream request with message and session_id
        graph: Compiled LangGraph instance
        request_obj: FastAPI Request object for disconnect detection
        session_store: Session store for persistence
        user_id: User ID for session creation and validation

    Yields:
        SSE-formatted event strings (e.g., "data: {...}\\n\\n")

    Raises:
        asyncio.CancelledError: When client disconnects (must be re-raised)
    """
    # TODO: import should be at top
    # Import shared session utilities
    from app.utils.session_helpers import (
        create_or_load_session,
        build_graph_state,
        build_graph_config,
        persist_session_updates
    )
    from app.models import create_metadata_event

    # Create or load session using shared logic (consistent with non-streaming)
    session_id, session_data = await create_or_load_session(
        request.session_id, user_id, session_store
    )

    # Emit metadata event as FIRST event (before any processing)
    # This allows frontend to capture session_id immediately
    yield create_metadata_event(session_id).to_sse_format()

    # Create streaming session tracker
    session = StreamingSession(
        session_id=session_id,
        status="active"
    )

    # Track assigned_agent from graph events
    assigned_agent = session_data.assigned_agent

    try:
        # Timeout wrapper (FR-014: 30-second timeout)
        async with asyncio.timeout(30):
            # Build graph state using shared utility
            state = build_graph_state(request.message, session_id, session_data)

            # Build graph config using shared utility
            config = build_graph_config(session_id)

            # Invoke LangGraph with event streaming (research: astream_events v2)
            async for event in graph.astream_events(
                state,
                config=config,
                version="v2"  # Use v2 for better performance
            ):
                # Check client disconnect at each iteration (FR-019)
                if await request_obj.is_disconnected():
                    logger.info(f"Client disconnected: session={request.session_id}")
                    session.mark_cancelled()
                    yield create_cancelled_event().to_sse_format()
                    break

                event_type = event["event"]
                node_name = event["metadata"].get("langgraph_node", "")

                # Stage transitions (FR-004)
                if event_type == "on_chain_start":
                    if node_name == "supervisor":
                        session.update_stage("routing")
                        # Emit routing start event
                        routing_event = create_stage_event("routing", "started")
                        yield routing_event.to_sse_format()

                    elif node_name == "rag_agent":
                        # Track assigned agent for session persistence
                        assigned_agent = "rag_agent"

                        # Emit routing complete (supervisor finished)
                        yield create_stage_event(
                            "routing", "complete",
                            metadata={"assigned_agent": "rag_agent"}
                        ).to_sse_format()

                        session.update_stage("retrieval")
                        stage_event = create_stage_event(
                            "retrieval", "started"
                        )
                        yield stage_event.to_sse_format()

                    elif node_name == "emotional_support":
                        # Track assigned agent for session persistence
                        assigned_agent = "emotional_support"

                        # Emit routing complete (supervisor finished)
                        yield create_stage_event(
                            "routing", "complete",
                            metadata={"assigned_agent": "emotional_support"}
                        ).to_sse_format()

                        # Emotional support goes directly to generation (no retrieval/reranking)
                        session.update_stage("generation")
                        yield create_stage_event("generation", "started").to_sse_format()

                # Retrieval completion (estimated from reranking start)
                if event_type == "on_chain_start" and "rerank" in node_name.lower():
                    session.update_stage("reranking")
                    # Emit retrieval complete
                    yield create_stage_event(
                        "retrieval", "complete",
                        metadata={"doc_count": "unknown"}  # Can track if needed
                    ).to_sse_format()
                    # Emit reranking start
                    yield create_stage_event(
                        "reranking", "started"
                    ).to_sse_format()

                # Token streaming (FR-001, FR-002, FR-003)
                if event_type == "on_chat_model_stream":
                    # Filter: Stream from rag_agent and emotional_support, skip supervisor
                    if node_name in ["rag_agent", "emotional_support"]:
                        token = event["data"]["chunk"].content or ""
                        if token:
                            # Update session tracking
                            session.add_token(token)
                            session.update_stage("generation")

                            # Emit token event
                            token_event = create_token_event(token)
                            yield token_event.to_sse_format()

                # LLM completion (marks reranking complete if not emitted yet)
                if event_type == "on_chat_model_end":
                    if node_name == "rag_agent":
                        if session.current_stage == "generation":
                            # Emit reranking complete (if not already emitted)
                            yield create_stage_event(
                                "reranking", "complete",
                                metadata={"selected": "unknown"}
                            ).to_sse_format()

                # Error events (FR-010)
                if event_type == "on_chain_error":
                    error_data = event["data"]
                    error_msg = str(error_data.get("error", "Unknown error"))
                    logger.error(f"Graph error: {error_msg}, session={request.session_id}")

                    session.mark_error(error_msg)
                    yield create_error_event(
                        "An error occurred during processing",
                        "PROCESSING_ERROR"
                    ).to_sse_format()
                    break

        # Stream completed successfully (FR-011)
        session.mark_completed()
        duration = datetime.utcnow().timestamp() - session.start_time

        # Persist session updates using shared utility (consistent with non-streaming)
        await persist_session_updates(
            session_id,
            session_data,
            assigned_agent=assigned_agent,
            metadata=session_data.metadata,  # Keep existing metadata
            session_store=session_store
        )

        logger.info(
            f"Stream completed: session={session_id}, "
            f"tokens={session.token_count}, duration={duration:.2f}s, "
            f"agent={assigned_agent}"
        )
        yield create_done_event().to_sse_format()

    except asyncio.TimeoutError:
        # Timeout handling (FR-014)
        logger.warning(f"Stream timeout: session={request.session_id}")
        session.mark_error("Request timeout")
        yield create_error_event(
            "Request timed out after 30 seconds",
            "TIMEOUT_ERROR"
        ).to_sse_format()

    except asyncio.CancelledError:
        # Client cancelled (stop button) - FR-018, FR-019
        logger.info(f"Stream cancelled by client: session={request.session_id}")
        session.mark_cancelled()
        yield create_cancelled_event().to_sse_format()
        raise  # Must re-raise for proper FastAPI cleanup

    except Exception as e:
        # Unexpected backend error
        logger.exception(f"Unexpected stream error: session={request.session_id}")
        session.mark_error(str(e))
        # Don't expose internal error details to frontend
        yield create_error_event(
            "An unexpected error occurred",
            "INTERNAL_ERROR"
        ).to_sse_format()

    finally:
        # Cleanup logging
        logger.debug(
            f"Stream cleanup: session={request.session_id}, "
            f"status={session.status}, tokens={session.token_count}"
        )


@router.post("")
async def chat(
    request: ChatStreamRequest,
    fastapi_request: Request,
    graph = Depends(get_graph),
) -> StreamingResponse:
    # TODO: we are not using this anymore? If yes, consider removing it.
    """SSE streaming endpoint for real-time chat responses.

    This endpoint:
    1. Validates request payload
    2. Creates SSE streaming response
    3. Streams processing stages and tokens
    4. Handles errors and cancellation

    Functional Requirements:
    - FR-006: SSE as transport mechanism
    - FR-007: Proper SSE format (data: prefix, \\n\\n delimiter)
    - FR-011: Clean connection closure
    - FR-014: 30-second timeout

    Success Criteria:
    - SC-001: First token within 1 second
    - SC-002: Token latency <100ms
    - SC-006: Support 10+ concurrent sessions

    Args:
        request: ChatStreamRequest with message and session_id
        fastapi_request: FastAPI Request object
        graph: LangGraph instance (dependency injection)

    Returns:
        StreamingResponse with text/event-stream content type

    Raises:
        HTTPException: If request validation fails (422)

    Example Request:
        POST /chat/stream
        {
            "message": "What are the side effects of aripiprazole?",
            "session_id": "550e8400-e29b-41d4-a716-446655440000"
        }

    Example SSE Response:
        data: {"type":"retrieval_start","content":{"stage":"retrieval","status":"started"},"timestamp":"2025-11-06T10:30:40.000Z"}

        data: {"type":"token","content":"Aripiprazole","timestamp":"2025-11-06T10:30:42.100Z"}

        data: {"type":"done","content":{},"timestamp":"2025-11-06T10:30:45.500Z"}
    """
    logger.info(f"Initiating SSE stream: session={request.session_id}")

    return StreamingResponse(
        stream_chat_events(request, graph, fastapi_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
