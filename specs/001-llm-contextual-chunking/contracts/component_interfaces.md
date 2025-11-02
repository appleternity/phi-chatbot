# Component Interfaces: Document Chunking System

**Feature**: 001-llm-contextual-chunking | **Date**: 2025-10-29

## Overview

This document defines the interfaces (contracts) for all components in the chunking pipeline. These contracts specify inputs, outputs, error conditions, and behavior guarantees.

---

## 1. StructureAnalyzer

**Purpose**: Phase 1 - Analyze document structure using LLM

**Interface**:
```python
class StructureAnalyzer:
    def __init__(self, llm_client: LLMProvider, cache_store: CacheStore):
        """
        Initialize structure analyzer.

        Args:
            llm_client: LLM provider for making API calls
            cache_store: Cache for storing/retrieving structure analyses
        """
        pass

    def analyze(self, document: Document) -> Structure:
        """
        Analyze document structure.

        Args:
            document: Input document to analyze

        Returns:
            Structure object with hierarchical organization

        Raises:
            StructureAnalysisError: If LLM fails or returns invalid structure
            ValidationError: If document is invalid

        Behavior:
            1. Check cache for existing structure (by file_hash)
            2. If cache miss, format prompt with TSV example (see prompt_templates.md)
            3. Send document to LLM for analysis
            4. Parse TSV response (see prompt_templates.md for format)
            5. Validate structure (non-overlapping sections, full coverage)
            6. Cache result before returning
            7. Fail fast on any error (no retries)

        TSV Response Format:
            title	level	start_char	end_char	parent_title
            (5 columns, tab-separated, see prompt_templates.md)

        Performance:
            - Cache hit: <10ms
            - Cache miss: 2-10s (LLM API latency)
        """
        pass
```

**Contract Tests**:
- Input: Valid document → Output: Valid structure with non-overlapping sections
- Input: Invalid document (empty) → Raises: ValidationError
- Input: Document with LLM failure → Raises: StructureAnalysisError
- Input: Document with malformed TSV response (wrong column count) → Raises: StructureAnalysisError
- Input: Document with malformed TSV response (invalid integers) → Raises: StructureAnalysisError
- Caching: Same document twice → Second call returns cached result (cache_hit=True)

**Prompt Templates**: See `contracts/prompt_templates.md` for TSV format and examples

---

## 2. BoundaryDetector

**Purpose**: Phase 2 - Determine semantic chunk boundaries

**Interface**:
```python
class BoundaryDetector:
    def __init__(self, llm_client: LLMProvider, token_counter: TokenCounter):
        """
        Initialize boundary detector.

        Args:
            llm_client: LLM provider for semantic analysis
            token_counter: Token counting utility
        """
        pass

    def detect_boundaries(
        self,
        document: Document,
        structure: Structure,
        max_chunk_tokens: int = 1000
    ) -> List[SegmentBoundary]:
        """
        Determine optimal chunk boundaries.

        Args:
            document: Source document
            structure: Analyzed structure from Phase 1
            max_chunk_tokens: Maximum tokens per chunk (default: 1000)

        Returns:
            Ordered list of segment boundaries (includes DOCUMENT_START and DOCUMENT_END)

        Raises:
            BoundaryDetectionError: If LLM fails or boundaries invalid
            ValidationError: If inputs invalid

        Behavior:
            1. Always create DOCUMENT_START boundary at position 0
            2. For each section in structure, evaluate if it exceeds max_chunk_tokens
            3. If section fits within limit, create SECTION_BREAK boundary
            4. If section exceeds limit, format prompt with TSV example (see prompt_templates.md)
            5. Use LLM to identify SEMANTIC_SHIFT points (parse TSV response)
            6. Create SIZE_CONSTRAINT boundaries if semantic shifts still too large
            7. Always create DOCUMENT_END boundary at document length
            8. Validate boundaries are ordered and non-overlapping
            9. Fail fast on any error

        TSV Response Format:
            position	boundary_type	justification
            (3 columns, tab-separated, see prompt_templates.md)

        Performance:
            - Simple structure (all sections < 1000 tokens): 100-500ms
            - Complex structure (needs semantic analysis): 2-10s per oversized section
        """
        pass
```

**Contract Tests**:
- Input: Document + Structure (all sections < 1000 tokens) → Output: Boundaries at section breaks only
- Input: Document + Structure (one section > 1000 tokens) → Output: Boundaries with SEMANTIC_SHIFT splits
- Input: Document with missing structure → Raises: ValidationError
- Input: Malformed TSV response (wrong column count) → Raises: BoundaryDetectionError
- Boundary ordering: All boundaries must be in ascending position order
- Boundary completeness: First boundary is DOCUMENT_START (pos=0), last is DOCUMENT_END (pos=len(document))

**Prompt Templates**: See `contracts/prompt_templates.md` for TSV format and examples

---

## 3. DocumentSegmenter

**Purpose**: Phase 3 - Segment document and clean text

**Interface**:
```python
class DocumentSegmenter:
    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator
    ):
        """
        Initialize document segmenter.

        Args:
            llm_client: LLM provider for text cleaning and summarization
            token_counter: Token counting utility
            metadata_validator: Validator for chunk metadata
        """
        pass

    def segment(
        self,
        document: Document,
        structure: Structure,
        boundaries: List[SegmentBoundary]
    ) -> List[Chunk]:
        """
        Segment document into chunks with metadata.

        Args:
            document: Source document
            structure: Document structure from Phase 1
            boundaries: Segment boundaries from Phase 2

        Returns:
            List of chunks with contextual prefix and metadata

        Raises:
            SegmentationError: If segmentation or metadata generation fails
            MetadataValidationError: If any chunk has invalid metadata
            ValidationError: If inputs invalid

        Behavior:
            1. For each pair of boundaries (start, end), extract text segment
            2. Identify section context from structure
            3. Use LLM to:
               - Generate metadata via TSV format (see prompt_templates.md)
               - Generate contextual prefix as plain text (see prompt_templates.md)
               - Clean text (normalize whitespace, fix formatting)
            4. Parse TSV metadata response (4 columns)
            5. Validate metadata completeness
            6. Prepend contextual prefix to cleaned text
            7. Count tokens in chunk
            8. Create Chunk object
            9. Validate token count ≤ 1000
            10. Fail fast on any error

        TSV Response Format (Metadata):
            chapter_title	section_title	subsection_title	summary
            (4 columns, tab-separated, see prompt_templates.md)

        Plain Text Format (Contextual Prefix):
            Single sentence, 20-50 words, starts with "This chunk is from..."

        Performance:
            - Per chunk: 200-1000ms (depends on LLM latency)
            - Batch processing: May parallelize chunk generation
        """
        pass
```

**Contract Tests**:
- Input: Document + Structure + Boundaries → Output: Chunks with 100% metadata completeness
- Input: Boundaries producing chunk > 1000 tokens → Raises: ValidationError
- Input: Malformed TSV metadata (wrong column count) → Raises: SegmentationError
- Input: Malformed contextual prefix (too short) → Raises: SegmentationError
- Metadata validation: All chunks must have non-empty chapter_title, section_title, summary
- Contextual prefix: Each chunk must have contextual prefix prepended

**Prompt Templates**: See `contracts/prompt_templates.md` for TSV format and examples

---

## 4. TextAligner

**Purpose**: Verify 100% text coverage (no loss or duplication)

**Interface**:
```python
class TextAligner:
    def verify_coverage(
        self,
        original_document: Document,
        chunks: List[Chunk]
    ) -> Tuple[float, List[str]]:
        """
        Verify that chunks cover all original document text.

        Args:
            original_document: Source document
            chunks: Generated chunks

        Returns:
            (coverage_ratio, missing_segments)
            - coverage_ratio: 0.0-1.0 (1.0 = perfect coverage)
            - missing_segments: List of text segments not in any chunk

        Raises:
            TextCoverageError: If coverage_ratio < 0.99
            ValidationError: If inputs invalid

        Behavior:
            1. Reconstruct document from chunks (using original_text, not chunk_text)
            2. Use difflib.SequenceMatcher to compare original vs reconstructed
            3. Calculate coverage ratio (1.0 = perfect match)
            4. Identify missing segments (text in original not in reconstruction)
            5. If coverage_ratio < 0.99, raise TextCoverageError with details
            6. Return results

        Performance:
            - Typical 5000-word document: <100ms
        """
        pass
```

**Contract Tests**:
- Input: Document + Chunks (100% coverage) → Output: (1.0, [])
- Input: Document + Chunks (missing text) → Raises: TextCoverageError with missing segments
- Input: Document + Chunks (duplicated text) → Coverage ratio < 1.0, details in error

---

## 5. ChunkingPipeline

**Purpose**: Main orchestrator for end-to-end chunking

**Interface**:
```python
class ChunkingPipeline:
    def __init__(
        self,
        structure_analyzer: StructureAnalyzer,
        boundary_detector: BoundaryDetector,
        document_segmenter: DocumentSegmenter,
        text_aligner: TextAligner,
        structure_model: str = "openai/gpt-4o",
        boundary_model: str = "openai/gpt-4o",
        segmentation_model: str = "google/gemini-2.0-flash-exp"
    ):
        """
        Initialize chunking pipeline.

        Args:
            structure_analyzer: Phase 1 component
            boundary_detector: Phase 2 component
            document_segmenter: Phase 3 component
            text_aligner: Validation component
            structure_model: LLM model for Phase 1 (default: openai/gpt-4o)
            boundary_model: LLM model for Phase 2 (default: openai/gpt-4o)
            segmentation_model: LLM model for Phase 3 (default: google/gemini-2.0-flash-exp)
        """
        pass

    def process_document(self, document: Document) -> ProcessingResult:
        """
        Process single document through full pipeline.

        Args:
            document: Input document

        Returns:
            ProcessingResult with chunks and metrics

        Raises:
            ChunkingError: Any phase failure (fail-fast)
            TextCoverageError: Coverage validation failure
            MetadataValidationError: Metadata validation failure

        Behavior:
            1. Phase 1: Analyze structure
            2. Phase 2: Detect boundaries
            3. Phase 3: Segment document
            4. Validation: Verify text coverage
            5. Validation: Verify metadata completeness
            6. Create ProcessingResult with metrics
            7. Fail fast on any error (no partial results)

        Performance:
            - Typical 5000-word chapter: 5-30s (depends on LLM latency and caching)
        """
        pass

    def process_folder(self, folder_path: Path) -> BatchProcessingResult:
        """
        Process all documents in folder.

        Args:
            folder_path: Path to folder containing documents

        Returns:
            BatchProcessingResult with all document results

        Raises:
            ChunkingError: If any document fails (fail-fast on first error)
            ValidationError: If folder invalid or empty

        Behavior:
            1. Discover all .txt and .md files in folder
            2. For each file, call process_document()
            3. If any document fails, halt immediately with error
            4. Aggregate successful results into BatchProcessingResult
            5. Write consolidated JSONL output

        Performance:
            - Sequential processing (no parallelization in MVP)
            - Per document: 5-30s
        """
        pass
```

**Contract Tests**:
- Input: Valid document → Output: ProcessingResult with 100% coverage and metadata
- Input: Folder with 5 documents → Output: BatchProcessingResult with 5 results
- Input: Folder with 1 failing document → Raises: ChunkingError, halts processing
- Caching: Second run on same document → Uses cached structure, reduced tokens

---

## 6. LLMProvider (Abstract Interface)

**Purpose**: Abstraction for LLM API calls (testability)

**Interface**:
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    @abstractmethod
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make chat completion API call.

        Args:
            model: Model identifier (e.g., "openai/gpt-4o")
            messages: List of message dicts with "role" and "content"
            response_format: Optional structured output format
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            API response dict with "choices" containing completion

        Raises:
            LLMProviderError: If API call fails
        """
        pass

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: API base URL (default: OpenRouter production)
        """
        pass

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Implementation using requests library"""
        pass
```

**Contract Tests (OpenRouterProvider)**:
- Input: Valid request → Output: Successful API response
- Input: Invalid API key → Raises: LLMProviderError with auth error
- Input: Invalid model → Raises: LLMProviderError with model not found
- Input: Network error → Raises: LLMProviderError with connection error
- Input: Structured output with response_format → Output: JSON-formatted response

**Mock Implementation for Tests**:
```python
class MockLLMProvider(LLMProvider):
    def __init__(self, responses: Dict[str, Any]):
        """
        Mock provider for testing.

        Args:
            responses: Pre-configured responses keyed by model
        """
        self.responses = responses
        self.call_history = []

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        self.call_history.append({"model": model, "messages": messages})
        return self.responses.get(model, self.responses["default"])
```

---

## 7. CacheStore (Abstract Interface)

**Purpose**: Abstraction for caching structure analyses

**Interface**:
```python
from abc import ABC, abstractmethod
from typing import Optional

class CacheStore(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data.

        Args:
            key: Cache key (typically file hash)

        Returns:
            Cached data or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key
            value: Data to cache (must be JSON-serializable)
        """
        pass

class FileCacheStore(CacheStore):
    def __init__(self, cache_dir: Path = Path(".cache")):
        """
        File-based cache implementation.

        Args:
            cache_dir: Directory for cache files
        """
        pass

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Load from {cache_dir}/structures/{key}.json"""
        pass

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Save to {cache_dir}/structures/{key}.json"""
        pass
```

**Contract Tests (FileCacheStore)**:
- Set then get same key → Returns same value
- Get non-existent key → Returns None
- Set with invalid JSON → Raises: ValueError
- Cache directory created automatically if not exists

---

## 8. TokenCounter (Utility)

**Purpose**: Count tokens in text for chunk size enforcement

**Interface**:
```python
class TokenCounter:
    def count_tokens(self, text: str, model: str) -> int:
        """
        Count tokens in text for given model.

        Args:
            text: Text to count tokens for
            model: Model identifier (determines tokenizer)

        Returns:
            Token count

        Behavior:
            - If model contains "openai" or "gpt": Use tiktoken
            - Otherwise: Use character-based estimate (1 token ≈ 4 chars)

        Performance:
            - <1ms for typical chunk text
        """
        pass
```

**Contract Tests**:
- Input: "Hello world", "openai/gpt-4o" → Output: 2 (tiktoken)
- Input: "Hello world", "google/gemini" → Output: 3 (11 chars / 4)
- Input: Empty string → Output: 0

---

## 9. CLI Interface (Typer-based)

**Purpose**: User-facing command-line interface for document processing

**Interface**:
```python
import typer
from typing import Annotated
from pathlib import Path
from enum import Enum

app = typer.Typer(
    name="chunking",
    help="LLM-based contextual document chunking for RAG pipelines"
)

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

@app.command(name="process")
def process_documents(
    input_path: Annotated[Path, typer.Option(
        "--input", "-i",
        help="Path to document file or folder",
        exists=True,
        readable=True
    )],
    output_dir: Annotated[Path, typer.Option(
        "--output", "-o",
        help="Output directory for JSONL files"
    )],
    structure_model: Annotated[str, typer.Option(
        "--structure-model",
        help="LLM model for Phase 1 (structure analysis)"
    )] = "openai/gpt-4o",
    boundary_model: Annotated[str, typer.Option(
        "--boundary-model",
        help="LLM model for Phase 2 (boundary detection)"
    )] = "openai/gpt-4o",
    segmentation_model: Annotated[str, typer.Option(
        "--segmentation-model",
        help="LLM model for Phase 3 (segmentation)"
    )] = "google/gemini-2.0-flash-exp",
    max_tokens: Annotated[int, typer.Option(
        "--max-tokens",
        help="Maximum tokens per chunk",
        min=100,
        max=2000
    )] = 1000,
    log_level: Annotated[LogLevel, typer.Option(
        "--log-level",
        help="Logging level"
    )] = LogLevel.INFO
):
    """
    Process documents into contextually-enriched chunks.

    Automatically detects if input is a single file or folder.
    Processes all .txt and .md files in folder if directory provided.

    Raises:
        typer.Exit: On processing errors (fail-fast)
    """
    pass

@app.command(name="cache")
def manage_cache(
    stats: Annotated[bool, typer.Option(
        "--stats",
        help="Display cache statistics"
    )] = False,
    clear: Annotated[bool, typer.Option(
        "--clear",
        help="Clear all cached data"
    )] = False
):
    """
    Manage local cache (if file-based caching enabled).
    """
    pass

if __name__ == "__main__":
    app()
```

**Contract Tests (CLI)**:
- Input: Valid file path + output dir → Processes single document successfully
- Input: Valid folder path → Processes all documents in folder
- Input: Non-existent path → Raises: typer validation error
- Input: Invalid model name → Raises: LLMProviderError with clear message
- Input: max_tokens out of range → Raises: typer validation error
- CLI help: `--help` flag → Displays comprehensive usage documentation

**User Experience Requirements**:
- All options must have clear `--help` descriptions
- Type validation happens before processing starts
- Progress indicators for batch processing
- Colorized output for errors and success messages (using rich/typer features)
- Exit codes: 0 (success), 1 (processing error), 2 (validation error)

---

## 10. MetadataValidator (Utility)

**Purpose**: Validate chunk metadata completeness

**Interface**:
```python
class MetadataValidator:
    def validate(self, metadata: ChunkMetadata) -> None:
        """
        Validate metadata completeness.

        Args:
            metadata: Chunk metadata to validate

        Raises:
            MetadataValidationError: If metadata invalid

        Validation Rules:
            - chapter_title: Non-empty string
            - section_title: Non-empty string
            - summary: 10-500 chars, not placeholder
        """
        pass
```

**Contract Tests**:
- Input: Valid metadata → No exception
- Input: Empty chapter_title → Raises: MetadataValidationError
- Input: Summary = "TODO" → Raises: MetadataValidationError

---

## Error Hierarchy

```python
class ChunkingError(Exception):
    """Base exception for all chunking errors"""
    pass

class StructureAnalysisError(ChunkingError):
    """Phase 1 failure"""
    pass

class BoundaryDetectionError(ChunkingError):
    """Phase 2 failure"""
    pass

class SegmentationError(ChunkingError):
    """Phase 3 failure"""
    pass

class TextCoverageError(ChunkingError):
    """Text alignment validation failure"""
    def __init__(self, coverage_ratio: float, missing_segments: List[str]):
        self.coverage_ratio = coverage_ratio
        self.missing_segments = missing_segments
        super().__init__(
            f"Coverage {coverage_ratio:.2%} < 99%. "
            f"Missing {len(missing_segments)} segments."
        )

class MetadataValidationError(ChunkingError):
    """Metadata completeness validation failure"""
    pass

class LLMProviderError(ChunkingError):
    """LLM API call failure"""
    pass
```

---

## Summary

**Total Interfaces**: 10 components
- **Pipeline**: StructureAnalyzer, BoundaryDetector, DocumentSegmenter
- **Validation**: TextAligner, MetadataValidator
- **Orchestration**: ChunkingPipeline
- **Abstractions**: LLMProvider, CacheStore
- **Utilities**: TokenCounter
- **User Interface**: CLI (Typer-based)

**Key Contracts**:
1. **Fail-Fast**: All components raise exceptions immediately on error
2. **Immutable Inputs**: No component modifies input objects
3. **Type Safety**: All inputs/outputs use Pydantic models
4. **Testability**: Abstract interfaces for LLM and cache (mockable)
5. **Validation**: 100% text coverage, 100% metadata completeness enforced
6. **User Control**: Per-phase model selection via CLI options
7. **TSV Format**: All structured LLM outputs use TSV (not JSON) for reliability

**LLM Response Formats**:
- **Structure Analysis**: TSV with 5 columns (title, level, start_char, end_char, parent_title)
- **Boundary Detection**: TSV with 3 columns (position, boundary_type, justification)
- **Metadata Generation**: TSV with 4 columns (chapter_title, section_title, subsection_title, summary)
- **Contextual Prefix**: Plain text (single sentence)

**Prompt Templates**: See `contracts/prompt_templates.md` for all prompts with TSV format examples

**CLI Features**:
- Typer framework with `typer.Option` and `Annotated` (no `typer.Argument`)
- Per-phase model selection (`--structure-model`, `--boundary-model`, `--segmentation-model`)
- Type validation and automatic help generation
- Single command for both file and folder processing (auto-detection)

All interfaces ready for TDD implementation.
