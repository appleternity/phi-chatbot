"""Base retrieval protocol for all strategies.

This defines the interface that all retrieval strategies must implement.
"""

from typing import Protocol, List, Dict, Any, Optional


class RetrieverProtocol(Protocol):
    """Protocol defining the interface for all retrieval strategies."""

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: User's search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of dictionaries with keys:
                - chunk_id: str
                - chunk_text: str
                - source_document: str
                - chapter_title: str
                - section_title: str
                - similarity_score: float
                - rerank_score: float (if reranking used)
        """
        ...
