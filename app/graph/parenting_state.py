"""State schema for agentic RAG parenting agent.

This module defines the state structure for the multi-step RAG graph that powers
the parenting advice system. The state extends LangGraph's MessagesState to track
query processing, retrieval results, generation output, and quality metrics across
multiple graph nodes.
"""

from typing import List, Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from app.core.retriever import Document


class ParentingRAGState(MessagesState):
    """State for agentic RAG parenting agent.

    Extends MessagesState to include RAG-specific fields for multi-step retrieval,
    query rewriting, document grading, and generation with quality tracking.

    Attributes:
        question (str): Original user question about parenting.
        queries (List[str]): Multi-query variations for comprehensive retrieval.
            Generated from the original question to capture different aspects
            (e.g., abstract, specific, contextual perspectives).

        documents (List[Document]): Raw retrieval results from hybrid search.
            Contains all documents retrieved before filtering and grading.
        filtered_documents (List[Document]): High-quality documents after relevance grading.
            Only includes documents that pass the relevance threshold (score >= 0.5).

        generation (str): Final generated response to the user's question.
            Synthesized from filtered_documents with proper citations.

        retrieval_attempts (int): Number of retrieval cycles attempted.
            Used to prevent infinite loops in query rewriting (max 3 attempts).
        should_rewrite (bool): Flag indicating if query should be rewritten.
            Set to True when filtered_documents is empty or quality is poor.

        relevance_scores (List[float]): Relevance scores for each retrieved document.
            Parallel to documents list, range [0.0, 1.0], used for quality metrics.
        confidence (float): Overall confidence score for the generation.
            Computed from relevance_scores and document count (range [0.0, 1.0]).

        sources (List[dict]): Metadata for cited sources in generation.
            Each dict contains: {url, title, timestamp, chunk_id, relevance_score}.
        user_context (dict): User-specific context for personalized responses.
            May include: {child_age, previous_topics, preferences, language}.

    Example:
        >>> state = ParentingRAGState(
        ...     question="How do I handle toddler tantrums?",
        ...     user_context={"child_age": 2, "language": "en"}
        ... )
    """

    # Query processing
    question: str = ""
    """Original user question about parenting."""

    queries: List[str] = []
    """Multi-query variations for comprehensive retrieval (3-4 variations)."""

    # Retrieval results
    documents: List[Document] = []
    """Raw retrieval results from hybrid search (before filtering)."""

    filtered_documents: List[Document] = []
    """High-quality documents after relevance grading (score >= 0.5)."""

    # Generation
    generation: str = ""
    """Final generated response with proper citations."""

    # Control flow
    retrieval_attempts: int = 0
    """Number of retrieval cycles attempted (max 3 to prevent loops)."""

    should_rewrite: bool = False
    """Flag indicating if query should be rewritten due to poor results."""

    # Quality metrics
    relevance_scores: List[float] = []
    """Relevance scores for each document (parallel to documents list)."""

    confidence: float = 0.0
    """Overall confidence score for generation (range [0.0, 1.0])."""

    # Metadata
    sources: List[dict] = []
    """Metadata for cited sources: [{url, title, timestamp, chunk_id, score}]."""

    user_context: dict = {}
    """User-specific context: {child_age, previous_topics, preferences, language}."""
