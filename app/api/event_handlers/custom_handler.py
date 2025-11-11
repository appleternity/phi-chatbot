"""Handler for custom events emitted via get_stream_writer().

This handler processes custom events emitted by nodes using LangGraph's
get_stream_writer() API. This enables direct emission of stage transitions
from nodes, eliminating the need for indirect detection via event parsing.

Custom Event Format:
{
    "type": "stage",
    "stage": "routing|retrieval|reranking|generation",
    "status": "started|complete",
    "metadata": {...}  # Optional additional data
}

Benefits over indirect detection:
- Nodes explicitly declare their stages (no inference needed)
- Simpler debugging (clear data flow)
- No complex if/else logic based on node names
- Eliminates nested chain handling complexity
"""

import logging
from typing import AsyncIterator

from app.models import StreamEvent, StreamingSession, create_stage_event

logger = logging.getLogger(__name__)


class CustomEventHandler:
    """Handles custom events emitted by nodes via get_stream_writer().

    Responsible for:
    - Processing stage transition events from nodes
    - Updating session state based on stage changes
    - Emitting SSE stage events to frontend

    Processes stream_mode="custom" chunks directly from graph.astream().

    Future extensibility:
    - Can handle other custom event types (progress, metrics, etc.)
    """

    async def handle_custom(
        self,
        chunk: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process custom event chunk directly (no event wrapper).

        Args:
            chunk: Custom event data from get_stream_writer()
            session: StreamingSession for state tracking

        Yields:
            StreamEvent objects for stage transitions
        """
        event_type = chunk.get("type")

        if event_type == "stage":
            # Handle stage transition events
            stage = chunk["stage"]
            status = chunk["status"]
            metadata = chunk.get("metadata", {})

            # Update session state
            if status == "started":
                session.update_stage(stage)

            # Emit SSE event
            yield create_stage_event(stage, status, metadata)

            logger.debug(
                f"Custom stage event: stage={stage}, status={status}, "
                f"metadata={metadata}"
            )

        else:
            # Future: Handle other custom event types here
            logger.debug(f"Unknown custom event type: {event_type}")
