"""Handler for graph execution errors.

This handler processes on_chain_error events and emits error SSE events
to the frontend while marking the session as failed.

Error Handling Strategy:
- Log detailed error for debugging
- Emit user-friendly error message (hide internal details)
- Mark session as error state
- Break event processing loop
"""

from typing import AsyncIterator
import logging

from app.models import StreamEvent, StreamingSession, create_error_event
from .base import EventHandler

logger = logging.getLogger(__name__)


class ChainErrorHandler:
    """Handles on_chain_error events for graph execution failures.

    Responsible for:
    - Logging detailed error information
    - Emitting user-friendly error event
    - Marking session as error state
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Check if this is a chain error event.

        Args:
            event: LangGraph event dict
            session: StreamingSession (unused)

        Returns:
            True if event is on_chain_error
        """
        return event["event"] == "on_chain_error"

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process error event and emit error SSE event.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent for processing error
        """
        # Extract error details
        error_data = event["data"]
        error_msg = str(error_data.get("error", "Unknown error"))

        # Log detailed error for debugging
        logger.error(
            f"Graph error: {error_msg}, session={session.session_id}, "
            f"stage={session.current_stage}"
        )

        # Mark session as error state
        session.mark_error(error_msg)

        # Emit user-friendly error (hide internal details)
        yield create_error_event(
            "An error occurred during processing",
            "PROCESSING_ERROR"
        )
