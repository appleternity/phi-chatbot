"""Handler for reranking stage detection.

This handler detects when reranking starts by looking for on_chain_start
events from nodes with "rerank" in their name.

Stage Flow (RAG Agent):
  retrieval → reranking → generation

Detection Logic:
- Retrieval complete is inferred when reranking starts
- Reranking started is detected from on_chain_start with "rerank" in node name
"""

from typing import AsyncIterator
import logging

from app.models import StreamEvent, StreamingSession, create_stage_event
from .base import EventHandler

logger = logging.getLogger(__name__)


class RerankStartHandler:
    """Handles reranking stage detection.

    Responsible for:
    - Detecting rerank node start → emit "retrieval" complete + "reranking" started

    Note: This handler runs BEFORE ChainStartHandler in the dispatcher
    because it has a more specific condition (node name contains "rerank").
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Check if this is a rerank chain start event.

        Args:
            event: LangGraph event dict
            session: StreamingSession (unused)

        Returns:
            True if event is on_chain_start and node name contains "rerank"
        """
        if event["event"] != "on_chain_start":
            return False

        node_name = event["metadata"].get("langgraph_node", "")
        return "rerank" in node_name.lower()

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process rerank start event and emit stage transitions.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent for retrieval complete and reranking started
        """
        node_name = event["metadata"].get("langgraph_node", "")

        # Emit retrieval complete (inferred from reranking starting)
        yield create_stage_event(
            "retrieval",
            "complete",
            metadata={"doc_count": "unknown"}  # Could track if needed
        )

        # Transition to reranking stage
        session.update_stage("reranking")
        yield create_stage_event("reranking", "started")

        logger.debug(f"Stage transition: retrieval → reranking (node: {node_name})")
