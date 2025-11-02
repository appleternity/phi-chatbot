# langgraph Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-29

## Active Technologies

- Python 3.11+ (001-llm-contextual-chunking)
- OpenRouter API for LLM calls
- Pydantic 2.x for data validation
- Tiktoken for token counting
- Typer for CLI

## Project Structure

```text
src/
  chunking/                 # Document chunking module (2-phase architecture)
    structure_analyzer.py   # Phase 1: Structure analysis
    chunk_extractor.py      # Phase 2: Chunk extraction
    chunking_pipeline.py    # Main orchestrator
    cli.py                  # Command-line interface
    models.py               # Data models
    llm_provider.py         # LLM API client
    cache_store.py          # Caching layer
    metadata_validator.py   # Validation utilities
    text_aligner.py         # Coverage validation
tests/
  chunking/                 # Chunking tests
    unit/                   # Unit tests
    integration/            # Integration tests
    contract/               # Contract tests
```

## Commands

### Chunking Commands

#### Full Pipeline (2-Phase Processing)

```bash
# Process a single document
python -m src.chunking.cli process --input chapter.txt --output output/

# Process a folder of documents
python -m src.chunking.cli process --input book_chapters/ --output output/

# Customize models (2-phase architecture)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model openai/gpt-4o \
  --extraction-model google/gemini-2.0-flash-exp \
  --max-tokens 1000 \
  --log-level DEBUG

# Force reprocessing (bypass cache)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --redo
```

#### Phase 1: Structure Analysis

Run structure analysis independently. Outputs structure JSON with sections and summaries.

```bash
# Analyze a single document
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --model openai/gpt-4o \
  --max-tokens 1000

# Analyze multiple documents
python -m src.chunking.cli analyze \
  --input book_chapters/ \
  --output analysis/ \
  --format jsonl

# Include token consumption statistics
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --stats

# Force reanalysis (bypass cache)
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --redo

# Output formats: json (default), jsonl, yaml
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --format yaml
```

**Use Cases**:
- Manual structure review before chunk extraction
- Cost optimization (expensive model for structure, cheap for extraction)
- A/B testing different extraction models with same structure
- Debugging Phase 1 independently

#### Phase 2: Chunk Extraction

Run chunk extraction using pre-analyzed structure. Requires structure JSON from analyze command.

```bash
# Extract chunks using analyzed structure
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --model google/gemini-2.0-flash-exp

# Skip validation (faster but risky)
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --no-validate

# Custom coverage threshold (default: 0.99 = 99%)
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --min-coverage 0.95
```

**Use Cases**:
- Human-in-the-loop: review structure before extraction
- Cost optimization: reuse structure, try different extraction models
- Debugging Phase 2 independently
- Batch extraction with single structure analysis

#### Quality Validation

Validate structure or chunks for completeness and quality.

```bash
# Validate structure JSON
python -m src.chunking.cli validate structure_output.json --type structure

# Validate chunks JSONL
python -m src.chunking.cli validate chunks_output.jsonl --type chunks

# Auto-detect type from filename
python -m src.chunking.cli validate chapter_structure.json  # Auto: structure
python -m src.chunking.cli validate chapter_chunks.jsonl   # Auto: chunks

# Validate chunks with coverage check
python -m src.chunking.cli validate \
  chunks_output.jsonl \
  --type chunks \
  --document-path chapter.txt

# Strict mode (treat warnings as errors)
python -m src.chunking.cli validate \
  structure_output.json \
  --strict
```

**Exit Codes**:
- `0`: Validation passed
- `3`: Validation failed (errors found)

**Use Cases**:
- Pre-deployment quality checks
- Debugging malformed outputs
- Coverage verification
- CI/CD pipeline integration

### Development Commands

```bash
# Run tests
pytest tests/chunking/
pytest tests/chunking/ --cov=src.chunking --cov-report=html

# Type checking
mypy src/chunking/ --ignore-missing-imports

# Linting
ruff check src/chunking/
ruff check src/chunking/ --fix

# Format code
black src/chunking/ tests/chunking/
```

## Code Style

Python 3.11+: Follow PEP 8, use type hints, Google-style docstrings
- Line length: 100 characters
- Use Pydantic models for data structures
- Fail-fast error handling with custom exceptions
- Comprehensive docstrings for all public methods

## Recent Changes

### Cache Removal - Output-Based Skip Logic (2025-11-01)

**Removed content-hash caching system and implemented simpler output-file-based skip logic**:

- **Key Change**: Replaced cache_store module with output file checking
  - Check if structure.json exists → skip Phase 1 if valid
  - Check each chunk file → skip that chunk if valid (granular skip logic)
  - `--redo` flag forces reprocessing regardless of existing files

- **Benefits**:
  - **Simplicity**: ~200 lines of cache code removed
  - **Transparency**: Output files are the source of truth (no hidden cache layer)
  - **Disk Space**: No duplicate storage (cache + output)
  - **Resumability**: Can resume interrupted extractions at chunk level
  - **Granular Control**: Delete specific chunk to regenerate just that section

- **Skip Logic Details**:
  - **Phase 1 (Structure Analysis)**: Checks `{output_dir}/{document_id}/{document_id}_structure.json`
  - **Phase 2 (Chunk Extraction)**: Checks each `{document_id}_chunk_{NNN}.json` individually
  - **Validation**: Attempts to parse files before skipping (regenerates if corrupted)
  - **--redo flag**: Bypasses all skip checks and forces full reprocessing

- **Retry Logic**: Exponential backoff for both phases
  - **Phase 1 (Structure Analysis)**: 3 retries with 2s, 4s, 8s backoff
  - **Phase 2 (Chunk Extraction)**: 3 retries with 2s, 4s, 8s backoff
  - Handles LLM API timeouts and transient failures gracefully
  - Works seamlessly with skip logic (already-extracted chunks are skipped on retry)

- **Files Modified**: 4 production files updated
  - `cli.py`: Removed FileCacheStore, updated --redo help text
  - `chunking_pipeline.py`: Removed cache_store parameter, added chunk extraction retry logic
  - `structure_analyzer.py`: Added output-based skip logic for structure files
  - `chunk_extractor.py`: Added granular per-chunk skip logic

- **Files Moved**: 1 file archived
  - `cache_store.py` → `research/cache_store.py` with deprecation notice
  - Research imports updated to reflect new location

- **Cache Commands Removed**:
  - `cache --stats`: No longer available
  - `cache --clear`: No longer needed

### V3 Experimental Architecture - Cache-Optimized Extractors (2025-10-31 - Late Evening)

**Created experimental chunk extractors optimized for LLM prompt caching**:

- **Key Innovation**: Eliminated redundant metadata generation (33-66% fewer LLM calls)
  - Metadata now derived from Phase 1 structure analysis (no LLM call needed!)
  - Single source of truth - perfect consistency between phases
  - Phase 1 already has all metadata: chapter_title, section_title, summary

- **V3A (Conservative)**: 2 LLM calls per section
  - Extract text → Generate contextual prefix
  - Metadata derived from Phase 1 structure
  - Cache efficiency: ~50-60%

- **V3B (Aggressive)**: 1 LLM call per section
  - Extract text + prefix merged in single call
  - Tagged output format for robust parsing
  - Cache efficiency: ~80-90%

- **Tag-Based Output Format**: Replaced fragile TSV with XML-style tags
  - Handles dirty text (tabs, newlines, special characters)
  - Clear field boundaries: `[TAG]content[/TAG]`
  - Robust error detection and parsing

- **ChunkMetadata Changes**:
  - `subsection_title`: Changed from `Optional[str]` to `List[str]`
  - Now captures ALL subsections, not just first one
  - Better hierarchical representation for RAG retrieval

- **Files Created**: 3 new files
  - `tag_parser.py`: XML-style tag parsing utilities
  - `chunk_extractor_v3_experimental.py`: V3A & V3B implementations
  - `V3_EXPERIMENTAL_README.md`: Comprehensive usage guide
  - `PROMPT_CACHING_TODO.md`: Implementation guide for prompt caching

- **Status**: 90% complete - Final step needed
  - Current: Document-first prompt structure (correct for caching)
  - Missing: `cache_control` breakpoints for actual caching
  - Remaining: Implement multipart message format with cache breakpoints
  - Expected savings: 80-90% cost reduction on multi-section documents

- **Reference**: See `PROMPT_CACHING_TODO.md` for complete implementation guide

### Empty Field Sentinel Fix (2025-10-31 - Evening)

**Replaced invisible tabs with explicit [EMPTY] sentinel for title-only sections**:

- **Root Cause**: Using tabs/whitespace to represent empty TSV fields is fragile
  - Invisible characters easily destroyed by `.strip()` or other text processing
  - Difficult to debug (can't see empty fields in logs)
  - Ambiguous for LLMs (unclear if "empty" means "skip column" or "output nothing")

- **The Solution**: Use explicit `[EMPTY]` sentinel value
  - **Prompt Update**: Instruct LLM to output `[EMPTY]` for empty start_words/end_words
  - **Parser Update**: Convert `[EMPTY]` to empty string when creating SectionV2 objects
  - **Example**: `Title\t1\tROOT\tSummary\t[EMPTY]\t[EMPTY]` (6 columns, last two explicitly empty)

- **Benefits**:
  - ✅ Explicit > Implicit (Python zen) - visible in logs and debugging
  - ✅ No whitespace ambiguity - can safely use `.strip()` everywhere
  - ✅ LLM-friendly - clearer instruction than "preserve invisible characters"
  - ✅ Robust - won't be destroyed by any text processing

- **Impact**: Unblocks document processing for all documents with title-only sections
  - Production errors eliminated: 4-column vs 6-column mismatch
  - Parser correctly handles empty fields with explicit sentinel

- **Files Modified**: 2 files
  - Updated: structure_analyzer_v2.py (prompt + parser with [EMPTY] conversion)
  - Updated: structure_analyzer.py (reverted unnecessary .rstrip() change for consistency)

### Title-Only Section Support (2025-10-31 - Morning)

**Enhanced SectionV2 to support title-only sections**:

- **Empty Boundary Markers**: Allow empty `start_words` and `end_words` for title-only sections
  - Title-only sections (headers with no body content) now represented naturally as empty strings
  - Eliminates forced LLM hallucination when no content exists
  - Structure analyzer V2 prompt updated to guide LLMs to output empty values appropriately

- **Chunk Extraction Skip Logic**: Automatically skip title-only sections during Phase 2
  - Sections with both `start_words=""` and `end_words=""` are skipped
  - No chunk generated for title-only sections (content is in subsections)
  - Prevents extraction errors and unnecessary LLM API calls

- **Data Model Changes**:
  - `SectionV2.start_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - `SectionV2.end_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - Default values allow omitting fields entirely in section creation

- **Test Coverage**: Added 4 unit tests for title-only sections
  - Test cases cover: normal content, empty fields, default values, mixed sections

- **Files Modified**: 3 files updated, 1 test file enhanced
  - Updated: models.py, structure_analyzer_v2.py, chunk_extractor_v2.py
  - Tests: tests/chunking/unit/test_utilities.py (added TestSectionV2 class)

### Architecture Redesign (2025-10-30)

**Major architectural changes for 001-llm-contextual-chunking**:

- **2-Phase Architecture**: Simplified from 3-phase to 2-phase pipeline
  - Phase 1: Structure Analysis (structure_analyzer.py)
  - Phase 2: Chunk Extraction (chunk_extractor.py)
  - Removed: Phase 2 (boundary_detector.py) and Phase 3 (document_segmenter.py)

- **Text Extraction Approach**: Replaced position-based processing
  - LLMs extract full text based on title + summary metadata
  - Eliminated unreliable character position output (start_char, end_char)
  - 3 LLM calls per section: extract text → metadata → contextual prefix

- **Content-Hash Caching**: Removed TTL-based expiration
  - Cache persists until document content changes
  - SHA256-based cache keys for content addressability
  - Supports `--redo` flag to force reprocessing

- **Independent Phase Execution**: New CLI commands
  - `analyze`: Run Phase 1 structure analysis independently
  - `extract`: Run Phase 2 chunk extraction with pre-analyzed structure
  - `validate`: Quality validation for structures and chunks
  - Enables human-in-the-loop workflows and cost optimization

- **Data Model Updates**:
  - Removed position fields: `Section.start_char`, `Section.end_char`, `Chunk.character_span`
  - Added `Section.summary` field (10-200 chars) for extraction guidance
  - Deleted `BoundaryType` enum and `SegmentBoundary` model
  - Renamed `BoundaryDetectionError` → `ChunkExtractionError`

- **Files Modified**: 8 files updated, 1 created, 2 deleted
  - Updated: models.py, cache_store.py, structure_analyzer.py, chunking_pipeline.py, cli.py
  - Created: chunk_extractor.py
  - Deleted: boundary_detector.py, document_segmenter.py

- 001-llm-contextual-chunking: Added Python 3.11+

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
