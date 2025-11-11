"""RAG agent for medical information retrieval.

Simplified architecture: Direct retrieval → LLM synthesis (no tool calling).
"""

import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END
from langgraph.types import Command

from app.agents.base import create_llm
from app.config import settings
from app.graph.state import MedicalChatState
from app.retrieval import AdvancedRetriever, RerankRetriever, SimpleRetriever
from app.utils.prompts import RAG_AGENT_PROMPT, RAG_CONTEXT_TEMPLATE

logger = logging.getLogger(__name__)
llm = create_llm(temperature=1.0)


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

    logger.info(f"Formatted documents for LLM:\n{formatted}")

    return formatted


def _format_conversation_history(messages) -> str:
    """Format conversation history for LLM context, excluding system messages.

    Args:
        messages: List of message objects from the conversation.

    Returns:
        Formatted string of conversation history with roles.
    """
    if not messages:
        return "No prior messages available."
    
    formatted_parts = []
    for message in messages:
        if isinstance(message, SystemMessage):
            continue  # skip system messages
        elif isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        else:
            raise ValueError("Unknown message type")
        formatted_parts.append(f"{role}: {message.content}")
    return "\n".join(formatted_parts)


async def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """RAG agent - direct search without tool calling.

    Flow: Extract query → Search KB → Synthesize answer with context

    Emits stage events:
    - retrieval:started - When starting document search
    - retrieval:complete - After retrieving documents (includes doc_count)
    - generation:started - Before LLM synthesis

    Args:
        state: Current graph state with messages and retriever

    Returns:
        Command with synthesized answer message
    """
    retriever = state.get("retriever")
    if not retriever:
        raise ValueError("Retriever not initialized in state")

    session_id = state['session_id']

    # Get stream writer for emitting stage events
    writer = get_stream_writer()

    # Emit retrieval started
    writer({
        "type": "stage",
        "stage": "retrieval",
        "status": "started"
    })

    # 1. Extract query from last user message
    last_message = state["messages"][-1]
    conversation_history = _format_conversation_history(state["messages"])
    query = last_message.content
    logger.debug(f"Session {session_id}: RAG query: {query}")

    # 2. Search knowledge base with full conversation context
    # Retrievers will extract appropriate history based on their strategy:
    # - Simple: last message only
    # - Rerank: last message only (reranker provides semantic richness)
    # - Advanced: last 5 messages for LLM query expansion context
    docs = await retriever.search(
        state["messages"],  # Pass full message history
        top_k=settings.top_k_documents,
    )
    formatted_docs = _format_retrieved_documents(docs)
    logger.debug(f"Session {session_id}: Retrieved {len(docs)} documents")

    # Emit retrieval complete with document count
    writer({
        "type": "stage",
        "stage": "retrieval",
        "status": "complete"
    })

    # Emit generation started
    writer({
        "type": "stage",
        "stage": "generation",
        "status": "started"
    })

    # 3. Build prompt with retrieved context
    system_msg = SystemMessage(content=RAG_AGENT_PROMPT)

    # Build context message from template
    context_msg = HumanMessage(content=RAG_CONTEXT_TEMPLATE.format(
        formatted_docs=formatted_docs,
        conversation_history=conversation_history,
        query=query
    ))

    # 4. Single LLM call to synthesize answer
    response = await llm.ainvoke([system_msg, context_msg])

    logger.debug(f"Session {session_id}: Generated response")
    logger.info(f"Response content: {response.content}")
    return Command(goto=END, update={"messages": [response]})


def create_rag_node(retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever):
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
