"""Event dispatcher for routing LangGraph events to handlers.

This module implements the EventDispatcher that routes events to registered handlers.
"""

from typing import AsyncIterator, Optional
import logging

from app.models import StreamEvent, StreamingSession
from .base import EventHandler

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Routes LangGraph events to appropriate handlers.

    The dispatcher maintains a registry of handlers and dispatches events
    to the first handler that can process it.
    """

    def __init__(self):
        """Initialize dispatcher with empty handler registry."""
        self._handlers: list[EventHandler] = []

    def register(self, handler: EventHandler) -> None:
        """Register an event handler.

        Handlers are checked in registration order. The first handler
        that returns True from can_handle() will process the event.

        Args:
            handler: EventHandler instance to register
        """
        self._handlers.append(handler)

    async def dispatch(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Dispatch event to first matching handler.

        Args:
            event: LangGraph event dict with 'event', 'data', 'metadata' keys
            session: StreamingSession for state tracking

        Yields:
            StreamEvent objects from the matching handler

        Note:
            Only the first matching handler processes the event.
            If no handler matches, no events are yielded.
        """
        for handler in self._handlers:
            if await handler.can_handle(event, session):
                async for sse_event in handler.handle(event, session):
                    yield sse_event
                return  # Only first matching handler processes the event

        # No handler matched - this is normal for events we don't care about
        logger.debug(
            f"No handler for event type: {event.get('event')} "
            f"from node: {event.get('metadata', {}).get('langgraph_node', 'unknown')}"
        )
