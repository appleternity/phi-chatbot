"""Base retrieval protocol for all strategies.

This defines the interface that all retrieval strategies must implement.
"""

from typing import Protocol, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage


class RetrieverProtocol(Protocol):
    """Protocol defining the interface for all retrieval strategies."""

    async def search(
        self,
        query: List[BaseMessage],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents using conversation history.

        Args:
            query: List of conversation messages for context-aware retrieval.
                   Each retriever strategy decides how much history to use:
                   - SimpleRetriever: Last human message only (max_history=1)
                   - RerankRetriever: Last human message only (max_history=1)
                   - AdvancedRetriever: Last 5 messages for query expansion context
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of dictionaries with keys:
                - chunk_id: str
                - chunk_text: str
                - source_document: str
                - chapter_title: str
                - section_title: str
                - subsection_title: str (optional)
                - summary: str
                - token_count: int
                - similarity_score: float
                - rerank_score: float (if reranking used)

        Example:
            >>> # Pass conversation history for context-aware retrieval
            >>> messages = [
            ...     HumanMessage(content="Tell me about aripiprazole"),
            ...     AIMessage(content="Aripiprazole is an antipsychotic..."),
            ...     HumanMessage(content="What about side effects?")
            ... ]
            >>> results = await retriever.search(messages, top_k=5)
        """
        ...
