"""Agentic RAG agent for parenting advice with corrective retrieval.

This module implements a multi-node LangGraph with corrective RAG capabilities:
- Agent decision: LLM decides whether to retrieve or answer directly
- Document grading: Filters retrieved documents by relevance
- Quality checking: Assesses if retrieval was sufficient
- Query rewriting: Improves queries when retrieval quality is poor
- Confidence scoring: Validates generation confidence before returning

Architecture Flow:
    START → agent_decision → [tool_calls?] → tools → grade_documents
         → check_quality → [good?] → generate_answer → confidence_check → END
                        → [poor?] → rewrite_query (max 2 attempts) → retrieve
"""

from typing import Literal, Annotated, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END
from app.graph.parenting_state import ParentingRAGState
from app.graph.state import MedicalChatState
from app.core.retriever import DocumentRetriever, Document
from app.core.reranker import CrossEncoderReranker
from app.agents.base import create_llm
from app.utils.prompts import PARENTING_AGENT_PROMPT
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# LLM with low temperature for factual accuracy
llm = create_llm(temperature=0.3)


# ============================================================================
# Helper Functions
# ============================================================================

def _format_parenting_documents(docs: list[Document]) -> str:
    """Format retrieved parenting documents for LLM consumption.

    This formatting is necessary to provide clear structure and source attribution
    for the LLM to generate accurate parenting advice.

    Args:
        docs: List of retrieved documents

    Returns:
        Markdown-formatted string with document information
    """
    if not docs:
        return "No relevant information found in the knowledge base."

    formatted = "# Retrieved Parenting Knowledge\n\n"
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown")
        formatted += f"## Source {i}: {source}\n\n"
        formatted += f"{doc.content}\n\n"
        formatted += "---\n\n"

    return formatted


# ============================================================================
# Tools
# ============================================================================

@tool
async def search_parenting_knowledge(
    query: str,
    state: Annotated[dict, "InjectedState"]
) -> str:
    """Search the parenting knowledge base for expert advice and strategies.

    Use this tool to find information about:
    - Child development stages and milestones
    - Age-appropriate parenting strategies
    - Behavior management techniques
    - Sleep training and feeding advice
    - Emotional regulation and discipline
    - Common parenting challenges

    Args:
        query: Search query about parenting or child development

    Returns:
        Formatted information from relevant documents
    """
    retriever: DocumentRetriever = state["retriever"]
    reranker: CrossEncoderReranker = state.get("reranker")

    # Retrieve documents
    docs = await retriever.search(query, top_k=settings.top_k_documents * 2)

    if not docs:
        return "No relevant information found in the knowledge base."

    # Rerank if reranker available
    if reranker:
        docs = await reranker.rerank(query, docs, top_k=settings.top_k_documents)

    # Store documents in state for grading
    state["documents"] = docs

    logger.debug(f"Retrieved {len(docs)} documents for query: {query}")
    return _format_parenting_documents(docs)


# ============================================================================
# Node Functions
# ============================================================================

def agent_decision_node(state: ParentingRAGState) -> ParentingRAGState:
    """Agent decides whether to retrieve information or answer directly.

    Uses LLM with tool calling to determine if knowledge base search is needed.
    If the query is simple or conversational, may answer without retrieval.

    Args:
        state: Current RAG state

    Returns:
        Updated state with agent decision (tool_calls or direct message)
    """
    logger.debug("Agent making retrieval decision")

    # Get last user message
    messages = state.get("messages", [])
    if not messages:
        return state

    last_message = messages[-1]

    # Create agent prompt with parenting expertise
    system_message = HumanMessage(content=PARENTING_AGENT_PROMPT)

    # Invoke LLM with tools
    retriever = state.get("retriever")
    reranker = state.get("reranker")

    # Inject retriever and reranker for tool access
    state_with_deps = {
        **state,
        "retriever": retriever,
        "reranker": reranker,
    }

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools([search_parenting_knowledge])

    # Invoke with system message + conversation
    response = llm_with_tools.invoke([system_message] + messages)

    # Add response to messages
    return {
        **state,
        "messages": messages + [response],
    }


def tools_node_factory(retriever: DocumentRetriever, reranker: CrossEncoderReranker):
    """Factory to create tools node with captured retriever and reranker.

    Args:
        retriever: Document retriever instance
        reranker: Document reranker instance

    Returns:
        ToolNode configured with parenting tools
    """
    # Create ToolNode with parenting tool
    tool_node = ToolNode([search_parenting_knowledge])

    def tools_wrapper(state: ParentingRAGState) -> ParentingRAGState:
        """Execute tool calls with injected dependencies."""
        # Inject retriever and reranker into state for tool access
        state_with_deps = {
            **state,
            "retriever": retriever,
            "reranker": reranker,
        }

        # Execute tools
        result = tool_node.invoke(state_with_deps)

        # Return updated state
        return result

    return tools_wrapper


def grade_documents_node(state: ParentingRAGState) -> ParentingRAGState:
    """Filter documents by relevance using LLM grading.

    Grades each document for relevance to the user's question.
    Only keeps documents with relevance score >= 0.5.

    Args:
        state: Current RAG state with documents

    Returns:
        Updated state with filtered_documents and relevance_scores
    """
    logger.debug("Grading document relevance")

    documents = state.get("documents", [])
    question = state.get("question", "")

    if not documents:
        logger.warning("No documents to grade")
        return {
            **state,
            "filtered_documents": [],
            "relevance_scores": [],
        }

    # Simple relevance grading using LLM
    filtered_docs = []
    relevance_scores = []

    for doc in documents:
        # Create grading prompt
        grading_prompt = f"""Grade the relevance of this document to the question.

Question: {question}

Document: {doc.content[:500]}...

Is this document relevant? Respond with only a number between 0.0 (not relevant) and 1.0 (highly relevant)."""

        response = llm.invoke([HumanMessage(content=grading_prompt)])

        try:
            # Extract score from response
            score_text = response.content.strip()
            score = float(score_text)

            relevance_scores.append(score)

            # Keep documents with score >= 0.5
            if score >= 0.5:
                filtered_docs.append(doc)
                logger.debug(f"Document passed grading with score {score:.2f}")
            else:
                logger.debug(f"Document filtered out with score {score:.2f}")

        except ValueError:
            logger.warning(f"Failed to parse relevance score: {response.content}")
            # Default to keeping document if parsing fails
            relevance_scores.append(0.5)
            filtered_docs.append(doc)

    logger.info(f"Filtered {len(filtered_docs)}/{len(documents)} documents as relevant")

    return {
        **state,
        "filtered_documents": filtered_docs,
        "relevance_scores": relevance_scores,
    }


def check_quality_node(state: ParentingRAGState) -> ParentingRAGState:
    """Assess retrieval quality to determine if query rewriting is needed.

    Checks:
    - Number of filtered documents (need at least 1)
    - Average relevance score (should be >= 0.6)
    - Maximum retrieval attempts (max 2)

    Args:
        state: Current RAG state

    Returns:
        Updated state with should_rewrite flag
    """
    logger.debug("Checking retrieval quality")

    filtered_docs = state.get("filtered_documents", [])
    relevance_scores = state.get("relevance_scores", [])
    attempts = state.get("retrieval_attempts", 0)

    # Check if we have good retrieval results
    has_docs = len(filtered_docs) > 0
    avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    good_quality = avg_score >= 0.6
    max_attempts_reached = attempts >= 2

    # Determine if rewrite is needed
    should_rewrite = (not has_docs or not good_quality) and not max_attempts_reached

    logger.info(
        f"Quality check: docs={len(filtered_docs)}, avg_score={avg_score:.2f}, "
        f"attempts={attempts}, should_rewrite={should_rewrite}"
    )

    return {
        **state,
        "should_rewrite": should_rewrite,
        "retrieval_attempts": attempts + 1,
    }


def rewrite_query_node(state: ParentingRAGState) -> ParentingRAGState:
    """Rewrite query to improve retrieval results.

    Uses LLM to generate a better query based on the original question
    and previous retrieval failures.

    Args:
        state: Current RAG state

    Returns:
        Updated state with rewritten question
    """
    logger.debug("Rewriting query for better retrieval")

    question = state.get("question", "")
    attempts = state.get("retrieval_attempts", 0)

    rewrite_prompt = f"""The original query did not retrieve good results.
Rewrite it to improve retrieval of parenting advice and child development information.

Original query: {question}

Attempt: {attempts}/2

Provide a rewritten query that:
1. Adds relevant context about parenting and child development
2. Uses terminology common in parenting literature
3. Specifies age ranges or developmental stages if applicable

Respond with only the rewritten query, no explanation."""

    response = llm.invoke([HumanMessage(content=rewrite_prompt)])
    rewritten_query = response.content.strip()

    logger.info(f"Rewrote query: '{question}' → '{rewritten_query}'")

    return {
        **state,
        "question": rewritten_query,
    }


def generate_answer_node(state: ParentingRAGState) -> ParentingRAGState:
    """Generate final answer from filtered documents.

    Synthesizes information from relevant documents to answer the user's question.
    Includes proper citations and age-appropriate advice.

    Args:
        state: Current RAG state

    Returns:
        Updated state with generation
    """
    logger.debug("Generating answer from filtered documents")

    filtered_docs = state.get("filtered_documents", [])
    question = state.get("question", "")
    user_context = state.get("user_context", {})

    if not filtered_docs:
        generation = (
            "I don't have enough reliable information to answer this question. "
            "Please consult a pediatrician or child development specialist for personalized advice."
        )
        return {
            **state,
            "generation": generation,
            "confidence": 0.0,
        }

    # Format documents for generation
    docs_text = "\n\n".join([
        f"Source {i+1}: {doc.content}"
        for i, doc in enumerate(filtered_docs)
    ])

    # Create generation prompt
    child_age = user_context.get("child_age", "")
    age_context = f"\n\nChild's age: {child_age} years old" if child_age else ""

    generation_prompt = f"""Answer the following parenting question using the provided sources.

Question: {question}{age_context}

Sources:
{docs_text}

Instructions:
1. Provide practical, actionable advice
2. Consider the child's age and developmental stage
3. Explain the reasoning behind your recommendations
4. Cite specific sources when possible
5. Be empathetic and encouraging
6. If unsure, acknowledge uncertainty

Answer:"""

    response = llm.invoke([HumanMessage(content=generation_prompt)])
    generation = response.content.strip()

    # Extract sources
    sources = [
        {
            "source": doc.metadata.get("source", "Unknown"),
            "timestamp": doc.metadata.get("timestamp", ""),
            "relevance": score,
        }
        for doc, score in zip(filtered_docs, state.get("relevance_scores", []))
    ]

    logger.info(f"Generated answer with {len(filtered_docs)} sources")

    return {
        **state,
        "generation": generation,
        "sources": sources,
    }


def confidence_check_node(state: ParentingRAGState) -> ParentingRAGState:
    """Calculate and validate confidence in generated answer.

    Confidence formula:
    confidence = (avg_relevance_score * 0.7) + (min(doc_count / 5, 1.0) * 0.3)

    Threshold: 0.6 for high confidence

    Args:
        state: Current RAG state

    Returns:
        Updated state with confidence score
    """
    logger.debug("Checking generation confidence")

    relevance_scores = state.get("relevance_scores", [])
    filtered_docs = state.get("filtered_documents", [])

    if not relevance_scores or not filtered_docs:
        confidence = 0.0
    else:
        # Calculate confidence
        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        doc_coverage = min(len(filtered_docs) / 5.0, 1.0)
        confidence = (avg_relevance * 0.7) + (doc_coverage * 0.3)

    logger.info(f"Generation confidence: {confidence:.2f}")

    return {
        **state,
        "confidence": confidence,
    }


# ============================================================================
# Routing Functions
# ============================================================================

def route_after_agent(state: ParentingRAGState) -> Literal["tools", "generate_answer"]:
    """Route after agent decision based on tool calls.

    If agent decided to use tools → route to tools node
    Otherwise → route directly to generate_answer (no retrieval needed)

    Args:
        state: Current RAG state

    Returns:
        Next node name
    """
    messages = state.get("messages", [])
    if not messages:
        return "generate_answer"

    last_message = messages[-1]

    # Check if last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.debug("Agent requested tool calls, routing to tools")
        return "tools"

    logger.debug("Agent answered directly, skipping retrieval")
    return "generate_answer"


def route_after_quality(
    state: ParentingRAGState,
) -> Literal["rewrite_query", "generate_answer"]:
    """Route after quality check based on should_rewrite flag.

    If poor quality and attempts < 2 → rewrite_query
    Otherwise → generate_answer (accept current results)

    Args:
        state: Current RAG state

    Returns:
        Next node name
    """
    should_rewrite = state.get("should_rewrite", False)

    if should_rewrite:
        logger.debug("Poor retrieval quality, routing to rewrite_query")
        return "rewrite_query"

    logger.debug("Good retrieval quality or max attempts, routing to generate_answer")
    return "generate_answer"


def route_after_confidence(
    state: ParentingRAGState,
) -> Literal["insufficient_info", END]:
    """Route after confidence check based on confidence threshold.

    If confidence < 0.6 → insufficient_info response
    Otherwise → END (return answer)

    Args:
        state: Current RAG state

    Returns:
        Next node name or END
    """
    confidence = state.get("confidence", 0.0)

    if confidence < 0.6:
        logger.warning(f"Low confidence ({confidence:.2f}), routing to insufficient_info")
        return "insufficient_info"

    logger.info(f"High confidence ({confidence:.2f}), returning answer")
    return END


def insufficient_info_node(state: ParentingRAGState) -> Command[Literal[END]]:
    """Handle low confidence responses with insufficient information message.

    Args:
        state: Current RAG state

    Returns:
        Command with insufficient info message
    """
    logger.debug("Generating insufficient information response")

    messages = state.get("messages", [])

    response = AIMessage(
        content=(
            "I don't have enough reliable information to answer this question confidently. "
            "For personalized parenting advice, I recommend:\n\n"
            "1. Consulting with your child's pediatrician\n"
            "2. Speaking with a child development specialist\n"
            "3. Contacting a licensed family therapist\n\n"
            "Every child is unique, and professional guidance can help address your specific situation."
        )
    )

    return Command(goto=END, update={"messages": messages + [response]})


# ============================================================================
# Graph Factory
# ============================================================================

def create_parenting_rag_agent(
    retriever: DocumentRetriever,
    reranker: CrossEncoderReranker,
) -> StateGraph:
    """Create compiled parenting RAG agent graph.

    This creates a multi-node LangGraph with corrective RAG:
    1. Agent decides to retrieve or answer directly
    2. Tools node executes retrieval if needed
    3. Grade documents by relevance
    4. Check quality and rewrite query if poor (max 2 attempts)
    5. Generate answer from filtered documents
    6. Check confidence and return or fallback

    Args:
        retriever: Document retriever instance
        reranker: Document reranker instance

    Returns:
        Compiled StateGraph[ParentingRAGState]
    """
    logger.info("Creating parenting RAG agent graph")

    # Create graph
    builder = StateGraph(ParentingRAGState)

    # Create tools node with captured dependencies
    tools_node = tools_node_factory(retriever, reranker)

    # Add nodes
    builder.add_node("agent_decision", agent_decision_node)
    builder.add_node("tools", tools_node)
    builder.add_node("grade_documents", grade_documents_node)
    builder.add_node("check_quality", check_quality_node)
    builder.add_node("rewrite_query", rewrite_query_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("confidence_check", confidence_check_node)
    builder.add_node("insufficient_info", insufficient_info_node)

    # Define edges
    # Start at agent decision
    builder.add_edge(START, "agent_decision")

    # Route after agent decision
    builder.add_conditional_edges(
        "agent_decision",
        route_after_agent,
        {
            "tools": "tools",
            "generate_answer": "generate_answer",
        },
    )

    # After tools, grade documents
    builder.add_edge("tools", "grade_documents")

    # After grading, check quality
    builder.add_edge("grade_documents", "check_quality")

    # Route after quality check
    builder.add_conditional_edges(
        "check_quality",
        route_after_quality,
        {
            "rewrite_query": "rewrite_query",
            "generate_answer": "generate_answer",
        },
    )

    # After rewrite, loop back to agent decision
    builder.add_edge("rewrite_query", "agent_decision")

    # After generate, check confidence
    builder.add_edge("generate_answer", "confidence_check")

    # Route after confidence check
    builder.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {
            "insufficient_info": "insufficient_info",
            END: END,
        },
    )

    # Insufficient info goes to END
    builder.add_edge("insufficient_info", END)

    # Compile without checkpointing (outer graph handles persistence)
    graph = builder.compile(checkpointer=False)

    logger.info("Parenting RAG agent graph compiled successfully")
    return graph


# ============================================================================
# Main Graph Integration
# ============================================================================

def parenting_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """Parenting agent node for integration with main graph.

    Converts MedicalChatState to ParentingRAGState, invokes the agent,
    and returns updated messages.

    Args:
        state: Current medical chat state

    Returns:
        Command with agent response
    """
    # Get parenting agent and dependencies from state
    parenting_agent = state.get("_parenting_agent")
    retriever = state.get("retriever")
    reranker = state.get("reranker")

    if not parenting_agent or not retriever:
        raise ValueError("Parenting agent or retriever not initialized in state")

    logger.debug(f"Session {state['session_id']}: Parenting agent processing request")

    # Extract question from last message
    messages = state.get("messages", [])
    question = messages[-1].content if messages else ""

    # Extract user context (e.g., child age from previous messages)
    user_context = {}
    # TODO: Add context extraction logic if needed

    # Create ParentingRAGState
    rag_state = ParentingRAGState(
        messages=messages,
        question=question,
        user_context=user_context,
        retriever=retriever,
        reranker=reranker,
    )

    # Invoke parenting agent
    response = parenting_agent.invoke(rag_state)

    # Return command with updated messages
    return Command(goto=END, update={"messages": response["messages"]})


def create_parenting_node(
    retriever: DocumentRetriever,
    reranker: CrossEncoderReranker,
):
    """Factory function to create parenting node with closure-captured dependencies.

    Linus: "Good code has no special cases" - This unified pattern eliminates
    the serialization problem by capturing non-serializable objects in closure.

    Architecture:
    - Outer graph uses MemorySaver to checkpoint conversation state (messages, session_id)
    - parenting_agent, retriever, and reranker are NOT serializable, captured in closure
    - Only serializable data gets persisted to checkpointer

    Args:
        retriever: Parenting document retriever instance (non-serializable)
        reranker: Cross-encoder reranker instance (non-serializable)

    Returns:
        Node function ready to be added to LangGraph
    """
    # Create parenting RAG agent in closure (captured, not checkpointed)
    parenting_agent = create_parenting_rag_agent(retriever, reranker)
    logger.debug("Parenting RAG agent created and captured in closure")

    def parenting_node(state: MedicalChatState) -> Command[Literal[END]]:
        """Parenting node with retriever and reranker injected via closure.

        Args:
            state: Current medical chat state (serializable only)

        Returns:
            Command with agent response and updated messages
        """
        logger.debug(f"Session {state['session_id']}: Parenting agent processing request")

        # Extract question from last message
        messages = state.get("messages", [])
        question = messages[-1].content if messages else ""

        # Extract user context (e.g., child age from previous messages)
        user_context = {}
        # TODO: Add context extraction logic if needed

        # Create ParentingRAGState with injected dependencies
        rag_state = ParentingRAGState(
            messages=messages,
            question=question,
            user_context=user_context,
            retriever=retriever,
            reranker=reranker,
        )

        # Invoke parenting agent
        response = parenting_agent.invoke(rag_state)

        # Return only serializable updates
        return Command(goto=END, update={"messages": response["messages"]})

    return parenting_node
