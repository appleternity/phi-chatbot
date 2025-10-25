"""LangGraph builder for medical chatbot.

Linus: "Good programmers worry about data structures and their relationships."
This module ONLY assembles the graph - node creation logic belongs to agent modules.

Architecture:
- Pure graph assembly - no node implementation details
- Factory functions handle closure pattern for non-serializable dependencies
- Fail-fast validation for required dependencies
- Clear ownership separation between modules
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.graph.state import MedicalChatState
from app.agents.supervisor import supervisor_node
from app.agents.emotional_support import emotional_support_node
from app.agents.rag_agent import create_rag_node
from app.agents.parenting_agent import create_parenting_node
from app.core.retriever import DocumentRetriever
import logging

logger = logging.getLogger(__name__)


def _get_checkpointer() -> BaseCheckpointSaver:
    """Return default MemorySaver checkpointer for production use.

    For tests, checkpointer is provided via pytest fixtures (see conftest.py)
    which properly manage AsyncSqliteSaver lifecycle.

    Returns:
        MemorySaver for in-memory conversation state
    """
    logger.info("🚀 Using MemorySaver for in-memory conversation state")
    return MemorySaver()


def route_based_on_assignment(
    state: MedicalChatState,
) -> Literal["supervisor", "emotional_support", "rag_agent", "parenting"]:
    """Route to supervisor if no agent assigned, otherwise route to assigned agent.

    This implements the session-sticky routing pattern where:
    - First message: Routes to supervisor for classification
    - Subsequent messages: Routes directly to assigned agent

    Args:
        state: Current graph state

    Returns:
        Node name to route to
    """
    if state.get("assigned_agent") is None:
        logger.debug(f"Session {state['session_id']}: No assigned agent, routing to supervisor")
        return "supervisor"

    assigned = state["assigned_agent"]
    logger.debug(f"Session {state['session_id']}: Routing to assigned agent: {assigned}")
    return assigned


def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: DocumentRetriever,
    parenting_reranker,
    checkpointer: BaseCheckpointSaver | None = None
):
    """Build and compile the medical chatbot graph.

    Linus: "This function should read like a well-written paragraph" -
    pure assembly logic, no implementation details.

    This creates a graph with session-aware routing:
    1. Check if agent is assigned in state
    2. If not assigned → supervisor classifies and assigns
    3. If assigned → route directly to assigned agent

    Args:
        retriever: Document retriever instance for RAG agent (required)
        parenting_retriever: Document retriever for parenting agent (required)
        parenting_reranker: Reranker for parenting agent (required)
        checkpointer: Optional checkpointer instance (defaults to MemorySaver)

    Returns:
        Compiled LangGraph ready for invocation

    Raises:
        ValueError: If required dependencies are missing
    """
    logger.info("Building medical chatbot graph...")

    # Fail-fast validation (Linus: "check errors early and loudly")
    if not parenting_retriever or not parenting_reranker:
        raise ValueError(
            "Parenting retriever and reranker are required. "
            "Please run: python -m src.precompute_parenting_embeddings --force"
        )

    # Create nodes using factory functions (Linus: "let each module own its logic")
    rag_node = create_rag_node(retriever)
    parenting_node = create_parenting_node(parenting_retriever, parenting_reranker)
    logger.debug("Agent nodes created via factory functions")

    # Build graph (Linus: "simple, linear, no special cases")
    builder = StateGraph(MedicalChatState)

    # Add all nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)
    builder.add_node("rag_agent", rag_node)
    builder.add_node("parenting", parenting_node)

    # Define routing maps (Linus: "data structures should be obvious")
    routing_map = {
        "supervisor": "supervisor",
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
        "parenting": "parenting",
    }

    supervisor_routing_map = {
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
        "parenting": "parenting",
    }

    # Connect nodes (Linus: "graph structure should be self-documenting")
    # Start with assignment-based routing
    builder.add_conditional_edges(
        START,
        route_based_on_assignment,
        routing_map,
    )

    # Supervisor assigns and routes to agent
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        supervisor_routing_map,
    )

    # All agents go to END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)
    builder.add_edge("parenting", END)

    # Compile with checkpointer (Linus: "defaults should do the right thing")
    checkpointer = checkpointer or _get_checkpointer()
    graph = builder.compile(checkpointer=checkpointer)

    logger.info("✅ Medical chatbot graph compiled successfully")
    return graph
