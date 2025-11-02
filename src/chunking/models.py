"""
Pydantic models for document chunking system.

This module defines all data structures used in the chunking pipeline with
strict validation and type safety.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, ValidationInfo


# ============================================================================
# Exceptions
# ============================================================================


class ChunkingError(Exception):
    """Base exception for chunking errors"""
    pass


class StructureAnalysisError(ChunkingError):
    """Phase 1 structure identification failed"""
    pass


class ChunkExtractionError(ChunkingError):
    """Phase 2 chunk extraction failed"""
    pass


class TextCoverageError(ChunkingError):
    """Text alignment verification failed"""

    def __init__(self, coverage_ratio: float, missing_segments: List[str]):
        self.coverage_ratio = coverage_ratio
        self.missing_segments = missing_segments
        super().__init__(
            f"Text coverage validation failed: {coverage_ratio:.2%} coverage. "
            f"Missing {len(missing_segments)} segments."
        )


class MetadataValidationError(ChunkingError):
    """Metadata completeness validation failed"""
    pass


class LLMProviderError(ChunkingError):
    """LLM API call failed"""
    pass


# ============================================================================
# Core Entities
# ============================================================================


class Document(BaseModel):
    """Input document with metadata"""

    file_path: Path
    content: str = Field(..., min_length=1)
    document_id: str
    file_hash: str
    encoding: str = "utf-8"

    class Config:
        frozen = True  # Immutable

    @classmethod
    def from_file(cls, file_path: Path) -> "Document":
        """Create Document from file path"""
        content = file_path.read_text(encoding="utf-8")
        document_id = file_path.stem  # filename without extension
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        return cls(
            file_path=file_path,
            content=content,
            document_id=document_id,
            file_hash=file_hash
        )

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Document content cannot be empty')
        return v


class Section(BaseModel):
    """Section within document structure with word-based boundary markers.

    Includes start_words and end_words fields that provide fuzzy matching hints
    for chunk extraction. These are NOT exact quotes but distinctive word sequences
    that help locate section boundaries.

    For title-only sections (e.g., headers with no body content), start_words
    and end_words should be empty strings.
    """

    title: str = Field(..., min_length=1)
    level: int = Field(..., ge=1, le=5)  # 1=section, 2=subsection, 3=subsubsection # be flexible
    parent_section: Optional[str] = None  # Title of parent section
    summary: str = Field(..., min_length=1, max_length=3000)

    # New fields for boundary detection (empty for title-only sections)
    start_words: str = Field(default="", max_length=1000)
    end_words: str = Field(default="", max_length=1000)
    is_table: bool = False  # True if this segment is a table

    class Config:
        frozen = True

    # @field_validator('summary')
    # @classmethod
    # def summary_meaningful(cls, v):
    #     """Ensure summary is not a placeholder"""
    #     placeholders = ['todo', 'n/a', 'none', 'tbd', '...', 'summary']
    #     if v.strip().lower() in placeholders:
    #         raise ValueError('Summary must be meaningful')
    #     return v

    # @field_validator('start_words', 'end_words')
    # @classmethod
    # def words_valid_format(cls, v, info: ValidationInfo):
    #     """Relaxed validation: 1-30 words, allow fuzzy matching variations

    #     This validator ensures basic quality without being too strict, since
    #     LLMs may paraphrase or adjust formatting slightly. We focus on catching
    #     obvious errors rather than enforcing exact matches.
    #     """
    #     v = v.strip()

    #     # Get field name from info
    #     field_name = info.field_name

    #     # Basic non-empty check
    #     if not v:
    #         raise ValueError(f'{field_name} cannot be empty')

    #     # Word count check (relaxed range: 1-30 words)
    #     word_count = len(v.split())
    #     if word_count < 1:
    #         raise ValueError(
    #             f'{field_name} must contain at least 1 word, got {word_count}. '
    #             'Provide enough context for fuzzy matching.'
    #         )
    #     if word_count > 30:
    #         raise ValueError(
    #             f'{field_name} should contain at most 30 words, got {word_count}. '
    #             'Keep it concise and distinctive.'
    #         )

    #     # Avoid generic phrases that appear everywhere
    #     generic_starts = ['this section', 'the section', 'this chapter', 'the chapter',
    #                      'in this', 'as mentioned', 'as we']
    #     if any(v.lower().startswith(phrase) for phrase in generic_starts):
    #         raise ValueError(
    #             f'{field_name} should not start with generic phrases like '
    #             f'"{v[:20]}...". Use distinctive content words.'
    #         )

    #     # No strict validation for exact quotes, punctuation, or capitalization
    #     # since fuzzy matching will handle these variations
    #     return v

    # @field_validator('start_words')
    # @classmethod
    # def start_words_not_title(cls, v, info: ValidationInfo):
    #     """Ensure start_words doesn't just repeat the section title"""
    #     if 'title' in info.data:
    #         title_lower = info.data['title'].lower().strip()
    #         words_lower = v.lower().strip()

    #         # Check if start_words begins with the title
    #         if words_lower.startswith(title_lower) or title_lower in words_lower[:50]:
    #             raise ValueError(
    #                 'start_words should contain section content, not the title. '
    #                 f'Got words starting with title: "{v[:30]}..."'
    #             )
    #     return v


class Structure(BaseModel):
    """Hierarchical organization of document (Phase 1 output)"""

    document_id: str
    chapter_title: str = Field(..., min_length=1)
    chapter_number: Optional[int] = Field(None, ge=1)
    sections: List[Section] = Field(..., min_items=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    analysis_model: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True

    @field_validator('sections')
    @classmethod
    def sections_valid_hierarchy(cls, v):
        """Ensure sections form a valid hierarchy with valid parent references"""
        section_titles = {section.title for section in v}
        for section in v:
            if section.parent_section and section.parent_section not in section_titles and section.parent_section != "ROOT":
                raise ValueError(f'Section "{section.title}" references non-existent parent "{section.parent_section}"')
        return v


class ChunkMetadata(BaseModel):
    """Metadata for individual chunk (required for RAG)"""

    chapter_title: str = Field(..., min_length=1)
    section_title: str = Field(..., min_length=1)
    subsection_title: List[str] = Field(default_factory=list)
    summary: str = Field(..., min_length=10, max_length=500)

    class Config:
        frozen = True

    @field_validator('summary')
    @classmethod
    def summary_not_placeholder(cls, v):
        placeholders = ['todo', 'n/a', 'none', 'tbd', '...', 'summary']
        if v.strip().lower() in placeholders:
            raise ValueError('Summary must be meaningful')
        return v

    @field_validator('chapter_title', 'section_title')
    @classmethod
    def titles_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty or whitespace')
        return v


class ProcessingMetadata(BaseModel):
    """Processing details for chunk"""

    phase_1_model: str  # Structure analysis model
    phase_2_model: str  # Chunk extraction model
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False  # Was structure cached?
    processing_time_ms: Optional[int] = None

    class Config:
        frozen = True


class Chunk(BaseModel):
    """Final output unit for RAG ingestion (Phase 2 output)"""

    chunk_id: str
    source_document: str
    chunk_text: str = Field(..., min_length=1)
    original_text: str = Field(..., min_length=1)
    contextual_prefix: str
    metadata: ChunkMetadata
    token_count: int = Field(..., ge=1)  # No upper limit - allow any token count for analysis
    processing_metadata: ProcessingMetadata

    class Config:
        frozen = True

    @field_validator('chunk_text', 'original_text')
    @classmethod
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v

    @field_validator('chunk_id')
    @classmethod
    def chunk_id_format(cls, v):
        if not re.match(r'^.+_chunk_\d{3,}$', v):
            raise ValueError('chunk_id must match format: {doc_id}_chunk_{nnn}')
        return v


class ProcessingReport(BaseModel):
    """Execution metrics for single document processing"""

    start_time: datetime
    end_time: datetime
    duration_seconds: float
    phase_1_tokens: int  # Tokens consumed in structure analysis
    phase_2_tokens: int  # Tokens consumed in chunk extraction
    total_tokens_consumed: int
    cache_hits: int
    errors: List[str] = Field(default_factory=list)

    class Config:
        frozen = True


class ProcessingResult(BaseModel):
    """Complete output from processing a single document"""

    document_id: str
    chunks: List[Chunk] = Field(..., min_items=1)
    structure: Structure
    text_coverage_ratio: float = Field(..., ge=0.0, le=1.0)
    total_chunks: int
    total_tokens: int
    processing_report: ProcessingReport

    class Config:
        frozen = True

    @field_validator('total_chunks')
    @classmethod
    def chunk_count_matches(cls, v, info: ValidationInfo):
        if 'chunks' in info.data and v != len(info.data['chunks']):
            raise ValueError('total_chunks must match len(chunks)')
        return v


class BatchReport(BaseModel):
    """Aggregated metrics for batch processing"""

    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    total_tokens_consumed: int
    total_cache_hits: int
    average_chunks_per_document: float
    errors_by_document: Dict[str, List[str]] = Field(default_factory=dict)

    class Config:
        frozen = True

    def cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate as a percentage.

        Returns:
            Cache hit rate (0.0 to 1.0)
        """
        total_documents = self.total_cache_hits + sum(
            1 for errors in self.errors_by_document.values() if not errors
        )
        if total_documents == 0:
            return 0.0
        return self.total_cache_hits / total_documents

    def token_savings_percentage(self, avg_tokens_per_uncached: int = 5000) -> float:
        """
        Calculate estimated token savings from caching.

        Args:
            avg_tokens_per_uncached: Average tokens for uncached analysis (default: 5000)

        Returns:
            Token savings percentage (0.0 to 1.0)
        """
        if self.total_cache_hits == 0:
            return 0.0

        # Estimate tokens that would have been consumed without caching
        tokens_without_cache = self.total_tokens_consumed + (
            self.total_cache_hits * avg_tokens_per_uncached
        )

        if tokens_without_cache == 0:
            return 0.0

        tokens_saved = self.total_cache_hits * avg_tokens_per_uncached
        return tokens_saved / tokens_without_cache


class BatchProcessingResult(BaseModel):
    """Result from processing multiple documents (folder)"""

    batch_id: str
    results: List[ProcessingResult]
    failed_documents: List[str] = Field(default_factory=list)
    total_documents: int
    successful_documents: int
    total_chunks: int
    batch_report: BatchReport

    class Config:
        frozen = True

    @field_validator('successful_documents')
    @classmethod
    def success_count_matches(cls, v, info: ValidationInfo):
        if 'results' in info.data and v != len(info.data['results']):
            raise ValueError('successful_documents must match len(results)')
        return v


# ============================================================================
# Token Counter Utility
# ============================================================================


class TokenCounter:
    """Utility for counting tokens in text"""

    def __init__(self):
        self._tiktoken_cache = {}

    def count_tokens(self, text: str, model: str) -> int:
        """
        Count tokens in text for given model.

        Args:
            text: Text to count tokens for
            model: Model name (e.g., "openai/gpt-4o")

        Returns:
            Token count
        """
        # Try tiktoken for OpenAI models
        if "openai" in model.lower() or "gpt" in model.lower():
            try:
                import tiktoken

                # Cache encoding for performance
                if model not in self._tiktoken_cache:
                    # Extract base model name (e.g., "gpt-4o" from "openai/gpt-4o")
                    base_model = model.split("/")[-1] if "/" in model else model

                    try:
                        encoding = tiktoken.encoding_for_model(base_model)
                    except KeyError:
                        # Fallback to cl100k_base for unknown models
                        encoding = tiktoken.get_encoding("cl100k_base")

                    self._tiktoken_cache[model] = encoding

                encoding = self._tiktoken_cache[model]
                return len(encoding.encode(text))

            except ImportError:
                # tiktoken not available, fall back to character-based
                pass

        # Conservative fallback: 1 token ≈ 4 characters
        return len(text) // 4
