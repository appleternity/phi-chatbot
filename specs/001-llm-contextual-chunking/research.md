# Research: LLM-Based Contextual Document Chunking

**Feature**: 001-llm-contextual-chunking | **Date**: 2025-10-29

## Research Questions

This document resolves all NEEDS CLARIFICATION items from the Technical Context section of plan.md.

---

## 1. OpenRouter SDK vs Requests Library

### Decision: Use `requests` library with manual API handling

### Rationale:
- **Simplicity**: OpenRouter provides an OpenAI-compatible REST API that works perfectly with standard HTTP libraries
- **Control**: Direct API calls give full control over request/response handling, headers, and error management
- **Caching Integration**: Manual request handling makes it easier to implement prompt caching with custom headers
- **No Lock-in**: Avoids dependency on unofficial SDK that may not be maintained
- **Documentation**: OpenRouter's API docs are comprehensive for direct HTTP usage

### Alternatives Considered:
1. **Official OpenRouter SDK**: No official Python SDK exists (only community packages with varying quality)
2. **OpenAI Python SDK**: Could work since OpenRouter is OpenAI-compatible, but adds unnecessary abstraction layer and dependency weight
3. **LangChain**: Too heavy for this use case, adds complexity we don't need

### Implementation Notes:
```python
# Example structure:
import requests
from typing import Dict, Any

class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def chat_completion(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": model, "messages": messages, **kwargs}
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
```

---

## 2. Caching Mechanism

### Decision: Hybrid approach - File-based cache with prompt caching API support

### Rationale:
- **Prompt Caching**: Leverage OpenRouter's prompt caching (where supported) by marking document content with cache control headers
- **Local Cache**: Use file-based JSON cache for structure analysis results to avoid redundant API calls on reprocessing
- **Simplicity**: File-based cache is easy to implement, inspect, and debug (JSON files in `.cache/` directory)
- **Persistence**: File cache survives process restarts, unlike in-memory
- **Cost-Effective**: Combines API-level caching (when available) with local caching for maximum token savings

### Alternatives Considered:
1. **In-memory only**: Lost on process restart, insufficient for batch processing workflows
2. **External service (Redis/Memcached)**: Overkill for CLI tool, adds deployment complexity
3. **SQLite**: More complexity than needed for simple key-value storage

### Implementation Strategy:
```python
# Structure:
# .cache/
# └── structures/
#     └── {document_hash}.json  # Cached structure analysis

import hashlib
import json
from pathlib import Path

class CacheStore:
    def __init__(self, cache_dir: Path = Path(".cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def get_structure(self, document_text: str) -> Optional[dict]:
        key = hashlib.sha256(document_text.encode()).hexdigest()
        cache_file = self.cache_dir / "structures" / f"{key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())
        return None

    def set_structure(self, document_text: str, structure: dict):
        key = hashlib.sha256(document_text.encode()).hexdigest()
        cache_file = self.cache_dir / "structures" / f"{key}.json"
        cache_file.parent.mkdir(exist_ok=True)
        cache_file.write_text(json.dumps(structure, indent=2))
```

**Prompt Caching Integration**:
- Use OpenRouter's prompt caching by structuring prompts with cacheable document content
- Cache structure results locally to avoid redundant API calls entirely on exact matches

---

## 3. LLM API Call Mocking Strategy

### Decision: `pytest-mock` with fixture-based mock responses

### Rationale:
- **Deterministic Tests**: Mock responses ensure tests are fast and don't depend on external API availability
- **Cost-Effective**: No real API calls during test execution (important for CI/CD)
- **Coverage**: Can test error scenarios (API failures, malformed responses) that are hard to reproduce with real calls
- **Standard Practice**: pytest-mock is the de facto standard for Python testing

### Alternatives Considered:
1. **VCR.py (HTTP recording)**: Records real API responses for replay, but requires initial real calls and harder to test edge cases
2. **Real API calls in tests**: Too slow, costly, and unreliable for CI/CD
3. **Custom mock framework**: Reinventing the wheel

### Implementation Pattern:
```python
# tests/chunking/fixtures/llm_responses.py
MOCK_STRUCTURE_RESPONSE = {
    "id": "chatcmpl-test",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "chapter_title": "Introduction to Testing",
                "sections": [
                    {"title": "Why Test?", "start": 0, "end": 500},
                    {"title": "Testing Types", "start": 500, "end": 1000}
                ]
            })
        }
    }]
}

# tests/chunking/unit/test_structure_analyzer.py
def test_analyze_structure_success(mocker):
    mock_post = mocker.patch('requests.post')
    mock_post.return_value.json.return_value = MOCK_STRUCTURE_RESPONSE
    mock_post.return_value.status_code = 200

    analyzer = StructureAnalyzer(llm_client=OpenRouterClient(api_key="test"))
    result = analyzer.analyze(document_text="Test document...")

    assert result.chapter_title == "Introduction to Testing"
    assert len(result.sections) == 2
```

---

## 4. Model Selection for Three Phases

### Decision:
- **Phase 1 & 2**: `openai/gpt-4o` or `anthropic/claude-3.5-sonnet` (high-capability, default: `openai/gpt-4o`)
- **Phase 3**: `google/gemini-2.0-flash-exp` (fast, cost-effective)
- **User Configurable**: Each phase model can be overridden via CLI options

### Rationale:

**Phase 1 (Structure Identification)**:
- Requires strong reasoning to understand document hierarchy
- Needs to handle ambiguous/unstructured text
- GPT-4o or Claude 3.5 Sonnet excel at structural analysis

**Phase 2 (Boundary Determination)**:
- Requires semantic understanding of content
- Must balance token limits with semantic coherence
- High-capability models provide better boundary decisions

**Phase 3 (Segmentation & Cleaning)**:
- Mostly text manipulation and formatting
- Follows structured instructions from Phase 1 & 2
- Gemini Flash provides excellent speed/cost ratio for this task

### Implementation:
```python
class ChunkingPipeline:
    def __init__(
        self,
        llm_provider: LLMProvider,
        structure_model: str = "openai/gpt-4o",
        boundary_model: str = "openai/gpt-4o",
        segmentation_model: str = "google/gemini-2.0-flash-exp"
    ):
        self.llm_provider = llm_provider
        self.structure_model = structure_model
        self.boundary_model = boundary_model
        self.segmentation_model = segmentation_model
```

**User Control**: Models are configurable via:
1. CLI options: `--structure-model`, `--boundary-model`, `--segmentation-model`
2. Environment variables: `STRUCTURE_MODEL`, `BOUNDARY_MODEL`, `SEGMENTATION_MODEL`
3. Default values as shown above

**Cost Optimization**: Users can test with cheaper models (e.g., all Gemini Flash) or use premium models (e.g., all GPT-4o) based on budget/quality needs.

---

## 5. Token Counting Library

### Decision: Use `tiktoken` for OpenAI models, fallback to character-based estimation

### Rationale:
- **Accuracy**: tiktoken provides accurate token counts for OpenAI tokenizers (GPT-4, GPT-3.5)
- **Speed**: Fast C implementation, suitable for batch processing
- **Standard**: Maintained by OpenAI, widely adopted
- **Limitation**: Doesn't support all models (Gemini, Claude use different tokenizers)

### Fallback Strategy:
```python
def count_tokens(text: str, model: str) -> int:
    if "openai" in model or "gpt" in model:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    else:
        # Conservative estimate: 1 token ≈ 4 characters
        return len(text) // 4
```

**Note**: For precise token counts with Gemini/Claude, we accept approximate counts for chunk size enforcement. The 1000-token limit has enough buffer (700-1000 range) to accommodate estimation errors.

---

## 6. Text Alignment Algorithm

### Decision: Use Python's `difflib.SequenceMatcher` for text coverage verification

### Rationale:
- **Built-in**: Standard library, no external dependency
- **Proven**: Used widely for diff tools, reliable algorithm
- **Efficient**: Fast enough for document-sized text (5000-10000 words)
- **Flexible**: Can detect both missing text and duplications

### Implementation Strategy:
```python
from difflib import SequenceMatcher

def verify_text_coverage(original: str, chunks: list[str]) -> tuple[float, list[str]]:
    """
    Verify that chunks cover all original text.

    Returns:
        (coverage_ratio, missing_segments)
        coverage_ratio: 0.0-1.0 (1.0 = perfect coverage)
        missing_segments: List of text segments not found in any chunk
    """
    reconstructed = " ".join(chunks)
    matcher = SequenceMatcher(None, original, reconstructed)

    coverage_ratio = matcher.ratio()

    # Find missing segments
    missing = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'delete':
            missing.append(original[i1:i2])

    return coverage_ratio, missing
```

**Validation Rule**: Fail if `coverage_ratio < 0.99` (99% coverage required to account for minor whitespace normalization).

---

## 7. Metadata Validation Strategy

### Decision: Pydantic models with strict validation

### Rationale:
- **Type Safety**: Pydantic enforces field types and constraints at runtime
- **Fail-Fast**: Validation errors raised immediately with clear messages
- **Documentation**: Models serve as living documentation of data structure
- **Ecosystem**: Well-integrated with Python type hints and IDE support

### Implementation:
```python
from pydantic import BaseModel, Field, validator

class ChunkMetadata(BaseModel):
    chapter_title: str = Field(..., min_length=1, description="Chapter title (required)")
    section_title: str = Field(..., min_length=1, description="Section title (required)")
    subsection_title: Optional[str] = Field(None, description="Subsection title (optional)")
    summary: str = Field(..., min_length=10, max_length=500, description="Brief summary")

    @validator('summary')
    def summary_not_empty_or_placeholder(cls, v):
        if v.strip().lower() in ['', 'n/a', 'none', 'todo']:
            raise ValueError('Summary must be meaningful, not placeholder')
        return v

class Chunk(BaseModel):
    chunk_id: str
    source_document: str
    chunk_text: str = Field(..., min_length=1)
    metadata: ChunkMetadata
    token_count: int = Field(..., ge=1, le=1000)

    @validator('chunk_text')
    def chunk_text_has_content(cls, v):
        if not v.strip():
            raise ValueError('Chunk text cannot be empty or whitespace-only')
        return v
```

**Validation Enforcement**: All chunks validated before writing to output. Any validation error triggers immediate failure with detailed error message.

---

## 8. Output Format Specification

### Decision: JSON Lines (JSONL) with structured schema

### Rationale:
- **Streaming**: Each line is independent, supports streaming writes
- **RAG-Friendly**: Standard format for vector database ingestion
- **Human-Readable**: JSON is inspectable for debugging
- **Tool Support**: Wide ecosystem support (jq, pandas, vector DB loaders)

### Schema:
```json
{
  "chunk_id": "doc1_chunk_001",
  "source_document": "chapter_01_introduction.txt",
  "chunk_text": "This chunk is from Introduction chapter, Section 1.2 on testing methodologies. Testing is essential...",
  "metadata": {
    "chapter_title": "Introduction",
    "section_title": "Testing Methodologies",
    "subsection_title": null,
    "summary": "Overview of software testing approaches and their benefits"
  },
  "token_count": 847,
  "processing_metadata": {
    "phase_1_model": "openai/gpt-4o",
    "phase_2_model": "openai/gpt-4o",
    "phase_3_model": "google/gemini-2.0-flash-exp",
    "processed_at": "2025-10-29T10:30:45Z",
    "cache_hit": false
  }
}
```

**File Naming**: `{input_folder_name}_chunks_{timestamp}.jsonl`

---

## 9. Error Handling Strategy

### Decision: Fail-fast with structured exceptions

### Rationale:
- **User Requirement**: Explicit requirement to fail immediately (no graceful degradation)
- **Debugging**: Early failures make root cause identification easier
- **Data Integrity**: Prevents partial/corrupted output from propagating

### Exception Hierarchy:
```python
class ChunkingError(Exception):
    """Base exception for chunking errors"""
    pass

class StructureAnalysisError(ChunkingError):
    """Phase 1 structure identification failed"""
    pass

class BoundaryDetectionError(ChunkingError):
    """Phase 2 boundary determination failed"""
    pass

class SegmentationError(ChunkingError):
    """Phase 3 segmentation/cleaning failed"""
    pass

class TextCoverageError(ChunkingError):
    """Text alignment verification failed"""
    def __init__(self, coverage_ratio: float, missing_segments: list[str]):
        self.coverage_ratio = coverage_ratio
        self.missing_segments = missing_segments
        super().__init__(
            f"Text coverage validation failed: {coverage_ratio:.2%} coverage. "
            f"Missing {len(missing_segments)} segments."
        )

class MetadataValidationError(ChunkingError):
    """Metadata completeness validation failed"""
    pass
```

**Error Context**: Each exception includes:
- Document identifier
- Processing phase
- Detailed error message
- Actionable recovery suggestion (e.g., "Check document structure", "Verify API key")

---

## 10. CLI Framework

### Decision: Use `typer` with `typer.Option` and `Annotated` (no `typer.Argument`)

### Rationale:
- **Type Safety**: Typer uses Python type hints for automatic validation
- **User-Friendly**: Automatic help generation, validation, and error messages
- **Modern**: Uses Python 3.6+ features (Annotated, type hints)
- **Explicit**: All parameters as options (--flag) rather than positional arguments for clarity
- **Rich Integration**: Built-in support for rich console output and progress bars

### Alternatives Considered:
1. **argparse**: Too verbose, manual validation, outdated patterns
2. **click**: Good but Typer is more Pythonic with type hints
3. **fire**: Too magical, lacks explicit parameter definitions

### Implementation Pattern:
```python
import typer
from typing import Annotated
from pathlib import Path

app = typer.Typer()

@app.command()
def process(
    input_path: Annotated[Path, typer.Option(
        "--input", "-i",
        help="Path to document file or folder"
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
        help="Maximum tokens per chunk"
    )] = 1000,
    log_level: Annotated[str, typer.Option(
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )] = "INFO"
):
    """Process documents into contextually-enriched chunks for RAG."""
    # Implementation here
    pass

if __name__ == "__main__":
    app()
```

**Benefits for Users**:
- Clear, self-documenting CLI with automatic `--help`
- Type validation (Path must exist, int must be number, etc.)
- Default values clearly visible
- IDE autocomplete support

---

## 11. LLM Output Format

### Decision: Use TSV (Tab-Separated Values) instead of JSON for LLM responses

### Rationale:
- **Reliability**: LLMs frequently produce malformed JSON (missing quotes, trailing commas, unescaped characters)
- **Simplicity**: TSV is easier for LLMs to generate correctly with clear examples in prompts
- **Parsing**: Simple `split('\t')` vs complex JSON parsing with error handling
- **Debuggability**: Easy to inspect TSV output visually, clear when format is wrong

### Alternatives Considered:
1. **JSON**: Standard but unreliable, requires extensive error recovery
2. **CSV**: Similar to TSV but commas in text cause issues, needs escaping
3. **XML**: Too verbose, LLMs struggle with closing tags

### Implementation Strategy:

**Prompt Engineering with Format Examples**:
```python
# Phase 1: Structure Analysis Prompt
structure_prompt = """
Analyze this document's hierarchical structure.

Output format: TSV with columns: title, level, start_char, end_char, parent_title
- level: 1=section, 2=subsection, 3=subsubsection
- parent_title: Use "ROOT" for top-level sections

Example output:
Introduction	1	0	1234	ROOT
Why Test?	2	0	567	Introduction
Types of Testing	2	567	1234	Introduction

Now analyze this document:
{document_text}

Output (TSV format):
"""

# Phase 2: Boundary Detection Prompt
boundary_prompt = """
Determine optimal chunk boundaries for this section.

Output format: TSV with columns: position, boundary_type, justification
- boundary_type: SECTION_BREAK, SEMANTIC_SHIFT, SIZE_CONSTRAINT
- position: character position in document

Example output:
0	DOCUMENT_START	Beginning of document
567	SECTION_BREAK	New section "Why Test?" begins
1234	DOCUMENT_END	End of document

Section to analyze: {section_text}
Max tokens per chunk: {max_tokens}

Output (TSV format):
"""
```

**Parsing with Error Handling**:
```python
def parse_tsv_structure(tsv_output: str) -> List[Section]:
    """Parse TSV structure output from LLM."""
    sections = []
    lines = tsv_output.strip().split('\n')

    for line_num, line in enumerate(lines, 1):
        parts = line.split('\t')
        if len(parts) != 5:
            raise ValueError(
                f"Line {line_num}: Expected 5 columns, got {len(parts)}. "
                f"Line: {line}"
            )

        title, level_str, start_str, end_str, parent = parts

        try:
            sections.append(Section(
                title=title.strip(),
                level=int(level_str),
                start_char=int(start_str),
                end_char=int(end_str),
                parent_section=None if parent == "ROOT" else parent.strip()
            ))
        except ValueError as e:
            raise ValueError(
                f"Line {line_num}: Invalid data - {e}. Line: {line}"
            )

    return sections
```

**Benefits**:
- Clear format examples in every prompt guide LLM output
- Simple validation (count columns, parse integers)
- Fail-fast on malformed output with line-specific error messages
- Easy to debug (just print the TSV, visually inspect)

---

## Summary

All technical uncertainties resolved. Key decisions:
1. **HTTP Library**: `requests` for direct API control
2. **Caching**: Hybrid file-based + prompt caching (CONFIRMED by user)
3. **Testing**: pytest-mock with fixture-based mocks
4. **Models**: GPT-4o/Claude 3.5 (phases 1-2), Gemini Flash (phase 3), user-configurable per phase
5. **Token Counting**: tiktoken with character-based fallback
6. **Text Alignment**: difflib.SequenceMatcher (99% coverage threshold)
7. **Validation**: Pydantic models with strict constraints
8. **Output Format (Final)**: JSONL with structured schema
9. **LLM Output Format**: TSV with format examples in prompts (CONFIRMED by user)
10. **Errors**: Fail-fast with structured exception hierarchy
11. **CLI**: typer with typer.Option and Annotated (no typer.Argument)

Ready to proceed to Phase 1 (Design & Contracts).
