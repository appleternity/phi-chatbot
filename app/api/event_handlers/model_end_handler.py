"""Handler for LLM completion events.

This handler processes on_chat_model_end events and emits stage completion
events when the LLM finishes generating.

Completion Logic:
- rag_agent LLM completes → emit "reranking" complete (if in generation stage)
- emotional_support LLM completes → no special handling (goes to END)
"""

from typing import AsyncIterator
import logging

from app.models import StreamEvent, StreamingSession, create_stage_event
from .base import EventHandler

logger = logging.getLogger(__name__)


class ModelEndHandler:
    """Handles on_chat_model_end events for LLM completion.

    Responsible for:
    - Detecting rag_agent LLM completion
    - Emitting "reranking" complete event (if not already emitted)
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Check if this is an LLM end event from rag_agent.

        Args:
            event: LangGraph event dict
            session: StreamingSession (unused)

        Returns:
            True if event is on_chat_model_end from rag_agent
        """
        if event["event"] != "on_chat_model_end":
            return False

        node_name = event["metadata"].get("langgraph_node", "")
        return node_name == "rag_agent"

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process LLM completion event and emit stage completion.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent for reranking complete (if in generation stage)
        """
        # Only emit reranking complete if we're in generation stage
        # (This means we've already emitted reranking started)
        if session.current_stage == "generation":
            yield create_stage_event(
                "reranking",
                "complete",
                metadata={"selected": "unknown"}
            )
            logger.debug("Stage transition: reranking complete (LLM finished)")
