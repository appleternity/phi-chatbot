# langgraph Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-29

## Active Technologies
- Python 3.11+ + transformers, torch (MPS support), psycopg2/asyncpg, pgvector, sentence-transformers, LangGraph, FastAPI (002-semantic-search)
- PostgreSQL 15+ with pgvector extension (002-semantic-search)
- Python 3.11+ + FastAPI 0.115+, LangGraph 0.6.0, LangChain-Core 0.3+, uvicorn 0.32+ with httpx 0.27+ for async streaming (003-sse-streaming)
- PostgreSQL 15+ with pgvector (existing - no changes needed) (003-sse-streaming)

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

  embeddings/               # Semantic search indexing (002-semantic-search)
    models.py               # ChunkMetadata, VectorDocument
    encoder.py              # Qwen3EmbeddingEncoder (MPS support)
    indexer.py              # Batch indexing pipeline
    cli.py                  # CLI commands: index, validate, version

app/
  core/
    postgres_retriever.py   # PostgreSQL + pgvector retriever
    qwen3_reranker.py       # Qwen3-Reranker-0.6B for reranking
  db/
    schema.py               # Database schema and migrations
    connection.py           # Connection pooling with asyncpg

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

### Semantic Search Commands

#### Database Setup

**Start PostgreSQL with pgvector extension**:

```bash
# Start PostgreSQL Docker container
docker-compose up -d

# Verify container is healthy
docker ps
# Should show: langgraph-postgres-vector (healthy)

# View logs
docker-compose logs -f postgres-vector

# Stop container
docker-compose down

# Stop and remove volumes (destructive)
docker-compose down -v
```

**Run database migration**:

```bash
# Create vector_chunks table and indexes
python -m app.db.schema \
  --host localhost \
  --port 5432 \
  --database medical_knowledge \
  --user postgres \
  --password postgres

# Or use environment variables from .env
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/medical_knowledge"
python -m app.db.schema
```

**Verify database setup**:

```bash
# Connect to PostgreSQL
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Check vector_chunks table
\d vector_chunks

# Check indexes
\di
```

#### Indexing Commands

**Index documents (batch processing)**:

```bash
# Index all chunks from data directory (uses defaults)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --verbose

# Index with custom parameters
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --model-name Qwen/Qwen3-Embedding-0.6B \
  --device mps \
  --batch-size 32 \
  --max-length 1024

# Skip already indexed chunks (default behavior)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --skip-existing

# Disable embedding normalization
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --no-normalize
```

**Check indexing version**:

```bash
python -m src.embeddings.cli version
```

#### Search Testing

**Test semantic search in Python**:

```python
import asyncio
from app.core.postgres_retriever import PostgreSQLRetriever
from app.db.connection import get_pool, close_pool

async def test_search():
    pool = await get_pool()
    retriever = PostgreSQLRetriever(pool)

    # Search with reranking (default)
    results = await retriever.search("aripiprazole mechanism of action", top_k=5)

    for i, doc in enumerate(results, 1):
        print(f"\n{i}. {doc.metadata['chunk_id']}")
        print(f"   Score: {doc.metadata['rerank_score']:.4f}")
        print(f"   Content: {doc.content[:200]}...")

    await close_pool()

asyncio.run(test_search())
```

**Smoke test (comprehensive pipeline validation)**:

```bash
# Run all tests: parse JSON, generate embeddings, database insertion
python test_indexing.py

# Tests include:
# 1. Parse chunk file (no database required)
# 2. Generate embeddings with Qwen3-Embedding-0.6B
# 3. Insert into PostgreSQL with duplicate handling
```

**Expected performance**:
- Indexing: ~16 chunks/batch on MPS (M1/M2/M3)
- Search: <100ms pgvector similarity search
- Reranking: <2s for 20 candidates (Qwen3-Reranker-0.6B)
- Total search latency: <2.1s for top-5 results

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
- 003-sse-streaming: Added Python 3.11+ + FastAPI 0.115+, LangGraph 0.6.0, LangChain-Core 0.3+, uvicorn 0.32+ with httpx 0.27+ for async streaming
- 002-semantic-search: Added Python 3.11+ + ransformers, torch (MPS support), psycopg2/asyncpg, pgvector, sentence-transformers, LangGraph, FastAPI

### History-Aware Retrieval - Conversation Context for Retrievers (2025-11-06)

**Enhanced retriever interface to accept conversation history for context-aware retrieval**:

- **Key Change**: Retrievers now accept either `str` or `List[BaseMessage]` as query input
  - Backward compatible: existing string queries still work
  - Context-aware: pass full conversation history for better retrieval
  - Strategy-specific: each retriever decides how much history to use

- **Retriever Strategy History Usage**:
  - **SimpleRetriever**: Last message only (`max_history=1`) - fast, simple
  - **RerankRetriever**: Last message only (`max_history=1`) - reranker provides semantic richness
  - **AdvancedRetriever**: Last 5 messages (`max_history=5`) - rich context for LLM query expansion

- **Implementation Details**:
  - `app/retrieval/utils.py`: New utility module with `extract_query_from_messages()` and `format_message_context()`
  - `app/retrieval/base.py`: Updated `RetrieverProtocol` signature to `Union[str, List[BaseMessage]]`
  - `app/retrieval/simple.py`, `rerank.py`, `advanced.py`: Updated to use message extraction utilities
  - `app/agents/rag_agent.py`: Now passes `state["messages"]` to retriever instead of just query string

- **Benefits**:
  - **Context Resolution**: Handles follow-up questions like "What about children?" with implicit context
  - **Separation of Concerns**: Retrievers encapsulate their own history needs (no longer RAG agent's responsibility)
  - **Enhanced Query Expansion**: AdvancedRetriever uses conversation context for better LLM query variations
  - **Zero Performance Impact**: Simple/Rerank strategies unchanged, Advanced adds ~100-200ms for richer context

- **Testing**:
  - `tests/unit/test_retrieval_utils.py`: Comprehensive tests for utility functions
  - Verified backward compatibility with string inputs
  - Tested multi-turn conversations with context extraction

- **Files Modified**:
  - Created: `app/retrieval/utils.py`, `tests/unit/test_retrieval_utils.py`
  - Updated: `app/retrieval/base.py`, `simple.py`, `rerank.py`, `advanced.py`, `app/agents/rag_agent.py`

### Cache Removal - Output-Based Skip Logic (2025-11-01)

**Removed content-hash caching system and implemented simpler output-file-based skip logic**:

- **Key Change**: Replaced cache_store module with output file checking
  - Check if structure.json exists → skip Phase 1 if valid
  - Check each chunk file → skip that chunk if valid (granular skip logic)
  - `--redo` flag forces reprocessing regardless of existing files

  - **Simplicity**: ~200 lines of cache code removed
  - **Transparency**: Output files are the source of truth (no hidden cache layer)
  - **Disk Space**: No duplicate storage (cache + output)
  - **Resumability**: Can resume interrupted extractions at chunk level
  - **Granular Control**: Delete specific chunk to regenerate just that section

  - **Phase 1 (Structure Analysis)**: Checks `{output_dir}/{document_id}/{document_id}_structure.json`
  - **Phase 2 (Chunk Extraction)**: Checks each `{document_id}_chunk_{NNN}.json` individually
  - **Validation**: Attempts to parse files before skipping (regenerates if corrupted)
  - **--redo flag**: Bypasses all skip checks and forces full reprocessing

  - **Phase 1 (Structure Analysis)**: 3 retries with 2s, 4s, 8s backoff
  - **Phase 2 (Chunk Extraction)**: 3 retries with 2s, 4s, 8s backoff
  - Handles LLM API timeouts and transient failures gracefully
  - Works seamlessly with skip logic (already-extracted chunks are skipped on retry)

  - `cli.py`: Removed FileCacheStore, updated --redo help text
  - `chunking_pipeline.py`: Removed cache_store parameter, added chunk extraction retry logic
  - `structure_analyzer.py`: Added output-based skip logic for structure files
  - `chunk_extractor.py`: Added granular per-chunk skip logic

  - `cache_store.py` → `research/cache_store.py` with deprecation notice
  - Research imports updated to reflect new location

  - `cache --stats`: No longer available
  - `cache --clear`: No longer needed

### V3 Experimental Architecture - Cache-Optimized Extractors (2025-10-31 - Late Evening)

**Created experimental chunk extractors optimized for LLM prompt caching**:

  - Metadata now derived from Phase 1 structure analysis (no LLM call needed!)
  - Single source of truth - perfect consistency between phases
  - Phase 1 already has all metadata: chapter_title, section_title, summary

  - Extract text → Generate contextual prefix
  - Metadata derived from Phase 1 structure
  - Cache efficiency: ~50-60%

  - Extract text + prefix merged in single call
  - Tagged output format for robust parsing
  - Cache efficiency: ~80-90%

  - Handles dirty text (tabs, newlines, special characters)
  - Clear field boundaries: `[TAG]content[/TAG]`
  - Robust error detection and parsing

  - `subsection_title`: Changed from `Optional[str]` to `List[str]`
  - Now captures ALL subsections, not just first one
  - Better hierarchical representation for RAG retrieval

  - `tag_parser.py`: XML-style tag parsing utilities
  - `chunk_extractor_v3_experimental.py`: V3A & V3B implementations
  - `V3_EXPERIMENTAL_README.md`: Comprehensive usage guide
  - `PROMPT_CACHING_TODO.md`: Implementation guide for prompt caching

  - Current: Document-first prompt structure (correct for caching)
  - Missing: `cache_control` breakpoints for actual caching
  - Remaining: Implement multipart message format with cache breakpoints
  - Expected savings: 80-90% cost reduction on multi-section documents


### Empty Field Sentinel Fix (2025-10-31 - Evening)

**Replaced invisible tabs with explicit [EMPTY] sentinel for title-only sections**:

  - Invisible characters easily destroyed by `.strip()` or other text processing
  - Difficult to debug (can't see empty fields in logs)
  - Ambiguous for LLMs (unclear if "empty" means "skip column" or "output nothing")

  - **Prompt Update**: Instruct LLM to output `[EMPTY]` for empty start_words/end_words
  - **Parser Update**: Convert `[EMPTY]` to empty string when creating SectionV2 objects
  - **Example**: `Title\t1\tROOT\tSummary\t[EMPTY]\t[EMPTY]` (6 columns, last two explicitly empty)

  - ✅ Explicit > Implicit (Python zen) - visible in logs and debugging
  - ✅ No whitespace ambiguity - can safely use `.strip()` everywhere
  - ✅ LLM-friendly - clearer instruction than "preserve invisible characters"
  - ✅ Robust - won't be destroyed by any text processing

  - Production errors eliminated: 4-column vs 6-column mismatch
  - Parser correctly handles empty fields with explicit sentinel

  - Updated: structure_analyzer_v2.py (prompt + parser with [EMPTY] conversion)
  - Updated: structure_analyzer.py (reverted unnecessary .rstrip() change for consistency)

### Title-Only Section Support (2025-10-31 - Morning)

**Enhanced SectionV2 to support title-only sections**:

  - Title-only sections (headers with no body content) now represented naturally as empty strings
  - Eliminates forced LLM hallucination when no content exists
  - Structure analyzer V2 prompt updated to guide LLMs to output empty values appropriately

  - Sections with both `start_words=""` and `end_words=""` are skipped
  - No chunk generated for title-only sections (content is in subsections)
  - Prevents extraction errors and unnecessary LLM API calls

  - `SectionV2.start_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - `SectionV2.end_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - Default values allow omitting fields entirely in section creation

  - Test cases cover: normal content, empty fields, default values, mixed sections

  - Updated: models.py, structure_analyzer_v2.py, chunk_extractor_v2.py
  - Tests: tests/chunking/unit/test_utilities.py (added TestSectionV2 class)

### Architecture Redesign (2025-10-30)

**Major architectural changes for 001-llm-contextual-chunking**:

  - Phase 1: Structure Analysis (structure_analyzer.py)
  - Phase 2: Chunk Extraction (chunk_extractor.py)
  - Removed: Phase 2 (boundary_detector.py) and Phase 3 (document_segmenter.py)

  - LLMs extract full text based on title + summary metadata
  - Eliminated unreliable character position output (start_char, end_char)
  - 3 LLM calls per section: extract text → metadata → contextual prefix

  - Cache persists until document content changes
  - SHA256-based cache keys for content addressability
  - Supports `--redo` flag to force reprocessing

  - `analyze`: Run Phase 1 structure analysis independently
  - `extract`: Run Phase 2 chunk extraction with pre-analyzed structure
  - `validate`: Quality validation for structures and chunks
  - Enables human-in-the-loop workflows and cost optimization

  - Removed position fields: `Section.start_char`, `Section.end_char`, `Chunk.character_span`
  - Added `Section.summary` field (10-200 chars) for extraction guidance
  - Deleted `BoundaryType` enum and `SegmentBoundary` model
  - Renamed `BoundaryDetectionError` → `ChunkExtractionError`

  - Updated: models.py, cache_store.py, structure_analyzer.py, chunking_pipeline.py, cli.py
  - Created: chunk_extractor.py
  - Deleted: boundary_detector.py, document_segmenter.py


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
