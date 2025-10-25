"""LangChain tools for agentic RAG parenting system.

This module provides specialized tools for multi-step RAG operations including:
- Hybrid search with reranking
- Multi-query generation for comprehensive retrieval
- Document relevance grading with LLM
- Query rewriting for improved results
"""

from typing import List, Annotated, Dict
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.prebuilt import InjectedState
from app.core.retriever import Document, DocumentRetriever
from app.agents.base import create_llm
from app.config import settings
import logging

logger = logging.getLogger(__name__)


# LLM instances with different temperatures for different tasks
llm_query_gen = create_llm(temperature=0.3)  # Balanced creativity for query variations
llm_grading = create_llm(temperature=0.1)  # Consistent, deterministic grading
llm_rewrite = create_llm(temperature=0.3)  # Balanced for query improvement


class RelevanceGrade(BaseModel):
    """Structured output for document relevance grading."""

    score: float = Field(
        description="Relevance score between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description="Explanation of why this score was assigned",
    )
    relevant: bool = Field(
        description="Whether document is relevant (score >= 0.5)",
    )


@tool
async def search_parenting_knowledge(
    query: str, state: Annotated[dict, InjectedState]
) -> str:
    """Search parenting knowledge base for advice on sleep, behavior, development, etc.

    This tool performs hybrid search (semantic + keyword) with reranking to find
    the most relevant parenting advice from the knowledge base.

    Use this tool to find information about:
    - Sleep training and bedtime routines
    - Behavioral challenges (tantrums, aggression, defiance)
    - Developmental milestones and concerns
    - Feeding and nutrition advice
    - Social-emotional development
    - Discipline strategies
    - School readiness and learning

    Args:
        query: Search query about parenting topic or specific question
        state: Injected state containing hybrid_retriever

    Returns:
        Formatted information from relevant documents with timestamps and sources

    Example:
        >>> result = await search_parenting_knowledge(
        ...     "How do I handle toddler tantrums?",
        ...     state
        ... )
    """
    # Get hybrid retriever from state
    retriever: DocumentRetriever = state.get("hybrid_retriever")
    if not retriever:
        logger.error("Hybrid retriever not found in state")
        return "Error: Knowledge base retriever not initialized."

    # Perform hybrid search with reranking
    try:
        docs = await retriever.search(query, top_k=settings.top_k_documents)

        if not docs:
            return "No relevant parenting advice found for this query. Try rephrasing or providing more context."

        # Format documents with rich metadata
        formatted = "# Retrieved Parenting Advice\n\n"
        for i, doc in enumerate(docs, 1):
            # Extract metadata
            source_url = doc.metadata.get("url", "Unknown source")
            title = doc.metadata.get("title", "Untitled")
            timestamp = doc.metadata.get("timestamp", "Unknown date")
            chunk_id = doc.metadata.get("chunk_id", "N/A")

            # Format document
            formatted += f"## Source {i}: {title}\n\n"
            formatted += f"**URL:** {source_url}\n"
            formatted += f"**Published:** {timestamp}\n"
            formatted += f"**Chunk ID:** {chunk_id}\n\n"
            formatted += f"{doc.content}\n\n"
            formatted += "---\n\n"

        logger.debug(f"Retrieved {len(docs)} documents for query: {query}")
        return formatted

    except Exception as e:
        logger.error(f"Error during parenting knowledge search: {e}")
        return f"Error searching knowledge base: {str(e)}"


@tool
def generate_multi_queries(question: str) -> List[str]:
    """Generate multiple query variations for comprehensive retrieval.

    Creates 3-4 variations of the original question from different angles:
    - Abstract/general perspective
    - Specific/detailed perspective
    - Contextual/situational perspective
    - Alternative phrasing

    This improves retrieval coverage by capturing different aspects of the question.

    Args:
        question: Original user question about parenting

    Returns:
        List of 3-4 query variations (including original)

    Example:
        >>> queries = generate_multi_queries("How do I handle toddler tantrums?")
        >>> # Returns: [
        >>> #   "How do I handle toddler tantrums?",
        >>> #   "Managing emotional outbursts in young children",
        >>> #   "Toddler tantrum prevention and de-escalation strategies",
        >>> #   "Why do toddlers have tantrums and how to respond"
        >>> # ]
    """
    prompt = ChatPromptTemplate.from_template(
        """You are an expert at generating search queries for parenting advice.

Given the original question, generate 3 alternative query variations that capture different aspects:
1. A more abstract/general version
2. A more specific/detailed version
3. A contextual/situational version

Original question: {question}

Generate the 3 alternative queries, one per line. Do not number them or add explanations.
Just provide 3 distinct queries that would retrieve different relevant information."""
    )

    chain = prompt | llm_query_gen | StrOutputParser()

    try:
        # Generate variations
        response = chain.invoke({"question": question})

        # Parse response into list
        variations = [q.strip() for q in response.strip().split("\n") if q.strip()]

        # Always include original question
        queries = [question] + variations[:3]  # Limit to 3 variations

        logger.debug(f"Generated {len(queries)} query variations for: {question}")
        return queries

    except Exception as e:
        logger.error(f"Error generating multi-queries: {e}")
        # Fallback to original question only
        return [question]


@tool
def grade_document_relevance(question: str, document: Document) -> Dict[str, any]:
    """Grade document relevance to the question using LLM with structured output.

    Uses an LLM to assess whether a retrieved document is relevant to answering
    the user's question. Returns a score, reasoning, and binary relevance decision.

    Threshold: score >= 0.5 is considered relevant.

    Args:
        question: Original user question
        document: Retrieved document to grade

    Returns:
        Dictionary with:
        - score (float): Relevance score [0.0, 1.0]
        - reasoning (str): Explanation of the score
        - relevant (bool): True if score >= 0.5

    Example:
        >>> doc = Document(content="Toddlers have tantrums due to...", metadata={})
        >>> result = grade_document_relevance(
        ...     "How do I handle toddler tantrums?",
        ...     doc
        ... )
        >>> # Returns: {"score": 0.85, "reasoning": "...", "relevant": True}
    """
    prompt = ChatPromptTemplate.from_template(
        """You are an expert at evaluating document relevance for parenting questions.

Question: {question}

Document:
{document_content}

Evaluate if this document is relevant for answering the question.

Consider:
- Does it directly address the question topic?
- Does it provide actionable advice or useful context?
- Is the information accurate and appropriate for parenting?

Provide:
1. A relevance score between 0.0 (completely irrelevant) and 1.0 (highly relevant)
2. Brief reasoning for the score
3. Binary decision: relevant if score >= 0.5

Be strict but fair. Documents should be clearly on-topic to be considered relevant."""
    )

    # Create chain with structured output
    chain = prompt | llm_grading.with_structured_output(RelevanceGrade)

    try:
        # Grade document
        result = chain.invoke({
            "question": question,
            "document_content": document.content[:2000]  # Limit content length
        })

        logger.debug(
            f"Graded document relevance: score={result.score:.2f}, "
            f"relevant={result.relevant}"
        )

        return {
            "score": result.score,
            "reasoning": result.reasoning,
            "relevant": result.relevant,
        }

    except Exception as e:
        logger.error(f"Error grading document relevance: {e}")
        # Default to neutral score on error
        return {
            "score": 0.5,
            "reasoning": f"Error during grading: {str(e)}",
            "relevant": True,  # Conservative: include document if grading fails
        }


@tool
def rewrite_query(original_query: str, retrieval_context: str) -> str:
    """Rewrite query to improve retrieval results based on previous failures.

    Uses an LLM to analyze why the original query didn't retrieve good results
    and generates an improved version that's more likely to succeed.

    Args:
        original_query: The original user question that failed to retrieve relevant docs
        retrieval_context: Information about what went wrong (e.g., "no relevant documents",
            "documents were off-topic about sleep instead of behavior")

    Returns:
        Improved query string that addresses retrieval failures

    Example:
        >>> improved = rewrite_query(
        ...     "My kid won't listen",
        ...     "No relevant documents found. Query too vague."
        ... )
        >>> # Returns: "How to get toddlers to follow instructions and improve listening skills"
    """
    prompt = ChatPromptTemplate.from_template(
        """You are an expert at improving search queries for parenting advice.

Original query: {original_query}

Retrieval context (what went wrong): {retrieval_context}

Analyze why the original query failed and generate an improved version that:
1. Is more specific and descriptive
2. Uses common parenting terminology
3. Targets the core intent of the question
4. Is likely to match relevant documents

Provide ONLY the improved query, nothing else."""
    )

    chain = prompt | llm_rewrite | StrOutputParser()

    try:
        # Rewrite query
        improved_query = chain.invoke({
            "original_query": original_query,
            "retrieval_context": retrieval_context,
        })

        improved_query = improved_query.strip()
        logger.debug(f"Rewrote query: '{original_query}' -> '{improved_query}'")
        return improved_query

    except Exception as e:
        logger.error(f"Error rewriting query: {e}")
        # Fallback to original query
        return original_query


# Export all tools for easy import
__all__ = [
    "search_parenting_knowledge",
    "generate_multi_queries",
    "grade_document_relevance",
    "rewrite_query",
]
