"""Abstract document retriever interface and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Document:
    """Document representation."""

    content: str
    metadata: dict
    id: Optional[str] = None
    parent_id: Optional[str] = None  # Reference to parent chunk
    child_ids: List[str] = field(default_factory=list)  # Child chunk IDs
    timestamp_start: Optional[str] = None  # "00:01:23.456"
    timestamp_end: Optional[str] = None  # "00:01:45.789"


class DocumentRetriever(ABC):
    """Abstract interface for document retrieval."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of most relevant documents
        """
        pass

    @abstractmethod
    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to the index.

        Args:
            docs: List of documents to add
        """
        pass
