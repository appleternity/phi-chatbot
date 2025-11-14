"""RAG agent for medical information retrieval.

Router-based architecture: Classify intent → Route to retrieval or direct response.
Restores history-aware retrieval with minimal changes to original implementation.
"""

import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.config import settings
from app.graph.state import MedicalChatState
from app.llm import internal_llm, response_llm
from app.retrieval import AdvancedRetriever, RerankRetriever, SimpleRetriever
from app.utils.prompts import (
    RAG_AGENT_PROMPT,
    RAG_CLASSIFICATION_PROMPT,
    RAG_CONTEXT_TEMPLATE,
    RAG_CONVERSATIONAL_TEMPLATE,
)
from app.utils.text_utils import normalize_llm_output

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
        formatted += f"### Content:\n{doc.get('chunk_text', 'No content.')}\n\n"
        formatted += "---\n\n"

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
            continue  # Skip system messages
        elif isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        else:
            role = "Unknown"
        formatted_parts.append(f"{role}: {message.content}")

    return "\n".join(formatted_parts)


def create_rag_agent(retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever):
    """Factory function to create router-based RAG agent with classification.

    Architecture:
    - classify_intent: Determine if retrieval needed (medical query vs. greeting)
    - rag_agent_node: Retrieve + generate (medical queries)
    - generate_without_retrieval: Direct response (greetings, clarifications)

    Args:
        retriever: Document retriever instance (injected via closure)

    Returns:
        Compiled StateGraph ready for integration
    """
    async def classify_intent(state: MedicalChatState) -> dict:
        """Classify user intent to route to retrieval or direct response.

        Determines if the user's message requires:
        - "retrieve": Medical/clinical question needing knowledge base lookup
        - "respond": Greeting, clarification, summary, or conversational query

        Args:
            state: Current graph state with conversation messages

        Returns:
            State update with routing decision
        """
        last_message = state["messages"][-1]
        session_id = state["session_id"]

        # Use classification prompt from centralized prompts module
        prompt = RAG_CLASSIFICATION_PROMPT.format(message=last_message.content)

        response = await internal_llm.ainvoke([HumanMessage(content=prompt)])
        intent = normalize_llm_output(response.content)

        # Validate and default to retrieve if unclear
        if intent not in ["retrieve", "respond"]:
            logger.warning(
                f"Session {session_id}: Invalid classification '{intent}', defaulting to 'retrieve'"
            )
            intent = "retrieve"

        logger.info(f"Session {session_id}: Classified intent as '{intent}'")

        return {"__routing": intent}

    async def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
        """RAG agent - retrieve from knowledge base and synthesize answer.

        Flow: Extract query → Search KB with full history → Synthesize answer

        Emits stage events:
        - retrieval:started - When starting document search
        - retrieval:complete - After retrieving documents
        - generation:started - Before LLM synthesis

        Args:
            state: Current graph state with messages and retriever

        Returns:
            Command with synthesized answer message
        """
        session_id = state["session_id"]

        # Get stream writer for emitting stage events
        writer = get_stream_writer()

        # Emit retrieval started
        writer({"type": "stage", "stage": "retrieval", "status": "started"})

        # 1. Extract query and conversation history
        last_message = state["messages"][-1]
        conversation_history = _format_conversation_history(state["messages"])
        query = last_message.content
        logger.debug(f"Session {session_id}: RAG query: {query}")

        # 2. Search knowledge base with full conversation context
        # Retrievers extract appropriate history based on their strategy:
        # - SimpleRetriever: last message only (max_history=1)
        # - RerankRetriever: last message only (max_history=1)
        # - AdvancedRetriever: last 5 messages for query expansion (max_history=5)
        docs = await retriever.search(
            state["messages"],  # ✅ Pass full message history for context-aware retrieval
            top_k=settings.top_k_documents,
        )
        formatted_docs = _format_retrieved_documents(docs)
        logger.debug(f"Session {session_id}: Retrieved {len(docs)} documents")

        # Emit retrieval complete
        writer({"type": "stage", "stage": "retrieval", "status": "complete"})

        # Emit generation started
        writer({"type": "stage", "stage": "generation", "status": "started"})

        # 3. Build prompt with retrieved context
        system_msg = SystemMessage(content=RAG_AGENT_PROMPT)
        context_msg = HumanMessage(
            content=RAG_CONTEXT_TEMPLATE.format(
                formatted_docs=formatted_docs,
                conversation_history=conversation_history,
                query=query,
            )
        )

        # 4. Single LLM call to synthesize answer
        response = await response_llm.ainvoke([system_msg, context_msg])

        logger.info(f"Session {session_id}: Generated response with retrieval")
        return Command(goto=END, update={"messages": [response]})

    async def generate_without_retrieval(state: MedicalChatState) -> Command[Literal[END]]:
        """Generate direct response without retrieval for conversational queries.

        Handles greetings, clarifications, thank yous, and other non-medical queries
        that don't require knowledge base lookup.

        Args:
            state: Current graph state with conversation messages

        Returns:
            Command with conversational response message
        """
        session_id = state["session_id"]

        # Get stream writer for emitting stage events
        writer = get_stream_writer()

        # Emit generation started (no retrieval)
        writer({"type": "stage", "stage": "generation", "status": "started"})

        logger.info(f"Session {session_id}: Generating direct response (no retrieval)")

        # Build conversational prompt
        conversation_history = _format_conversation_history(state["messages"])
        system_msg = SystemMessage(content=RAG_AGENT_PROMPT)
        context_msg = HumanMessage(
            content=RAG_CONVERSATIONAL_TEMPLATE.format(
                conversation_history=conversation_history
            )
        )

        # Generate conversational response
        response = await response_llm.ainvoke([system_msg, context_msg])

        logger.info(f"Session {session_id}: Generated response without retrieval")
        return Command(goto=END, update={"messages": [response]})

    # Build the graph
    builder = StateGraph(MedicalChatState)

    # Add nodes
    builder.add_node("classify", classify_intent)
    builder.add_node("retrieve", rag_agent_node)
    builder.add_node("respond", generate_without_retrieval)

    # Add edges
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        lambda state: state["__routing"],  # Read routing decision from state
        ["retrieve", "respond"],
    )
    builder.add_edge("retrieve", END)
    builder.add_edge("respond", END)

    # Compile and return
    graph = builder.compile()
    logger.info("Router-based RAG agent compiled successfully")

    return graph
