"""
Contract: DocumentRetriever Interface

This contract defines the interface that PostgreSQLRetriever must implement
for drop-in compatibility with the existing RAG agent.

Status: IMMUTABLE (changing this breaks RAG agent integration)
Reference: app/core/retriever.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List


@dataclass
class Document:
    """
    Document dataclass representing a search result.

    This is the EXISTING data structure from app/core/retriever.py.
    PostgreSQLRetriever MUST return results in this format.
    """

    content: str
    metadata: Dict[str, Any]
    id: str
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRetriever(ABC):
    """
    Abstract base class for document retrieval.

    PostgreSQLRetriever must implement this interface to be compatible
    with the existing RAG agent (app/agents/rag_agent.py).

    Key Constraints:
    - search() must be async (LangGraph agents use async/await)
    - Return type must be List[Document] (not custom types)
    - filters parameter must support Dict[str, Any] format

    Note: add_documents() is NOT part of this interface. All indexing
    is done via separate CLI script (src/embeddings/cli.py), not through
    the retriever interface.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Search for documents using natural language query.

        Args:
            query: Natural language search query (e.g., "side effects of aripiprazole")
            top_k: Number of results to return (default: 5)
            filters: Optional metadata filters (e.g., {"source_document": "02_aripiprazole"})

        Returns:
            List of Document objects, ranked by relevance (highest first)

        Raises:
            ValueError: If query is empty or invalid
            ConnectionError: If database connection fails
            RuntimeError: If embedding generation fails
        """
        pass


# Contract Test Requirements
"""
PostgreSQLRetriever MUST pass the following contract tests:

1. Interface Compliance:
   - Inherits from DocumentRetriever
   - Implements search() method with correct signature
   - Does NOT implement add_documents() (indexing is CLI-only)

2. Async Behavior:
   - search() returns awaitable coroutine

3. Return Type Validation:
   - search() returns List[Document] (not custom types)
   - Each Document has required fields: content, metadata, id

4. Error Handling:
   - Raises ValueError for empty queries
   - Raises ConnectionError for database failures
   - Raises RuntimeError for embedding generation failures

5. Metadata Compatibility:
   - Document.metadata contains: source_document, chapter_title, section_title
   - Document.metadata contains: similarity_score, rerank_score (both mandatory)
   - Document.metadata values are JSON-serializable

6. Filter Support:
   - filters={"source_document": "02_aripiprazole"} returns only matching docs
   - filters=None returns all results (no filtering)

7. Ranking Behavior:
   - Results ordered by rerank_score (highest first)
   - Reranking is always enabled (mandatory)
   - top_k=5 returns exactly 5 results (or fewer if not enough matches)

Test Location: tests/contract/test_retriever_interface.py
"""
