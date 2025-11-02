# Quickstart: LLM-Based Contextual Document Chunking

**Feature**: 001-llm-contextual-chunking | **Date**: 2025-10-29

## Overview

This quickstart guide helps developers understand the document chunking system, set up their environment, and run their first chunking operation.

---

## What This System Does

The document chunking system processes book chapters (plain text or markdown files) into semantically coherent, contextually-enriched chunks optimized for RAG (Retrieval-Augmented Generation) pipelines.

**Key Features**:
- **LLM-Driven Structure Analysis**: Identifies document hierarchy (chapters, sections, subsections)
- **Semantic Boundary Detection**: Splits content at meaningful points, not arbitrary character counts
- **Contextual Enrichment**: Prepends context to each chunk (Anthropic's Contextual Retrieval approach)
- **Metadata Generation**: Adds chapter title, section title, and summary to every chunk
- **100% Text Coverage**: Verifies no text is lost or duplicated during chunking
- **Prompt Caching**: Reduces API costs by caching structure analyses

**Use Case**: Prepare educational content (book chapters) for RAG systems that need to retrieve relevant information with proper context.

---

## Prerequisites

**Required**:
- Python 3.11 or higher
- OpenRouter API key ([get one here](https://openrouter.ai/))
- Book chapters as plain text (.txt) or markdown (.md) files

**Optional**:
- Knowledge of LangGraph/multi-agent systems (if integrating with existing agents)

---

## Installation

### 1. Clone Repository
```bash
git clone <repo-url>
cd langgraph
git checkout 001-llm-contextual-chunking
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
# Or using poetry:
poetry install
```

**Dependencies**:
- `requests` - HTTP client for OpenRouter API
- `tiktoken` - Token counting for OpenAI models
- `pydantic` - Data validation and settings management
- `python-dotenv` - Environment variable management
- `typer` - Modern CLI framework with type hints
- `pytest`, `pytest-mock`, `pytest-cov` - Testing framework

### 3. Configure Environment
Create `.env` file in project root:
```bash
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # Optional, defaults to this

# Optional model overrides
STRUCTURE_MODEL=openai/gpt-4o  # Default for Phase 1 & 2
SEGMENTATION_MODEL=google/gemini-2.0-flash-exp  # Default for Phase 3

# Optional caching
CACHE_DIR=.cache  # Default cache directory
```

---

## Quick Start: Process a Single Document

### Example 1: Process One Chapter

Create a sample chapter file `chapter_01.txt`:
```text
# Chapter 1: Introduction to Testing

Testing is a critical part of software development. This chapter covers the fundamentals.

## Why Test?

Testing helps catch bugs early...

## Types of Testing

There are several types of testing...
```

**Run the chunker**:
```bash
python -m src.chunking.cli process --input chapter_01.txt --output output/
```

**Output**:
```
Processing: chapter_01.txt
Phase 1: Analyzing structure... ✓ (2.3s)
Phase 2: Detecting boundaries... ✓ (1.5s)
Phase 3: Segmenting document... ✓ (4.2s)
Validation: Text coverage... ✓ 100.0%
Validation: Metadata completeness... ✓ 100.0%

Results:
- Chunks generated: 2
- Total tokens: 1,847
- Coverage: 100.0%
- Output: output/chunks.jsonl
```

**Inspect output**:
```bash
cat output/chunks.jsonl | jq .
```

```json
{
  "chunk_id": "chapter_01_chunk_001",
  "source_document": "chapter_01",
  "chunk_text": "This chunk is from Chapter 1 (Introduction to Testing), Section: Why Test?. Testing is a critical part of software development...",
  "metadata": {
    "chapter_title": "Introduction to Testing",
    "section_title": "Why Test?",
    "subsection_title": null,
    "summary": "Explains importance of testing in catching bugs early"
  },
  "token_count": 847,
  ...
}
```

---

## Process a Folder of Chapters

### Example 2: Batch Process Multiple Chapters

**Folder structure**:
```
book_chapters/
├── chapter_01_introduction.txt
├── chapter_02_testing_basics.txt
├── chapter_03_advanced_topics.txt
└── chapter_04_best_practices.txt
```

**Run batch processing**:
```bash
python -m src.chunking.cli process --input book_chapters/ --output output/
```

**Note**: The CLI automatically detects if input is a file or folder.

**Output**:
```
Processing folder: book_chapters/
Found 4 documents

[1/4] Processing: chapter_01_introduction.txt... ✓
[2/4] Processing: chapter_02_testing_basics.txt... ✓
[3/4] Processing: chapter_03_advanced_topics.txt... ✓
[4/4] Processing: chapter_04_best_practices.txt... ✓

Batch Results:
- Total documents: 4
- Successful: 4
- Failed: 0
- Total chunks: 12
- Total tokens: 10,247
- Output: output/book_chapters_chunks_20251029_103045.jsonl
```

---

## Understanding the Output

### JSONL Format

Each line in the output file is a JSON object representing one chunk:

```json
{
  "chunk_id": "chapter_01_chunk_001",
  "source_document": "chapter_01_introduction",
  "chunk_text": "Contextual prefix + original text...",
  "original_text": "Original text without prefix...",
  "contextual_prefix": "This chunk is from...",
  "metadata": {
    "chapter_title": "Introduction to Testing",
    "section_title": "Why Test?",
    "subsection_title": null,
    "summary": "Brief summary of chunk content"
  },
  "token_count": 847,
  "character_span": [0, 1234],
  "processing_metadata": {
    "phase_1_model": "openai/gpt-4o",
    "phase_2_model": "openai/gpt-4o",
    "phase_3_model": "google/gemini-2.0-flash-exp",
    "processed_at": "2025-10-29T10:30:45Z",
    "cache_hit": false,
    "processing_time_ms": 7890
  }
}
```

### Field Explanations

- **chunk_id**: Unique identifier (format: `{doc_id}_chunk_{nnn}`)
- **source_document**: Original filename (without extension)
- **chunk_text**: Full text with contextual prefix (use this for embedding)
- **original_text**: Original text without prefix (for reference)
- **contextual_prefix**: Context prepended to chunk (Anthropic approach)
- **metadata**: Structured metadata for filtering/routing
  - **chapter_title**: Chapter-level title
  - **section_title**: Section within chapter
  - **subsection_title**: Subsection if applicable (null otherwise)
  - **summary**: AI-generated brief summary
- **token_count**: Actual token count (≤ 1000 guaranteed)
- **character_span**: [start, end] positions in original document
- **processing_metadata**: Processing details and model info

---

## Use Cases

### 1. Ingest into Vector Database

```python
import json
from pathlib import Path

# Load chunks
chunks = []
with open("output/chunks.jsonl") as f:
    for line in f:
        chunks.append(json.loads(line))

# Ingest into vector DB (example with Pinecone)
for chunk in chunks:
    embedding = embed_model.encode(chunk["chunk_text"])
    vector_db.upsert(
        id=chunk["chunk_id"],
        vector=embedding,
        metadata={
            "text": chunk["chunk_text"],
            "chapter": chunk["metadata"]["chapter_title"],
            "section": chunk["metadata"]["section_title"],
            "summary": chunk["metadata"]["summary"],
            "source": chunk["source_document"]
        }
    )
```

### 2. Filter by Chapter/Section

```bash
# Extract all chunks from Chapter 1
cat output/chunks.jsonl | jq 'select(.metadata.chapter_title == "Introduction to Testing")'

# Extract specific section
cat output/chunks.jsonl | jq 'select(.metadata.section_title == "Why Test?")'
```

### 3. Analyze Token Distribution

```bash
# Get token count statistics
cat output/chunks.jsonl | jq '.token_count' | python -c "
import sys
tokens = [int(line) for line in sys.stdin]
print(f'Min: {min(tokens)}, Max: {max(tokens)}, Avg: {sum(tokens)/len(tokens):.1f}')
"
```

---

## Advanced Configuration

### Custom Model Selection

Override default models for each phase via CLI:
```bash
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model anthropic/claude-3.5-sonnet \
  --boundary-model openai/gpt-4o \
  --segmentation-model google/gemini-2.0-flash-exp
```

**Model Selection Guide**:
- **Phase 1 (Structure)**: High-capability model recommended
  - `openai/gpt-4o` (default, excellent reasoning)
  - `anthropic/claude-3.5-sonnet` (alternative, great at structure)
  - `google/gemini-2.0-flash-exp` (budget option, less accurate)

- **Phase 2 (Boundaries)**: High-capability model recommended
  - `openai/gpt-4o` (default)
  - `anthropic/claude-3.5-sonnet` (alternative)

- **Phase 3 (Segmentation)**: Fast model sufficient
  - `google/gemini-2.0-flash-exp` (default, fast and cheap)
  - `openai/gpt-4o` (higher quality, slower and expensive)

**Cost vs Quality**:
```bash
# Budget mode (faster, cheaper, less accurate)
--structure-model google/gemini-2.0-flash-exp \
--boundary-model google/gemini-2.0-flash-exp \
--segmentation-model google/gemini-2.0-flash-exp

# Premium mode (slower, expensive, highest quality)
--structure-model openai/gpt-4o \
--boundary-model openai/gpt-4o \
--segmentation-model openai/gpt-4o
```

### Adjust Chunk Size

```bash
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --max-tokens 800
```

**Note**: Smaller chunks = more chunks, potentially higher cost. Default 1000 tokens balances context and granularity.

### Enable Verbose Logging

```bash
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --log-level DEBUG
```

**DEBUG output includes**:
- Structure analysis results
- Boundary detection decisions
- Token counts per phase
- Cache hit/miss information

### Cache Management

**View cache statistics**:
```bash
python -m src.chunking.cli cache --stats
```

**Clear cache**:
```bash
python -m src.chunking.cli cache --clear
```

**Note**: Cache management commands only relevant if using file-based caching.

---

## Troubleshooting

### Error: "Text coverage validation failed"

**Symptom**: Processing fails with coverage < 99%

**Causes**:
- LLM generated chunks with missing text segments
- Text cleaning removed too much content

**Solution**:
1. Check document formatting (ensure no corrupted characters)
2. Try different model for Phase 3 (segmentation)
3. Review error message for missing segments
4. Report issue if persistent

### Error: "Metadata validation failed"

**Symptom**: Chunk missing required metadata fields

**Causes**:
- LLM failed to generate metadata
- Document lacks clear structure

**Solution**:
1. Ensure document has headings/sections
2. Try higher-capability model for Phase 3
3. Check document formatting

### Error: "LLMProviderError: 401 Unauthorized"

**Symptom**: API authentication failure

**Solution**:
1. Verify `OPENROUTER_API_KEY` in `.env` file
2. Check API key is valid and has sufficient credits
3. Test API key with curl:
```bash
curl https://openrouter.ai/api/v1/auth/key -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Slow Processing

**Symptom**: Taking too long to process documents

**Solutions**:
1. **Enable caching**: Second run on similar documents will be much faster
2. **Use faster models**: Try `google/gemini-2.0-flash-exp` for all phases (less accurate but faster)
3. **Reduce chunk size**: Smaller `--max-tokens` = fewer chunks = faster processing

---

## Integration with Existing Agents

If integrating with existing LangGraph agents:

```python
from src.chunking.chunking_pipeline import ChunkingPipeline
from src.chunking.llm_provider import OpenRouterProvider

# Initialize pipeline
llm_provider = OpenRouterProvider(api_key=os.getenv("OPENROUTER_API_KEY"))
pipeline = ChunkingPipeline(llm_provider=llm_provider)

# Process document
from src.chunking.models import Document
from pathlib import Path

doc = Document.from_file(Path("chapter.txt"))
result = pipeline.process_document(doc)

# Use chunks in agent workflow
for chunk in result.chunks:
    # Add to vector store, process, etc.
    pass
```

---

## Testing

### Run Tests

```bash
# All tests
pytest tests/chunking/

# Specific test suite
pytest tests/chunking/contract/
pytest tests/chunking/integration/
pytest tests/chunking/unit/

# With coverage
pytest tests/chunking/ --cov=src.chunking --cov-report=html
```

### Test with Mock LLM

```python
from tests.chunking.fixtures.llm_responses import MOCK_STRUCTURE_RESPONSE
from src.chunking.llm_provider import MockLLMProvider

# Create mock provider
mock_llm = MockLLMProvider(responses={
    "openai/gpt-4o": MOCK_STRUCTURE_RESPONSE
})

# Use in tests
pipeline = ChunkingPipeline(llm_provider=mock_llm)
result = pipeline.process_document(test_document)
```

---

## Next Steps

1. **Read the Plan**: [plan.md](plan.md) - Full technical design
2. **Explore Data Models**: [data-model.md](data-model.md) - All data structures
3. **Review Contracts**: [contracts/component_interfaces.md](contracts/component_interfaces.md) - Component interfaces
4. **Check Research**: [research.md](research.md) - Technology decisions and rationale
5. **Implement Tasks**: [tasks.md](tasks.md) - Detailed implementation tasks (created by `/speckit.tasks`)

---

## Support

- **Issues**: File bug reports or feature requests in GitHub Issues
- **Documentation**: Full docs in `specs/001-llm-contextual-chunking/`
- **Testing**: Comprehensive test suite in `tests/chunking/`

Happy chunking! 🚀
