# Document Chunking System

LLM-based contextual document chunking for RAG pipelines.

## Overview

This module implements an intelligent document chunking system that processes book chapters and other long-form documents into semantically coherent, contextually-enriched chunks optimized for Retrieval-Augmented Generation (RAG) systems.

### Key Features

- **LLM-Driven Structure Analysis**: Identifies document hierarchy (chapters, sections, subsections) using GPT-4o
- **Semantic Boundary Detection**: Splits content at meaningful points, not arbitrary character counts
- **Contextual Enrichment**: Prepends contextual information to each chunk (Anthropic's Contextual Retrieval approach)
- **Metadata Generation**: Adds chapter title, section title, subsection title, and summary to every chunk
- **100% Text Coverage Validation**: Verifies no text is lost or duplicated during chunking
- **Prompt Caching**: Reduces API costs by caching structure analyses
- **Fail-Fast Error Handling**: Halts immediately on errors with detailed diagnostics

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cat > .env << EOF
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EOF
```

### Basic Usage

```bash
# Process a single chapter
python -m src.chunking.cli process --input chapter.txt --output output/

# Process a folder of chapters
python -m src.chunking.cli process --input book_chapters/ --output output/

# View cache statistics
python -m src.chunking.cli cache --stats

# Clear cache
python -m src.chunking.cli cache --clear
```

### Python API

```python
from pathlib import Path
from src.chunking.chunking_pipeline import ChunkingPipeline
from src.chunking.llm_provider import OpenRouterProvider
from src.chunking.cache_store import FileCacheStore
from src.chunking.models import Document

# Initialize components
llm_provider = OpenRouterProvider(api_key="your_key")
cache_store = FileCacheStore()

# Create pipeline
pipeline = ChunkingPipeline(
    llm_provider=llm_provider,
    cache_store=cache_store,
    structure_model="openai/gpt-4o",
    boundary_model="openai/gpt-4o",
    segmentation_model="google/gemini-2.0-flash-exp"
)

# Process a document
document = Document.from_file(Path("chapter.txt"))
result = pipeline.process_document(document, max_chunk_tokens=1000)

# Access results
print(f"Generated {result.total_chunks} chunks")
print(f"Text coverage: {result.text_coverage_ratio:.1%}")

# Iterate over chunks
for chunk in result.chunks:
    print(f"\nChunk ID: {chunk.chunk_id}")
    print(f"Section: {chunk.metadata.section_title}")
    print(f"Summary: {chunk.metadata.summary}")
    print(f"Token count: {chunk.token_count}")
    print(f"Text preview: {chunk.chunk_text[:100]}...")
```

## Architecture

### Three-Phase Pipeline

#### Phase 1: Structure Analysis
- **Input**: Raw document text
- **Model**: openai/gpt-4o (high-capability for reasoning)
- **Output**: Hierarchical structure with sections and boundaries
- **Caching**: Structure analysis results cached by document hash

```python
from src.chunking.structure_analyzer import StructureAnalyzer

analyzer = StructureAnalyzer(llm_client, cache_store, model="openai/gpt-4o")
structure = analyzer.analyze(document)

# Access structure
for section in structure.sections:
    print(f"{section.level} - {section.title} ({section.start_char}-{section.end_char})")
```

#### Phase 2: Boundary Detection
- **Input**: Document + structure from Phase 1
- **Model**: openai/gpt-4o (semantic analysis)
- **Output**: Ordered list of semantic boundaries
- **Logic**: Identifies SECTION_BREAK, SEMANTIC_SHIFT, and SIZE_CONSTRAINT boundaries

```python
from src.chunking.boundary_detector import BoundaryDetector

detector = BoundaryDetector(llm_client, token_counter, model="openai/gpt-4o")
boundaries = detector.detect_boundaries(document, structure, max_chunk_tokens=1000)

# Access boundaries
for boundary in boundaries:
    print(f"{boundary.boundary_type} at position {boundary.position}: {boundary.justification}")
```

#### Phase 3: Document Segmentation
- **Input**: Document + structure + boundaries
- **Model**: google/gemini-2.0-flash-exp (fast text processing)
- **Output**: Final chunks with metadata and contextual prefixes
- **Operations**: Text cleaning, metadata generation, contextual prefix creation

```python
from src.chunking.document_segmenter import DocumentSegmenter

segmenter = DocumentSegmenter(llm_client, token_counter, metadata_validator, model="google/gemini-2.0-flash-exp")
chunks = segmenter.segment(document, structure, boundaries)

# Access chunk data
for chunk in chunks:
    print(f"Chunk: {chunk.chunk_id}")
    print(f"Metadata: {chunk.metadata}")
    print(f"Contextual prefix: {chunk.contextual_prefix}")
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ChunkingPipeline                          │
│                     (Orchestrator)                           │
└───────┬────────────────────┬────────────────────┬───────────┘
        │                    │                    │
        v                    v                    v
┌───────────────┐   ┌──────────────┐   ┌─────────────────┐
│  Structure    │   │  Boundary    │   │   Document      │
│  Analyzer     │   │  Detector    │   │  Segmenter      │
│  (Phase 1)    │   │  (Phase 2)   │   │  (Phase 3)      │
└───────┬───────┘   └──────┬───────┘   └────────┬────────┘
        │                  │                     │
        v                  v                     v
┌─────────────────────────────────────────────────────────────┐
│                      Shared Services                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ LLMProvider │  │  CacheStore  │  │TokenCounter  │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### Core Models

```python
from src.chunking.models import Document, Structure, Chunk

# Document: Input to the pipeline
document = Document(
    document_id="chapter_01",
    content="Full chapter text...",
    file_hash="sha256_hash",
    source_file="/path/to/chapter.txt"
)

# Structure: Output of Phase 1
structure = Structure(
    document_id="chapter_01",
    chapter_title="Introduction to Testing",
    sections=[
        Section(title="Why Test?", level=2, start_char=0, end_char=500),
        Section(title="Types of Testing", level=2, start_char=500, end_char=1000)
    ],
    analysis_model="openai/gpt-4o"
)

# Chunk: Final output
chunk = Chunk(
    chunk_id="chapter_01_chunk_001",
    source_document="chapter_01",
    chunk_text="Contextual prefix + original text",
    original_text="Original text without prefix",
    contextual_prefix="This chunk is from Chapter 1...",
    metadata=ChunkMetadata(
        chapter_title="Introduction to Testing",
        section_title="Why Test?",
        subsection_title=None,
        summary="Explains the importance of testing"
    ),
    token_count=847,
    character_span=(0, 500)
)
```

### Metadata Structure

```python
{
    "chunk_id": "chapter_01_chunk_001",
    "source_document": "chapter_01_introduction",
    "chunk_text": "Contextual prefix + cleaned text",
    "metadata": {
        "chapter_title": "Introduction to Testing",
        "section_title": "Why Test?",
        "subsection_title": null,
        "summary": "Explains the importance of testing in software development"
    },
    "token_count": 847,
    "character_span": [0, 1234],
    "processing_metadata": {
        "phase_1_model": "openai/gpt-4o",
        "phase_2_model": "openai/gpt-4o",
        "phase_3_model": "google/gemini-2.0-flash-exp",
        "processed_at": "2025-10-29T10:30:45Z"
    }
}
```

## Configuration

### Model Selection

```bash
# Default configuration (recommended)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model openai/gpt-4o \
  --boundary-model openai/gpt-4o \
  --segmentation-model google/gemini-2.0-flash-exp

# Budget mode (faster, less accurate)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model google/gemini-2.0-flash-exp \
  --boundary-model google/gemini-2.0-flash-exp \
  --segmentation-model google/gemini-2.0-flash-exp

# Premium mode (best quality, highest cost)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model openai/gpt-4o \
  --boundary-model openai/gpt-4o \
  --segmentation-model openai/gpt-4o
```

### Chunk Size Tuning

```bash
# Smaller chunks (more granular)
python -m src.chunking.cli process --input chapter.txt --output output/ --max-tokens 500

# Default (balanced)
python -m src.chunking.cli process --input chapter.txt --output output/ --max-tokens 1000

# Larger chunks (more context)
python -m src.chunking.cli process --input chapter.txt --output output/ --max-tokens 1500
```

### Logging Levels

```bash
# Debug (verbose output with timing and decisions)
python -m src.chunking.cli process --input chapter.txt --output output/ --log-level DEBUG

# Info (default, progress messages)
python -m src.chunking.cli process --input chapter.txt --output output/ --log-level INFO

# Warning (errors and warnings only)
python -m src.chunking.cli process --input chapter.txt --output output/ --log-level WARNING
```

## Validation

### Text Coverage Validation

The system ensures 100% text coverage using character-level alignment:

```python
from src.chunking.text_aligner import TextAligner

# Verify coverage (automatically done in pipeline)
coverage_ratio, missing_segments = TextAligner.verify_coverage(
    original_text=document.content,
    chunks=chunks,
    min_coverage=0.99  # 99% minimum required
)

if coverage_ratio < 0.99:
    raise TextCoverageError(f"Coverage only {coverage_ratio:.1%}, missing segments: {missing_segments}")
```

### Metadata Validation

Every chunk must have complete metadata:

```python
from src.chunking.metadata_validator import MetadataValidator

validator = MetadataValidator()

# Validate single chunk
validator.validate_chunk(chunk)

# Validate all chunks
validator.validate_chunks(chunks)
```

## Error Handling

The system uses fail-fast error handling with specific exception types:

```python
from src.chunking.models import (
    StructureAnalysisError,    # Phase 1 errors
    BoundaryDetectionError,     # Phase 2 errors
    SegmentationError,          # Phase 3 errors
    TextCoverageError,          # Validation errors
    MetadataValidationError     # Metadata errors
)

try:
    result = pipeline.process_document(document)
except StructureAnalysisError as e:
    print(f"Structure analysis failed: {e}")
except BoundaryDetectionError as e:
    print(f"Boundary detection failed: {e}")
except SegmentationError as e:
    print(f"Segmentation failed: {e}")
except TextCoverageError as e:
    print(f"Coverage validation failed: {e}")
except MetadataValidationError as e:
    print(f"Metadata validation failed: {e}")
```

## Testing

### Run Tests

```bash
# All tests
pytest tests/chunking/

# Unit tests only
pytest tests/chunking/unit/

# Integration tests
pytest tests/chunking/integration/

# Contract tests
pytest tests/chunking/contract/

# With coverage report
pytest tests/chunking/ --cov=src.chunking --cov-report=html
```

### Mock LLM Provider

For testing without API calls:

```python
from src.chunking.llm_provider import MockLLMProvider

mock_llm = MockLLMProvider(responses={
    "openai/gpt-4o": {
        "choices": [{"message": {"content": "Mock TSV response"}}]
    }
})

pipeline = ChunkingPipeline(llm_provider=mock_llm, cache_store=cache_store)
```

## Performance

### Token Consumption

Typical token usage for a 10,000-word chapter:

| Phase | Model | Tokens | Cost (est.) |
|-------|-------|--------|-------------|
| Phase 1 | GPT-4o | ~12,000 | $0.30 |
| Phase 2 | GPT-4o | ~15,000 | $0.38 |
| Phase 3 | Gemini-2.0-flash | ~8,000 | $0.01 |
| **Total** | - | **~35,000** | **$0.69** |

With caching enabled, subsequent similar documents reduce Phase 1 costs by 50%+.

### Processing Time

Average processing times (10,000-word chapter):

- Phase 1: 2-3 seconds
- Phase 2: 1-2 seconds
- Phase 3: 4-6 seconds
- **Total**: 7-11 seconds

## Troubleshooting

### Common Issues

**Error: "Text coverage validation failed"**
- Cause: LLM skipped text segments during chunking
- Solution: Try different segmentation model or check document formatting

**Error: "Metadata validation failed"**
- Cause: LLM didn't generate required metadata
- Solution: Ensure document has clear structure or use higher-capability model

**Error: "LLMProviderError: 401 Unauthorized"**
- Cause: Invalid or missing API key
- Solution: Verify `OPENROUTER_API_KEY` in `.env` file

**Slow processing**
- Use caching for repeated structures
- Switch to faster models (gemini-2.0-flash-exp for all phases)
- Reduce `--max-tokens` to create fewer chunks

## API Reference

### ChunkingPipeline

Main orchestrator for the chunking system.

```python
pipeline = ChunkingPipeline(
    llm_provider: LLMProvider,
    cache_store: CacheStore,
    structure_model: str = "openai/gpt-4o",
    boundary_model: str = "openai/gpt-4o",
    segmentation_model: str = "google/gemini-2.0-flash-exp"
)

result = pipeline.process_document(
    document: Document,
    max_chunk_tokens: int = 1000
) -> ProcessingResult

batch_result = pipeline.process_folder(
    folder_path: Path,
    max_chunk_tokens: int = 1000
) -> BatchProcessingResult
```

### StructureAnalyzer

Phase 1: Analyze document structure.

```python
analyzer = StructureAnalyzer(
    llm_client: LLMProvider,
    cache_store: CacheStore,
    model: str = "openai/gpt-4o"
)

structure = analyzer.analyze(document: Document) -> Structure
```

### BoundaryDetector

Phase 2: Detect semantic boundaries.

```python
detector = BoundaryDetector(
    llm_client: LLMProvider,
    token_counter: TokenCounter,
    model: str = "openai/gpt-4o"
)

boundaries = detector.detect_boundaries(
    document: Document,
    structure: Structure,
    max_chunk_tokens: int = 1000
) -> List[SegmentBoundary]
```

### DocumentSegmenter

Phase 3: Segment into chunks with metadata.

```python
segmenter = DocumentSegmenter(
    llm_client: LLMProvider,
    token_counter: TokenCounter,
    metadata_validator: MetadataValidator,
    model: str = "google/gemini-2.0-flash-exp"
)

chunks = segmenter.segment(
    document: Document,
    structure: Structure,
    boundaries: List[SegmentBoundary]
) -> List[Chunk]
```

## Contributing

See the main project documentation for contribution guidelines.

## License

See the main project LICENSE file.

## Support

- **Documentation**: Full specification in `specs/001-llm-contextual-chunking/`
- **Tests**: Comprehensive test suite in `tests/chunking/`
- **Issues**: Report bugs or request features via GitHub Issues
