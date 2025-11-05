# Data Model: Semantic Search with PostgreSQL and pgvector

**Feature Branch**: `002-semantic-search`
**Created**: 2025-11-02
**Related**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md)

## Overview

This document defines the data models for semantic search implementation, including embedding configuration, chunk metadata, vector storage, and search results. All models use Pydantic for validation and are designed for compatibility with the existing DocumentRetriever interface.

---

## Core Entities

### 1. ChunkMetadata

**Purpose**: Represents metadata for a single document chunk extracted from JSON files in `data/chunking_final`.

**Source**: Extracted from chunk JSON files (e.g., `02_aripiprazole_chunk_017.json`)

**Fields**:
- `chunk_id` (str): Unique identifier from source JSON (e.g., "02_aripiprazole_chunk_017")
- `source_document` (str): Origin filename without extension (e.g., "02_aripiprazole")
- `chapter_title` (str): Chapter or section title from source document
- `section_title` (str): Primary section title
- `subsection_title` (List[str]): List of all subsection titles (hierarchical)
- `summary` (str): Brief summary of chunk content (10-200 chars)
- `token_count` (int): Number of tokens in chunk_text
- `chunk_text` (str): Full text content for embedding

**Validation Rules**:
- `chunk_id` must be non-empty and unique
- `chunk_text` must have at least 10 characters (meaningful content)
- `token_count` must be positive integer
- `subsection_title` defaults to empty list if not present

**Pydantic Model**:
```python
from pydantic import BaseModel, Field
from typing import List

class ChunkMetadata(BaseModel):
    chunk_id: str = Field(..., min_length=1, description="Unique chunk identifier")
    source_document: str = Field(..., min_length=1, description="Source document name")
    chapter_title: str = Field(default="", description="Chapter title")
    section_title: str = Field(default="", description="Section title")
    subsection_title: List[str] = Field(default_factory=list, description="Subsection titles")
    summary: str = Field(default="", min_length=0, max_length=500, description="Content summary")
    token_count: int = Field(..., gt=0, description="Token count in chunk_text")
    chunk_text: str = Field(..., min_length=10, description="Full chunk text")
```

**Example**:
```json
{
  "chunk_id": "02_aripiprazole_chunk_017",
  "source_document": "02_aripiprazole",
  "chapter_title": "Pharmacology",
  "section_title": "Mechanism of Action",
  "subsection_title": ["Dopamine Receptors", "Serotonin Receptors"],
  "summary": "Aripiprazole acts as partial agonist at D2 and 5-HT1A receptors",
  "token_count": 342,
  "chunk_text": "Aripiprazole is a partial agonist..."
}
```

---

### 2. VectorDocument

**Purpose**: Represents a document chunk with its vector embedding, ready for storage in PostgreSQL with pgvector.

**Relationships**:
- Extends ChunkMetadata with embedding vector
- Maps to Document dataclass for DocumentRetriever interface compatibility

**Fields**:
- All fields from ChunkMetadata (inherited)
- `embedding` (List[float]): 1024-dimensional vector from Qwen3-Embedding-0.6B
- `created_at` (datetime): Timestamp when embedding was generated

**Validation Rules**:
- `embedding` must have exactly 1024 dimensions (Qwen3-Embedding-0.6B output)
- All embedding values must be finite floats (no NaN or infinity)
- `created_at` defaults to current UTC timestamp

**Pydantic Model**:
```python
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field, field_validator

class VectorDocument(ChunkMetadata):
    embedding: List[float] = Field(..., min_length=1024, max_length=1024, description="1024-dim embedding vector")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: List[float]) -> List[float]:
        if len(v) != 1024:
            raise ValueError("Embedding must have exactly 1024 dimensions")
        if not all(isinstance(x, (int, float)) and not (x != x or x == float('inf') or x == float('-inf')) for x in v):
            raise ValueError("Embedding contains invalid values (NaN or infinity)")
        return v
```

---

### 3. ~~EmbeddingConfig~~ (REMOVED)

**Status**: This configuration class has been removed to simplify the codebase.

**Replacement**: Use direct constructor parameters for `Qwen3EmbeddingEncoder`:

```python
from src.embeddings.encoder import Qwen3EmbeddingEncoder

# Before (with EmbeddingConfig):
# config = EmbeddingConfig(model_name="...", device="mps", batch_size=16)
# encoder = Qwen3EmbeddingEncoder(config)

# After (direct parameters):
encoder = Qwen3EmbeddingEncoder(
    model_name="Qwen/Qwen3-Embedding-0.6B",  # default
    device="mps",  # "mps", "cuda", or "cpu"
    batch_size=16,  # 1-128
    max_length=8196,  # 128-32768
    normalize_embeddings=True,  # default
    instruction=None  # optional
)
```

**Parameters** (same as before):
- `model_name`: Hugging Face model identifier
- `device`: Device for inference ("mps", "cuda", "cpu") with automatic fallback
- `batch_size`: Batch size for embedding generation (1-128)
- `max_length`: Maximum token length for inputs (128-32768)
- `normalize_embeddings`: Whether to L2-normalize embeddings
- `instruction`: Task-specific instruction prefix (optional)

---

### 4. SearchQuery

**Purpose**: Represents a user's natural language search input with metadata.

**Fields**:
- `query_text` (str): User's natural language query
- `query_embedding` (List[float]): 1024-dimensional vector representation
- `top_k` (int): Number of results to retrieve (default: 20 for reranking)
- `filters` (Optional[Dict[str, Any]]): Metadata filters (e.g., source_document, chapter_title)
- `timestamp` (datetime): Query submission time

**Validation Rules**:
- `query_text` must be non-empty (at least 3 characters)
- `query_embedding` must have exactly 1024 dimensions
- `top_k` must be positive integer (typically 5-20)

**Pydantic Model**:
```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

class SearchQuery(BaseModel):
    query_text: str = Field(..., min_length=3, description="Natural language query")
    query_embedding: List[float] = Field(..., min_length=1024, max_length=1024, description="Query vector")
    top_k: int = Field(default=20, ge=1, le=100, description="Number of results to retrieve")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Query time")
```

---

### 5. SearchResult

**Purpose**: Represents a single search result with similarity and reranking scores.

**Relationships**:
- Links SearchQuery to VectorDocument
- Maps to Document dataclass for DocumentRetriever interface

**Fields**:
- `chunk_id` (str): Reference to VectorDocument
- `content` (str): Chunk text (from VectorDocument.chunk_text)
- `metadata` (Dict[str, Any]): Chunk metadata (chapter, section, source)
- `similarity_score` (float): Cosine similarity from pgvector (0.0-1.0)
- `rerank_score` (float): Score from Qwen3-Reranker (0.0-1.0) - MANDATORY
- `rank` (int): Position in results (1-indexed)

**Validation Rules**:
- `similarity_score` must be in range [0.0, 1.0]
- `rerank_score` must be in range [0.0, 1.0] (required, reranking is always enabled)
- `rank` must be positive integer

**Pydantic Model**:
```python
from pydantic import BaseModel, Field
from typing import Dict, Any

class SearchResult(BaseModel):
    chunk_id: str = Field(..., description="Reference to VectorDocument")
    content: str = Field(..., min_length=10, description="Chunk text content")
    metadata: Dict[str, Any] = Field(..., description="Chunk metadata")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    rerank_score: float = Field(..., ge=0.0, le=1.0, description="Reranker score (mandatory)")
    rank: int = Field(..., ge=1, description="Result position (1-indexed)")
```

---

### 6. ~~RerankerConfig~~ (REMOVED)

**Status**: This configuration class has been removed to simplify the codebase.

**Replacement**: Use direct constructor parameters for `Qwen3Reranker`:

```python
from app.core.qwen3_reranker import Qwen3Reranker

# Before (with RerankerConfig):
# config = RerankerConfig(model_name="...", device="mps", batch_size=8)
# reranker = Qwen3Reranker.from_config(config)

# After (direct parameters):
reranker = Qwen3Reranker(
    model_name="Qwen/Qwen3-Reranker-0.6B",  # default
    device="mps",  # "mps", "cuda", or "cpu"
    batch_size=8,  # 1-32
    max_length=8192  # default
)
```

**Parameters** (same as before):
- `model_name`: Hugging Face model identifier
- `device`: Device for inference ("mps", "cuda", "cpu") with automatic fallback
- `batch_size`: Batch size for reranking (1-32)
- `max_length`: Maximum token length for inputs

**Note**: `top_k` and `candidate_count` are now controlled at the retriever level, not in the reranker configuration.

---

## Database Schema

### PostgreSQL Table: `vector_chunks`

**Purpose**: Store document chunks with embeddings for semantic search.

**Schema**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vector_chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    chapter_title TEXT,
    section_title TEXT,
    subsection_title TEXT[],  -- Array of subsection titles
    summary TEXT,
    token_count INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,  -- pgvector type
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- HNSW index for fast cosine similarity search
CREATE INDEX ON vector_chunks USING hnsw (embedding vector_cosine_ops);

-- Metadata indexes for filtering
CREATE INDEX idx_source_document ON vector_chunks(source_document);
CREATE INDEX idx_chapter_title ON vector_chunks(chapter_title);
```

**Key Design Decisions**:
- **Primary Key**: `chunk_id` ensures uniqueness and prevents duplicate indexing
- **Vector Type**: `vector(1024)` matches Qwen3-Embedding-0.6B output dimension
- **HNSW Index**: Optimal for query performance (~1.5ms vs 650ms sequential scan)
- **Cosine Distance**: `vector_cosine_ops` standard for text embeddings
- **Metadata Indexes**: Enable filtering by source_document and chapter_title
- **Timestamps**: Track when chunks were indexed and updated

---

## Interface Compatibility

### DocumentRetriever Interface Mapping

**Purpose**: Ensure PostgreSQLRetriever is drop-in compatible with FAISSRetriever.

**Existing Document Dataclass** (from `app/core/retriever.py`):
```python
@dataclass
class Document:
    content: str
    metadata: Dict[str, Any]
    id: str
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

**VectorDocument → Document Mapping**:
```python
def to_document(vector_doc: VectorDocument) -> Document:
    return Document(
        id=vector_doc.chunk_id,
        content=vector_doc.chunk_text,
        metadata={
            "source_document": vector_doc.source_document,
            "chapter_title": vector_doc.chapter_title,
            "section_title": vector_doc.section_title,
            "subsection_title": vector_doc.subsection_title,
            "summary": vector_doc.summary,
            "token_count": vector_doc.token_count,
        },
        parent_id=None,  # Not used in chunking pipeline
        child_ids=[],    # Not used in chunking pipeline
        created_at=vector_doc.created_at,
        updated_at=vector_doc.created_at,  # Same as created_at for batch indexing
    )
```

**DocumentRetriever Interface Compliance**:
```python
class PostgreSQLRetriever(DocumentRetriever):
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search for documents using semantic similarity.

        Args:
            query: Natural language search query
            top_k: Number of results to return (after reranking)
            filters: Metadata filters (e.g., {"source_document": "02_aripiprazole"})

        Returns:
            List of Document objects ranked by relevance
        """
        pass

    async def add_documents(self, documents: List[Document]) -> None:
        """
        Add documents to vector database (for compatibility).

        Note: This method is NOT used for batch indexing (separate CLI script).
        Provided for interface compatibility only.
        """
        pass
```

---

## State Transitions

### Indexing Pipeline State Flow

```
JSON File → ChunkMetadata → VectorDocument → PostgreSQL Storage
    ↓            ↓               ↓                 ↓
  Parse      Validate      Generate         Store with
 Metadata    Fields       Embedding         HNSW Index
```

**State Validation**:
- **Parse**: Validate JSON structure, extract chunk_text
- **Validate**: Pydantic validation (non-empty fields, token_count > 0)
- **Generate**: MPS-accelerated embedding, L2 normalization
- **Store**: Upsert to PostgreSQL, skip duplicates

### Search Query State Flow

```
User Query → SearchQuery → Vector Search → Candidate Results → Reranking → Final Results
    ↓            ↓              ↓                 ↓               ↓             ↓
  Parse     Generate      HNSW Lookup      Top-20 Chunks   Qwen3-Reranker  Top-5 Documents
 Query     Embedding     (cosine dist)   (similarity)     (rerank score)  (DocumentRetriever)
```

**State Validation**:
- **Parse**: Validate query length (≥3 chars), sanitize input
- **Generate**: Same embedding model as indexing (consistency)
- **HNSW Lookup**: Apply metadata filters, retrieve top-20 candidates
- **Reranking**: Qwen3-Reranker processes (query, chunk) pairs
- **Final**: Convert VectorDocument → Document, return top-5

---

## Validation Rules Summary

| Entity | Critical Validations |
|--------|---------------------|
| ChunkMetadata | chunk_id non-empty, chunk_text ≥10 chars, token_count > 0 |
| VectorDocument | embedding exactly 1024 dims, no NaN/infinity values |
| SearchQuery | query_text ≥3 chars, query_embedding 1024 dims, top_k > 0 |
| SearchResult | similarity_score [0.0, 1.0], rank ≥1 |

**Note**: EmbeddingConfig and RerankerConfig have been removed. Validation is now performed directly in constructor parameters.

---

## Implementation Checklist

- [ ] Define Pydantic models in `src/embeddings/models.py`
- [ ] Implement VectorDocument → Document conversion in `src/vector_store/postgres_retriever.py`
- [ ] Create PostgreSQL schema migration in `src/vector_store/schema.py`
- [ ] Write validation tests in `tests/unit/test_models.py`
- [ ] Test interface compatibility in `tests/contract/test_retriever_interface.py`
- [ ] Verify HNSW index performance in `tests/integration/test_search_workflow.py`

---

## References

- [Qwen3-Embedding-0.6B Model Card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [DocumentRetriever Interface](../../../app/core/retriever.py)
- [Research Document](./research.md)
