# Data Model: LLM-Based Contextual Document Chunking

**Feature**: 001-llm-contextual-chunking | **Date**: 2025-10-29

## Overview

This document defines all data structures used in the document chunking pipeline. All models use Pydantic for validation and type safety.

---

## Core Entities

### 1. Document

**Purpose**: Represents input document (book chapter) with metadata

**Fields**:
- `file_path`: Path - Absolute path to source document file
- `content`: str - Raw document text (UTF-8)
- `document_id`: str - Unique identifier (derived from filename)
- `file_hash`: str - SHA256 hash of content (for caching)
- `encoding`: str - Character encoding (default: "utf-8")

**Validation Rules**:
- `content` must not be empty
- `file_path` must exist and be readable
- `document_id` must be valid filename-safe string

**Relationships**:
- Source for Structure (1:1)
- Referenced by Chunk (1:N)

```python
from pydantic import BaseModel, Field, validator
from pathlib import Path
import hashlib

class Document(BaseModel):
    file_path: Path
    content: str = Field(..., min_length=1)
    document_id: str
    file_hash: str
    encoding: str = "utf-8"

    @classmethod
    def from_file(cls, file_path: Path) -> "Document":
        content = file_path.read_text(encoding="utf-8")
        document_id = file_path.stem  # filename without extension
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        return cls(
            file_path=file_path,
            content=content,
            document_id=document_id,
            file_hash=file_hash
        )

    @validator('content')
    def content_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Document content cannot be empty')
        return v
```

---

### 2. Structure

**Purpose**: Hierarchical organization of document (Phase 1 output)

**Fields**:
- `document_id`: str - Reference to source document
- `chapter_title`: str - Chapter-level title
- `chapter_number`: Optional[int] - Chapter number if available
- `sections`: List[Section] - Ordered list of sections
- `metadata`: Dict[str, Any] - Additional structural metadata
- `analysis_model`: str - LLM model used for analysis
- `analyzed_at`: datetime - Timestamp of analysis

**Validation Rules**:
- `chapter_title` must not be empty
- `sections` must contain at least one section
- Section boundaries must not overlap
- Sections must cover entire document span

**Relationships**:
- Produced from Document (1:1)
- Contains Sections (1:N)
- Used by BoundaryDetector to create SegmentBoundaries

```python
from datetime import datetime
from typing import List, Optional, Dict, Any

class Section(BaseModel):
    title: str = Field(..., min_length=1)
    level: int = Field(..., ge=1, le=3)  # 1=section, 2=subsection, 3=subsubsection
    start_char: int = Field(..., ge=0)
    end_char: int = Field(..., gt=0)
    parent_section: Optional[str] = None  # Title of parent section

    @validator('end_char')
    def end_after_start(cls, v, values):
        if 'start_char' in values and v <= values['start_char']:
            raise ValueError('end_char must be greater than start_char')
        return v

class Structure(BaseModel):
    document_id: str
    chapter_title: str = Field(..., min_length=1)
    chapter_number: Optional[int] = Field(None, ge=1)
    sections: List[Section] = Field(..., min_items=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    analysis_model: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('sections')
    def sections_non_overlapping(cls, v):
        for i in range(len(v) - 1):
            if v[i].end_char > v[i+1].start_char:
                raise ValueError(f'Sections overlap: {v[i].title} and {v[i+1].title}')
        return v
```

---

### 3. SegmentBoundary

**Purpose**: Decision point for chunk splits (Phase 2 output)

**Fields**:
- `boundary_id`: str - Unique identifier
- `position`: int - Character position in document
- `boundary_type`: BoundaryType - Reason for split (enum)
- `justification`: str - Explanation for boundary placement
- `section_context`: str - Section title at this boundary
- `estimated_chunk_size`: int - Estimated tokens before this boundary

**BoundaryType Enum**:
- `SECTION_BREAK`: Natural section boundary
- `SEMANTIC_SHIFT`: Content topic change
- `SIZE_CONSTRAINT`: Approaching 1000 token limit
- `DOCUMENT_START`: Beginning of document
- `DOCUMENT_END`: End of document

**Validation Rules**:
- `position` must be within document bounds
- `justification` must be meaningful (not placeholder)
- `estimated_chunk_size` must be > 0 (except DOCUMENT_START)

**Relationships**:
- Derived from Structure (N:1)
- Used to generate Chunks (N:1)

```python
from enum import Enum

class BoundaryType(str, Enum):
    SECTION_BREAK = "section_break"
    SEMANTIC_SHIFT = "semantic_shift"
    SIZE_CONSTRAINT = "size_constraint"
    DOCUMENT_START = "document_start"
    DOCUMENT_END = "document_end"

class SegmentBoundary(BaseModel):
    boundary_id: str
    position: int = Field(..., ge=0)
    boundary_type: BoundaryType
    justification: str = Field(..., min_length=10)
    section_context: str
    estimated_chunk_size: int = Field(..., ge=0)

    @validator('justification')
    def justification_meaningful(cls, v):
        placeholders = ['todo', 'n/a', 'none', 'tbd', '...']
        if v.strip().lower() in placeholders:
            raise ValueError('Justification cannot be placeholder')
        return v
```

---

### 4. ChunkMetadata

**Purpose**: Metadata for individual chunk (required for RAG)

**Fields**:
- `chapter_title`: str - Chapter title (required)
- `section_title`: str - Section title (required)
- `subsection_title`: Optional[str] - Subsection title if applicable
- `summary`: str - Brief content summary (10-500 chars)

**Validation Rules**:
- All required fields must be non-empty
- `summary` must be meaningful (not placeholder)
- `summary` length: 10-500 characters

```python
class ChunkMetadata(BaseModel):
    chapter_title: str = Field(..., min_length=1)
    section_title: str = Field(..., min_length=1)
    subsection_title: Optional[str] = None
    summary: str = Field(..., min_length=10, max_length=500)

    @validator('summary')
    def summary_not_placeholder(cls, v):
        placeholders = ['todo', 'n/a', 'none', 'tbd', '...', 'summary']
        if v.strip().lower() in placeholders:
            raise ValueError('Summary must be meaningful')
        return v

    @validator('chapter_title', 'section_title')
    def titles_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty or whitespace')
        return v
```

---

### 5. Chunk

**Purpose**: Final output unit for RAG ingestion (Phase 3 output)

**Fields**:
- `chunk_id`: str - Unique identifier (format: `{doc_id}_chunk_{nnn}`)
- `source_document`: str - Source document identifier
- `chunk_text`: str - Full chunk text with contextual prefix
- `original_text`: str - Original text without contextual prefix
- `contextual_prefix`: str - Prepended context (Anthropic approach)
- `metadata`: ChunkMetadata - Structured metadata
- `token_count`: int - Actual token count
- `character_span`: Tuple[int, int] - (start_char, end_char) in original document
- `processing_metadata`: ProcessingMetadata - Processing details

**Validation Rules**:
- `chunk_text` must not be empty
- `token_count` must be ≤ 1000
- `metadata` must pass ChunkMetadata validation
- `character_span` must be valid (end > start)

**Relationships**:
- Generated from Document + SegmentBoundaries (N:1:N)
- Contains ChunkMetadata (1:1)
- Part of ProcessingResult (N:1)

```python
class ProcessingMetadata(BaseModel):
    phase_1_model: str  # Structure analysis model
    phase_2_model: str  # Boundary detection model
    phase_3_model: str  # Segmentation model
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False  # Was structure cached?
    processing_time_ms: Optional[int] = None

class Chunk(BaseModel):
    chunk_id: str
    source_document: str
    chunk_text: str = Field(..., min_length=1)
    original_text: str = Field(..., min_length=1)
    contextual_prefix: str
    metadata: ChunkMetadata
    token_count: int = Field(..., ge=1, le=1000)
    character_span: Tuple[int, int]
    processing_metadata: ProcessingMetadata

    @validator('chunk_text', 'original_text')
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v

    @validator('character_span')
    def span_valid(cls, v):
        start, end = v
        if end <= start:
            raise ValueError('character_span end must be greater than start')
        return v

    @validator('chunk_id')
    def chunk_id_format(cls, v):
        if not re.match(r'^[\w-]+_chunk_\d{3,}$', v):
            raise ValueError('chunk_id must match format: {doc_id}_chunk_{nnn}')
        return v
```

---

### 6. ProcessingResult

**Purpose**: Complete output from processing a single document

**Fields**:
- `document_id`: str - Source document identifier
- `chunks`: List[Chunk] - All generated chunks
- `structure`: Structure - Document structure (for debugging)
- `text_coverage_ratio`: float - Coverage validation result (0.0-1.0)
- `total_chunks`: int - Count of chunks
- `total_tokens`: int - Sum of all chunk tokens
- `processing_report`: ProcessingReport - Execution metrics

**Validation Rules**:
- `chunks` must not be empty
- `text_coverage_ratio` must be ≥ 0.99 (99% coverage required)
- `total_chunks` must match len(chunks)

```python
class ProcessingReport(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    phase_1_tokens: int  # Tokens consumed in structure analysis
    phase_2_tokens: int  # Tokens consumed in boundary detection
    phase_3_tokens: int  # Tokens consumed in segmentation
    total_tokens_consumed: int
    cache_hits: int
    errors: List[str] = Field(default_factory=list)

class ProcessingResult(BaseModel):
    document_id: str
    chunks: List[Chunk] = Field(..., min_items=1)
    structure: Structure
    text_coverage_ratio: float = Field(..., ge=0.0, le=1.0)
    total_chunks: int
    total_tokens: int
    processing_report: ProcessingReport

    @validator('text_coverage_ratio')
    def coverage_acceptable(cls, v):
        if v < 0.99:
            raise ValueError(
                f'Text coverage {v:.2%} below required 99%. '
                'Missing content detected.'
            )
        return v

    @validator('total_chunks')
    def chunk_count_matches(cls, v, values):
        if 'chunks' in values and v != len(values['chunks']):
            raise ValueError('total_chunks must match len(chunks)')
        return v
```

---

### 7. BatchProcessingResult

**Purpose**: Result from processing multiple documents (folder)

**Fields**:
- `batch_id`: str - Unique batch identifier
- `results`: List[ProcessingResult] - Results per document
- `failed_documents`: List[str] - Document IDs that failed
- `total_documents`: int - Total documents attempted
- `successful_documents`: int - Successfully processed count
- `total_chunks`: int - Total chunks across all documents
- `batch_report`: BatchReport - Aggregated metrics

```python
class BatchReport(BaseModel):
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    total_tokens_consumed: int
    total_cache_hits: int
    average_chunks_per_document: float
    errors_by_document: Dict[str, List[str]] = Field(default_factory=dict)

class BatchProcessingResult(BaseModel):
    batch_id: str
    results: List[ProcessingResult]
    failed_documents: List[str] = Field(default_factory=list)
    total_documents: int
    successful_documents: int
    total_chunks: int
    batch_report: BatchReport

    @validator('successful_documents')
    def success_count_matches(cls, v, values):
        if 'results' in values and v != len(values['results']):
            raise ValueError('successful_documents must match len(results)')
        return v
```

---

## State Transitions

```mermaid
graph TD
    A[Document] -->|Phase 1| B[Structure]
    B -->|Phase 2| C[SegmentBoundary[]]
    C -->|Phase 3| D[Chunk[]]
    D -->|Validation| E[ProcessingResult]
    E -->|Batch| F[BatchProcessingResult]

    B -.Cache.-> G[(CacheStore)]
    G -.Retrieve.-> B

    D -->|Text Alignment| H{Coverage ≥ 99%?}
    H -->|Yes| E
    H -->|No| I[TextCoverageError]

    D -->|Metadata Validation| J{Complete & Valid?}
    J -->|Yes| E
    J -->|No| K[MetadataValidationError]
```

---

## Immutability Contract

All models are **immutable** after creation:
- Use Pydantic's `Config.frozen = True` for immutability
- State transformations create new instances
- No in-place modifications allowed

```python
class Document(BaseModel):
    # ... fields ...

    class Config:
        frozen = True  # Immutable after creation
```

---

## Summary

**Total Entities**: 10 models
- **Input**: Document
- **Phase 1**: Structure, Section
- **Phase 2**: SegmentBoundary, BoundaryType (enum)
- **Phase 3**: Chunk, ChunkMetadata, ProcessingMetadata
- **Output**: ProcessingResult, ProcessingReport, BatchProcessingResult, BatchReport

**Key Validation Points**:
1. Document content non-empty
2. Structure sections non-overlapping
3. Segment boundaries justified
4. Chunk metadata complete (100%)
5. Text coverage ≥ 99%
6. Token count ≤ 1000 per chunk

All models support:
- JSON serialization (Pydantic built-in)
- Type-safe validation (runtime checks)
- Immutability (frozen config)
- Clear error messages (validator functions)
