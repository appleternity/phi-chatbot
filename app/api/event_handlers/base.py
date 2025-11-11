"""Base protocol for event handlers.

This module defines the EventHandler protocol that all event handlers must implement.
"""

from typing import Protocol, AsyncIterator
from app.models import StreamEvent, StreamingSession


class EventHandler(Protocol):
    """Protocol for handling LangGraph events and emitting SSE events.

    Each handler is responsible for:
    1. Determining if it can handle a specific event (can_handle)
    2. Processing the event and yielding SSE events (handle)
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Determine if this handler should process the event.

        Args:
            event: LangGraph event dict with 'event', 'data', 'metadata' keys
            session: StreamingSession tracking current state

        Returns:
            True if this handler should process the event, False otherwise
        """
        ...

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process the event and yield SSE events.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent objects to be converted to SSE format
        """
        ...
