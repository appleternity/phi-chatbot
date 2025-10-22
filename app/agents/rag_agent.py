"""RAG agent for medical information retrieval."""

from typing import Literal, Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.core.retriever import DocumentRetriever
from app.agents.base import create_llm
from app.utils.prompts import RAG_AGENT_PROMPT
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize LLM with low temperature for factual accuracy
llm = create_llm(temperature=1.0)


@tool
async def search_medical_docs(
    query: str, state: Annotated[dict, InjectedState]
) -> str:
    """Search the medical knowledge base for information about medications.

    Use this tool to find information about:
    - Medication names and classifications
    - Uses and indications
    - Dosage information
    - Side effects
    - Warnings and interactions

    Args:
        query: Search query (medication name, condition, or question)

    Returns:
        Formatted information from relevant documents
    """
    retriever: DocumentRetriever = state["retriever"]
    docs = await retriever.search(query, top_k=settings.top_k_documents)

    if not docs:
        return "No relevant information found in the knowledge base."

    # Format documents for LLM
    formatted = "# Retrieved Information\n\n"
    for i, doc in enumerate(docs, 1):
        med_name = doc.metadata.get("name", "Unknown")
        formatted += f"## Source {i}: {med_name}\n\n"
        formatted += f"{doc.content}\n\n"
        formatted += "---\n\n"

    logger.debug(f"Retrieved {len(docs)} documents for query: {query}")
    return formatted


def create_rag_agent(retriever: DocumentRetriever):
    """Create RAG agent with access to document retriever.

    This agent is stateless and doesn't maintain its own checkpointing.
    The outer graph (builder.py) handles conversation persistence via MemorySaver.

    Two-layer serialization fix:
    1. Closure pattern (builder.py): Captures rag_agent/retriever in closure scope,
       preventing them from being added to outer graph's checkpointed state.
    2. checkpointer=False (this function): Prevents inner agent from attempting
       to checkpoint the temporary state_with_retriever that contains the
       non-serializable FAISSRetriever object.

    Both layers are necessary:
    - Without closure: Outer MemorySaver would try to serialize retriever/rag_agent
    - Without checkpointer=False: Inner agent would try to serialize retriever

    Conversation persistence:
    - Handled by outer graph's MemorySaver (messages, session_id, assigned_agent)
    - Inner agent is stateless - executes current query only
    - Multi-turn conversations work via outer checkpoint loading

    Args:
        retriever: Document retriever instance

    Returns:
        Configured ReAct agent (stateless, checkpointer explicitly disabled)
    """
    return create_react_agent(
        llm,
        tools=[search_medical_docs],
        prompt=RAG_AGENT_PROMPT,
        checkpointer=False,  # Critical: prevents inner agent from checkpointing state_with_retriever
    )


def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """RAG agent that answers medical questions using knowledge base.

    This agent uses retrieval-augmented generation to provide accurate information.

    Args:
        state: Current graph state

    Returns:
        Command with agent response
    """
    # Get RAG agent and retriever from state (injected by graph builder)
    rag_agent = state.get("_rag_agent")
    retriever = state.get("retriever")

    if not rag_agent or not retriever:
        raise ValueError("RAG agent or retriever not initialized in state")

    logger.debug(f"Session {state['session_id']}: RAG agent searching knowledge base")

    # Inject retriever into state for tool access
    state_with_retriever = {**state, "retriever": retriever}

    # Invoke agent
    response = rag_agent.invoke(state_with_retriever)

    # Return command with response
    return Command(goto=END, update={"messages": response["messages"]})
