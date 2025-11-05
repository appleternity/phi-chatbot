"""
Data models for semantic search embedding and indexing pipeline.

This module defines Pydantic models for:
- ChunkMetadata: Metadata extracted from JSON chunk files
- VectorDocument: Document with embedding vector for database storage
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Chunk Metadata Models
# ==============================================================================

class ChunkMetadata(BaseModel):
    """
    Metadata for a single document chunk extracted from JSON files.

    Source: data/chunking_final/*.json files
    Example: 02_aripiprazole_chunk_017.json
    """
    chunk_id: str = Field(..., description="Unique chunk identifier")
    source_document: str = Field(..., description="Source document name")
    chapter_title: str = Field(default="", description="Chapter title")
    section_title: str = Field(default="", description="Section title")
    subsection_title: List[str] = Field(default_factory=list, description="Subsection titles (hierarchical)")
    summary: str = Field(default="", description="Content summary")
    token_count: int = Field(..., gt=0, description="Token count in chunk_text")
    chunk_text: str = Field(..., description="Full chunk text")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "02_aripiprazole_chunk_017",
                "source_document": "02_aripiprazole",
                "chapter_title": "Pharmacology",
                "section_title": "Mechanism of Action",
                "subsection_title": ["Dopamine Receptors", "Serotonin Receptors"],
                "summary": "Aripiprazole acts as partial agonist at D2 and 5-HT1A receptors",
                "token_count": 342,
                "chunk_text": "Aripiprazole is a partial agonist..."
            }
        }


class VectorDocument(ChunkMetadata):
    """
    Document chunk with embedding vector for database storage.

    Extends ChunkMetadata with:
    - embedding: Vector from embedding model (dimension determined by model)
    - created_at: Timestamp when embedding was generated
    """
    embedding: List[float] = Field(
        ...,
        description="Embedding vector (dimension varies by model)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: List[float]) -> List[float]:
        """Validate embedding values for NaN and infinity."""
        # Check for NaN or infinity
        for i, val in enumerate(v):
            if not isinstance(val, (int, float)):
                raise ValueError(f"Embedding value at index {i} is not numeric: {type(val)}")
            if val != val:  # NaN check
                raise ValueError(f"Embedding contains NaN at index {i}")
            if val == float('inf') or val == float('-inf'):
                raise ValueError(f"Embedding contains infinity at index {i}")

        return v


# ==============================================================================
# Search Query and Result Models
# ==============================================================================

class SearchQuery(BaseModel):
    """
    Natural language search query with metadata.

    Used for query-time semantic search requests.
    """
    query_text: str = Field(..., description="Natural language query")
    query_embedding: List[float] = Field(
        ...,
        description="Query vector (dimension varies by model)"
    )
    top_k: int = Field(
        default=20,
        ge=1,
        description="Number of results to retrieve"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata filters (e.g., source_document, chapter_title)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Query submission time"
    )


class SearchResult(BaseModel):
    """
    Single search result with similarity and reranking scores.

    Maps to Document dataclass for DocumentRetriever interface compatibility.
    """
    chunk_id: str = Field(..., description="Reference to VectorDocument")
    content: str = Field(..., description="Chunk text content")
    metadata: Dict[str, Any] = Field(..., description="Chunk metadata")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score from pgvector"
    )
    rerank_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Reranker score (mandatory, reranking always enabled)"
    )
    rank: int = Field(..., ge=1, description="Result position (1-indexed)")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "02_aripiprazole_chunk_017",
                "content": "Aripiprazole is a partial agonist...",
                "metadata": {
                    "source_document": "02_aripiprazole",
                    "chapter_title": "Pharmacology",
                    "section_title": "Mechanism of Action",
                    "subsection_title": ["Dopamine Receptors"],
                    "summary": "Aripiprazole mechanism of action",
                    "token_count": 342
                },
                "similarity_score": 0.87,
                "rerank_score": 0.92,
                "rank": 1
            }
        }
