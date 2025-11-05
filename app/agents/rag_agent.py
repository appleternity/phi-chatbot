"""RAG agent for medical information retrieval.

Simplified architecture: Direct retrieval → LLM synthesis (no tool calling).
"""

from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.core.retriever import DocumentRetriever
from app.agents.base import create_llm
from app.utils.prompts import RAG_AGENT_PROMPT
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _format_retrieved_documents(docs: list[dict]) -> str:
    """Format retrieved documents for LLM consumption.

    This formatting is necessary to provide clear structure and source attribution
    for the LLM to generate accurate responses.

    Args:
        docs: List of retrieved document dictionaries

    Returns:
        Markdown-formatted string with document information
    """
    if not docs:
        return "No relevant information found in the knowledge base."

    formatted = "# Retrieved Information\n\n"
    for i, doc in enumerate(docs, 1):
        # Build a breadcrumb for the source, filtering out empty parts
        source_parts = [
            doc.get("source_document"),
            doc.get("chapter_title"),
            doc.get("section_title"),
            doc.get("subsection_title"),
        ]
        source_path = " > ".join(filter(None, source_parts))
        if not source_path:
            source_path = "Unknown Source"

        formatted += f"## Source {i}: {source_path}\n\n"
        # formatted += f"### Summary:\n{doc.get('summary', 'Not available.')}\n\n"
        formatted += f"### Content:\n{doc.get('chunk_text', 'No content.')}\n\n"
        # formatted += f"Similarity Score: {doc.get('similarity_score', 'N/A'):.4f}\n"
        formatted += "---\n\n"

    return formatted


async def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """RAG agent - direct search without tool calling.

    Flow: Extract query → Search KB → Synthesize answer with context

    Args:
        state: Current graph state with messages and retriever

    Returns:
        Command with synthesized answer message
    """
    retriever = state.get("retriever")
    if not retriever:
        raise ValueError("Retriever not initialized in state")

    session_id = state['session_id']

    # 1. Extract query from last user message
    last_message = state["messages"][-1]
    query = last_message.content
    logger.debug(f"Session {session_id}: RAG query: {query}")

    # 2. Search knowledge base directly (no tool calling!)
    docs = await retriever.search(query, top_k=settings.top_k_documents)
    formatted_docs = _format_retrieved_documents(docs)
    logger.debug(f"Session {session_id}: Retrieved {len(docs)} documents")

    # 3. Build prompt with retrieved context
    system_msg = SystemMessage(content=RAG_AGENT_PROMPT)
    context_msg = HumanMessage(content=f"""{formatted_docs}

# User Question
{query}

Based on the retrieved information above, provide a comprehensive answer.""")

    # 4. Single LLM call to synthesize answer
    llm = create_llm(temperature=0.0)  # Factual, deterministic
    response = await llm.ainvoke([system_msg, context_msg])

    logger.debug(f"Session {session_id}: Generated response")
    return Command(goto=END, update={"messages": [response]})


def create_rag_node(retriever: DocumentRetriever):
    """Factory function to create RAG node with closure-captured dependencies.

    Simplified architecture:
    - No ReAct agent, no tool calling
    - Direct retrieval → LLM synthesis pipeline
    - Retriever captured in closure (not serialized)

    Args:
        retriever: Document retriever instance (non-serializable)

    Returns:
        Async node function ready to be added to LangGraph
    """
    async def rag_node(state: MedicalChatState) -> Command[Literal[END]]:
        """RAG node with retriever injected via closure.

        Args:
            state: Current graph state (serializable only)

        Returns:
            Command with synthesized answer message
        """
        # Inject retriever into temporary state (not checkpointed)
        state_with_retriever = {**state, "retriever": retriever}

        # Call simplified rag_agent_node (await since it's async!)
        return await rag_agent_node(state_with_retriever)

    return rag_node
