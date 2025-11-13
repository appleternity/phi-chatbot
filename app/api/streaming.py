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
import time

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
from app.config import settings

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
        # Build graph state using shared utility
        state = build_graph_state(request.message, session_id, session_data)

        # Build graph config using shared utility
        config = build_graph_config(session_id)

        # Idle timeout tracking (FR-014: timeout on stream inactivity, not total execution time)
        # Note: This allows long-running queries as long as events keep arriving
        idle_timeout_seconds = settings.stream_idle_timeout
        events_emitted = 0

        # Manually iterate over the LangGraph stream so we can wrap each await with the idle timeout
        stream_iter = graph.astream(
            state,
            config=config,
            stream_mode=["messages", "custom"]
        ).__aiter__()
        try:
            while True:
                try:
                    # Enforce idle-timeout while awaiting the next chunk; handler work is unrestricted
                    mode, chunk = await asyncio.wait_for(
                        stream_iter.__anext__(),
                        timeout=idle_timeout_seconds
                    )
                except StopAsyncIteration:
                    break

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
                        events_emitted += 1
                elif mode == "messages":
                    # chunk is a tuple: (message, metadata)
                    message_chunk, metadata = chunk
                    async for sse_event in model_handler.handle_message(message_chunk, metadata, session):
                        yield sse_event.to_sse_format()
                        events_emitted += 1
        finally:
            aclose = getattr(stream_iter, "aclose", None)
            if aclose:
                await aclose()

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
        # Idle timeout handling (FR-014)
        # Raised when no chunks received within idle_timeout_seconds while awaiting stream
        total_duration = time.time() - session.start_time
        logger.warning(
            f"Stream idle timeout: session={session_id}, "
            f"idle_duration={idle_timeout_seconds:.1f}s, "
            f"total_duration={total_duration:.1f}s, "
            f"events_emitted={events_emitted}, "
            f"current_stage={session.current_stage or 'unknown'}"
        )
        session.mark_error(f"No stream activity for {idle_timeout_seconds}s")

        # Persist session before timeout error (preserve conversation context)
        await persist_session_updates(
            session_id,
            session_data,
            assigned_agent=session_data.assigned_agent,
            metadata=session_data.metadata,
            session_store=session_store
        )

        yield create_error_event(
            f"Stream idle timeout after {idle_timeout_seconds}s of inactivity",
            "IDLE_TIMEOUT"
        ).to_sse_format()

    except asyncio.CancelledError:
        # Client cancelled (stop button) - FR-018, FR-019
        logger.info(f"Stream cancelled by client: session={request.session_id}")
        session.mark_cancelled()

        # Persist session to preserve conversation context (user message)
        # This ensures user doesn't lose their question on cancellation
        # Note: Partial assistant response is intentionally discarded for clean state
        await persist_session_updates(
            session_id,
            session_data,
            assigned_agent=session_data.assigned_agent,
            metadata=session_data.metadata,
            session_store=session_store
        )

        # Send cancelled event to frontend BEFORE re-raising
        # Critical: Both yield AND raise are required:
        # - yield: Sends SSE event to frontend for "Request cancelled" UI (not generic network error)
        # - raise: Propagates cancellation to FastAPI for proper resource cleanup
        # Without yield: Frontend sees connection error instead of cancellation
        # Without raise: FastAPI resources leak, violates asyncio cancellation protocol
        yield create_cancelled_event().to_sse_format()
        raise  # Must re-raise for proper FastAPI cleanup

    except Exception as e:
        # Unexpected backend error
        logger.exception(f"Unexpected stream error: session={request.session_id}")
        session.mark_error(str(e))

        # Best-effort session persistence to preserve conversation context
        # Use try/except since error might be database-related
        try:
            await persist_session_updates(
                session_id,
                session_data,
                assigned_agent=session_data.assigned_agent,
                metadata=session_data.metadata,
                session_store=session_store
            )
        except Exception as persist_error:
            # Log persistence failure but don't let it mask original error
            logger.warning(
                f"Failed to persist session on error: session={session_id}, "
                f"persist_error={persist_error}"
            )

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
