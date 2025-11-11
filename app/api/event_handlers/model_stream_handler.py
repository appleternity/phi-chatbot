"""Handler for LLM token streaming from stream_mode="messages".

This handler processes message chunks from LangGraph's stream_mode="messages"
and emits token events for the frontend to display in real-time.

Token Streaming Rules (Simplified):
- All messages in the stream are from user-facing LLMs
- Internal LLM calls (supervisor, query expansion) use .invoke() so don't appear in stream
- Only stream from rag_agent and emotional_support nodes
- Update session to "generation" stage when tokens start flowing
"""

import logging
from typing import AsyncIterator

from app.models import StreamEvent, StreamingSession, create_token_event

logger = logging.getLogger(__name__)


class ModelStreamHandler:
    """Handles message chunks from stream_mode="messages" for token streaming.

    Responsible for:
    - Processing message chunks from rag_agent and emotional_support
    - Emitting token events for frontend display
    - Tracking token count in session

    Note: No internal LLM filtering needed - all internal calls use .invoke()
    Agents explicitly emit generation:started stage events, so no automatic stage
    transition is needed here.
    """

    async def handle_message(
        self,
        message_chunk,
        metadata: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process message chunk and emit token events.

        Only processes messages from rag_agent and emotional_support nodes.
        Ignores internal LLM calls (supervisor, query expansion) to prevent
        unwanted token streaming.

        Args:
            message_chunk: Message chunk from LangGraph
            metadata: Chunk metadata
            session: StreamingSession for state tracking

        Yields:
            StreamEvent for each token (only for user-facing agents)
        """
        # Filter: Only handle user-facing agent messages
        node_name = metadata.get("langgraph_node", "")
        tags = metadata.get("tags", [])

        if node_name not in {"rag_agent", "emotional_support"}:
            return  # Silently ignore - not from user-facing agent

        if "internal-llm" in tags:
            return  # Silently ignore - internal LLM call

        # Process token
        token = message_chunk.content or ""

        if token:
            # Update session tracking
            session.add_token(token)

            # Emit token event
            yield create_token_event(token)

            logger.debug(f"Token emitted from node: {node_name}")
