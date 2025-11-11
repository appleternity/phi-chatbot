"""Handler for on_chain_start events (stage transitions).

This handler processes LangGraph on_chain_start events and emits
appropriate SSE stage events based on which node is starting.

Graph Flow (from app/graph/builder.py):
┌─────────────────────────────────────────────────────────────┐
│ START                                                        │
│   │                                                          │
│   ├─► (first message) ─► supervisor ─► [rag_agent | emotional_support] ─► END
│   │                                                          │
│   └─► (subsequent)   ─────────────────► [assigned_agent] ───► END
└─────────────────────────────────────────────────────────────┘

Stage Emission Logic:
- supervisor starts → "routing" stage starts
- rag_agent starts → "routing" stage completes, "retrieval" stage starts
- emotional_support starts → "routing" stage completes, "generation" stage starts

Why Indirect Detection (Next Agent Start vs Supervisor End)?
------------------------------------------------------------
The supervisor node uses llm.with_structured_output() which creates nested chains.
This results in multiple on_chain_start/on_chain_end events:

1. on_chain_start supervisor          # Outer supervisor node
2. on_chain_start supervisor          # Nested LLM chain with structured output
3. on_chain_end supervisor            # Nested chain ends (output: "emotional_support")
4. on_chain_end supervisor            # Outer node ends (output: Command object)

We cannot reliably detect which on_chain_end represents true supervisor completion,
and we need to know WHICH agent was assigned. Therefore, we use indirect detection:
when the next agent (rag_agent or emotional_support) starts, we know:
1. Supervisor has completed
2. Which agent was assigned (from the node_name)

This is why "routing complete" is emitted when rag_agent/emotional_support starts,
not when supervisor ends.
"""

from typing import AsyncIterator
import logging

from app.models import StreamEvent, StreamingSession, create_stage_event
from .base import EventHandler

logger = logging.getLogger(__name__)


class ChainStartHandler:
    """Handles on_chain_start events for stage transitions.

    Responsible for:
    - supervisor starts → emit "routing" stage started
    - rag_agent starts → emit "routing" complete + "retrieval" started
    - emotional_support starts → emit "routing" complete + "generation" started

    See module docstring for detailed explanation of indirect detection logic.
    """

    async def can_handle(self, event: dict, session: StreamingSession) -> bool:
        """Check if this is an on_chain_start event we should handle.

        Args:
            event: LangGraph event dict
            session: StreamingSession (unused)

        Returns:
            True if event type is on_chain_start and node is supervisor, rag_agent, or emotional_support
        """
        if event["event"] != "on_chain_start":
            return False

        node_name = event["metadata"].get("langgraph_node", "")
        return node_name in ["supervisor", "rag_agent", "emotional_support"]

    async def handle(
        self,
        event: dict,
        session: StreamingSession
    ) -> AsyncIterator[StreamEvent]:
        """Process on_chain_start event and emit stage transition events.

        Args:
            event: LangGraph event dict
            session: StreamingSession for state tracking

        Yields:
            StreamEvent objects for stage transitions
        """
        node_name = event["metadata"].get("langgraph_node", "")

        if node_name == "supervisor":
            # Supervisor starting → routing stage begins
            session.update_stage("routing")
            yield create_stage_event("routing", "started")
            logger.debug("Stage transition: routing started")

        elif node_name == "rag_agent":
            # RAG agent starting → routing complete, retrieval begins
            # Emit routing complete with agent metadata
            yield create_stage_event(
                "routing",
                "complete",
                metadata={"assigned_agent": "rag_agent"}
            )

            # Transition to retrieval stage
            session.update_stage("retrieval")
            yield create_stage_event("retrieval", "started")
            logger.debug("Stage transition: routing → retrieval (rag_agent)")

        elif node_name == "emotional_support":
            # Emotional support starting → routing complete, skip to generation
            # Emit routing complete with agent metadata
            yield create_stage_event(
                "routing",
                "complete",
                metadata={"assigned_agent": "emotional_support"}
            )

            # Emotional support goes directly to generation (no retrieval/reranking)
            session.update_stage("generation")
            yield create_stage_event("generation", "started")
            logger.debug("Stage transition: routing → generation (emotional_support)")
