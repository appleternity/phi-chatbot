"""Handler for LLM token streaming events.

This handler processes on_chat_model_stream events and emits token events
for the frontend to display in real-time.

Token Streaming Rules:
- Only stream from rag_agent and emotional_support nodes
- Skip tokens from supervisor (classification, not user-facing)
- Filter internal RAG LLM calls (query expansion, document analysis, reranking)
- Only stream final response generation tokens
- Update session to "generation" stage when tokens start flowing
"""

from typing import AsyncIterator
import logging

from app.models import StreamEvent, StreamingSession, create_token_event
from .base import EventHandler

logger = logging.getLogger(__name__)


class ModelStreamHandler:
    """Handles on_chat_model_stream events for real-time token streaming.

    Responsible for:
    - Filtering tokens from rag_agent and emotional_support only
    - Emitting token events for frontend display
    - Tracking token count in session
    - Transitioning to generation stage on first token
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Check if this is a token stream event from rag_agent or emotional_support.

        Args:
            event: LangGraph event dict
            session: StreamingSession (unused)

        Returns:
            True if event is on_chat_model_stream from rag_agent or emotional_support
        """
        if event["event"] != "on_chat_model_stream":
            return False

        node_name = event["metadata"].get("langgraph_node", "")
        return node_name in ["rag_agent", "emotional_support"]

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process token stream event and emit token SSE events.

        Filters out internal RAG LLM calls (query expansion, document analysis, reranking)
        and only streams tokens from final response generation.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent for each token (if non-empty and not internal)
        """
        # Extract metadata to identify call type
        metadata = event.get("metadata", {})
        run_name = metadata.get("ls_run_name", "").lower()

        # Log run_name for debugging and pattern identification
        if run_name:
            logger.debug(f"Token stream from run_name: {run_name}")

        # Skip internal LLM calls (query expansion, document analysis, reranking)
        # These are RAG preprocessing steps that shouldn't be shown to users
        internal_patterns = [
            "query_expansion",
            "query_rewrite",
            "document_analysis",
            "rerank",
            "retrieval",
            "expand",
            "analyze"
        ]

        if any(pattern in run_name for pattern in internal_patterns):
            logger.debug(f"Skipping internal LLM call: {run_name}")
            return

        # Extract token from event data
        token = event["data"]["chunk"].content or ""

        if token:
            # Update session tracking
            session.add_token(token)
            session.update_stage("generation")

            # Emit token event
            yield create_token_event(token)
