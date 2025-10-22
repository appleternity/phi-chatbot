"""LangGraph builder for medical chatbot."""

from typing import Literal, Optional
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.graph.state import MedicalChatState
from app.agents.supervisor import supervisor_node
from app.agents.emotional_support import emotional_support_node
from app.agents.rag_agent import create_rag_agent
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
) -> Literal["supervisor", "emotional_support", "rag_agent"]:
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
    checkpointer: Optional[BaseCheckpointSaver] = None
):
    """Build and compile the medical chatbot graph.

    This creates a graph with session-aware routing:
    1. Check if agent is assigned
    2. If not assigned → supervisor classifies and assigns
    3. If assigned → route directly to assigned agent

    Args:
        retriever: Document retriever instance for RAG agent
        checkpointer: Optional checkpointer instance
                     - If None: Auto-detects environment (SqliteSaver for tests, MemorySaver for production)
                     - If provided: Uses the specified checkpointer

    Returns:
        Compiled LangGraph ready for invocation
    """
    logger.info("Building medical chatbot graph...")

    # Create graph builder
    builder = StateGraph(MedicalChatState)

    # Create RAG agent with retriever
    rag_agent = create_rag_agent(retriever)
    logger.debug("RAG agent created with retriever")

    # Create RAG node with closure pattern
    #
    # ARCHITECTURE: This closure pattern solves the serialization problem:
    # - The outer graph uses MemorySaver to checkpoint conversation state
    # - rag_agent (CompiledStateGraph) and retriever (DocumentRetriever) are NOT serializable
    # - By capturing them in closure scope, they remain accessible but aren't checkpointed
    # - Only serializable data (messages, session_id, etc.) gets persisted
    #
    # Alternative approaches considered:
    # - Storing in app.state: Breaks graph composability
    # - Passing via config: Would require state schema changes
    # - Nested checkpointing: Unnecessary - outer graph already handles persistence
    def rag_node_wrapper(state: MedicalChatState):
        """Wrapper that captures rag_agent and retriever in closure.

        This pattern ensures agent and retriever are accessible to the node
        without storing them in the checkpointed state (which would fail
        msgpack serialization). The retriever is passed via temporary state
        dict only during invocation, never persisted.
        """
        # Pass retriever via temporary state for tool access
        state_with_retriever = {**state, "retriever": retriever}

        # Invoke agent with retriever-enhanced state
        response = rag_agent.invoke(state_with_retriever)

        # Return only serializable state updates
        return Command(goto=END, update={"messages": response["messages"]})

    # Add routing check node (passes through state unchanged)
    def check_assignment_node(state: MedicalChatState):
        """Check assignment node - just returns state unchanged."""
        return state

    # Add all nodes
    builder.add_node("check_assignment", check_assignment_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)
    builder.add_node("rag_agent", rag_node_wrapper)

    # Define edges
    # Start at routing check
    builder.add_edge(START, "check_assignment")

    # Route based on assignment
    builder.add_conditional_edges(
        "check_assignment",
        route_based_on_assignment,
        {
            "supervisor": "supervisor",
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent",
        },
    )

    # Supervisor assigns and routes to agent
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        {"emotional_support": "emotional_support", "rag_agent": "rag_agent"},
    )

    # All agents go to END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)

    # Auto-select checkpointer if not provided
    if checkpointer is None:
        checkpointer = _get_checkpointer()

    # Compile with checkpointer for conversation memory
    graph = builder.compile(checkpointer=checkpointer)

    logger.info("Medical chatbot graph compiled successfully")
    return graph
