"""SSE Streaming Core Logic.

This module implements Server-Sent Events (SSE) streaming for real-time chat responses.
Provides token-by-token streaming with processing stage indicators.

The main entry point is the stream_chat_events() function, which is used by the
/chat endpoint in app/main.py when streaming=true.

Architecture:
- Direct event handler calls for custom and message events
- CustomEventHandler processes stage transitions from get_stream_writer()
- ModelStreamHandler processes LLM token streams for real-time display
- See app/api/event_handlers/ for handler implementations

Spec Reference: specs/003-sse-streaming/data-model.md
Source: specs/003-sse-streaming/contracts/streaming_api.py
"""

from fastapi import Request
from typing import AsyncIterator
from datetime import datetime
import asyncio
import logging

from app.models import (
    ChatStreamRequest,
    StreamingSession,
    create_done_event,
    create_error_event,
    create_cancelled_event,
    create_metadata_event,
)
from app.api.event_handlers import CustomEventHandler, ModelStreamHandler
from app.utils.session_helpers import (
    create_or_load_session,
    build_graph_state,
    build_graph_config,
    persist_session_updates
)

logger = logging.getLogger(__name__)


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

    # Initialize event handlers
    custom_handler = CustomEventHandler()
    model_handler = ModelStreamHandler()

    try:
        # Timeout wrapper (FR-014: 30-second timeout)
        async with asyncio.timeout(30):
            # Build graph state using shared utility
            state = build_graph_state(request.message, session_id, session_data)

            # Build graph config using shared utility
            config = build_graph_config(session_id)

            # Invoke LangGraph with stream modes
            # stream_mode=["messages", "custom"] captures:
            # - "messages": LLM token streaming (token-by-token from user-facing LLMs)
            # - "custom": Custom events from get_stream_writer() (stage transitions + metadata)
            # Note: Internal LLM calls (supervisor, query expansion) use .invoke() so don't appear in stream
            async for mode, chunk in graph.astream(
                state,
                config=config,
                stream_mode=["messages", "custom"]
            ):
                # Check client disconnect at each iteration (FR-019)
                if await request_obj.is_disconnected():
                    logger.info(f"Client disconnected: session={request.session_id}")
                    session.mark_cancelled()
                    yield create_cancelled_event().to_sse_format()
                    break

                # Process events based on stream mode
                # Handlers emit SSE events and update streaming state (current_stage, token_count)
                # Handlers are responsible for their own filtering logic
                if mode == "custom":
                    async for sse_event in custom_handler.handle_custom(chunk, session):
                        yield sse_event.to_sse_format()
                elif mode == "messages":
                    # chunk is a tuple: (message, metadata)
                    message_chunk, metadata = chunk
                    async for sse_event in model_handler.handle_message(message_chunk, metadata, session):
                        yield sse_event.to_sse_format()

        # Stream completed successfully (FR-011)
        session.mark_completed()
        duration = datetime.utcnow().timestamp() - session.start_time

        # Get final state to extract assigned_agent (LangGraph best practice)
        # Supervisor sets assigned_agent in state via Command.update
        final_state = await graph.aget_state(config)
        assigned_agent = final_state.values.get("assigned_agent") or session_data.assigned_agent

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
