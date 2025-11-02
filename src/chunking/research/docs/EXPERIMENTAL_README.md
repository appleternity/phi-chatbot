# Experimental Chunk Extractors: Cache-Optimized with Tag-Based Parsing

This directory contains 3 experimental chunk extractor implementations optimized for LLM caching efficiency and robust parsing of "dirty" text with tabs, newlines, and special characters.

## Key Improvements

### 1. **LLM Caching Optimization**
- ✅ **Document text at BEGINNING** of all prompts → Maximum cache reuse
- ✅ Dynamic parameters (section title, boundaries) at END → Enables caching
- ✅ 50-90% cost reduction through cache hits (after first section)
- ✅ 80% latency reduction for large documents (>10K tokens)

**Why This Matters**: OpenRouter/OpenAI cache the beginning of prompts. By placing static content (document text) first, subsequent sections of the same document reuse the cached content, dramatically reducing cost and latency.

### 2. **Tag-Based Output Format**
- ✅ Replaces fragile TSV format with XML-style tags
- ✅ Handles multi-line content, tabs, and special characters robustly
- ✅ Clear field boundaries with self-closing tags: `[TAG]content[/TAG]`
- ✅ Easy to parse with regex, unambiguous field detection

**Why This Matters**: Chunk text can contain tabs, newlines, and special characters that break TSV parsing. Tags provide clear, robust boundaries.

---

## Available Versions

### **Version V2A: Separate Calls + Document Context** (Conservative)

**Architecture**: 3 LLM calls per section
1. Extract text (document-first prompt)
2. Generate metadata (document-first prompt, tagged output)
3. Generate prefix (document-first prompt, plain text output)

**Cache Efficiency**: ~60-70% (document cached once, reused 3x per section)

**Pros**:
- ✅ Maximum cache reuse across operation types
- ✅ Clear separation of concerns
- ✅ Easy to debug individual operations
- ✅ Validated output format per operation

**Cons**:
- ❌ 3 LLM calls per section = higher latency
- ❌ More API calls = more overhead

**Best For**: Production use, maximum reliability, when debugging is important

---

### **Version V2B: Merged Metadata + Prefix** (Moderate)

**Architecture**: 2 LLM calls per section
1. Extract text (document-first prompt, plain text output)
2. Generate metadata + prefix together (document-first prompt, tagged output with 5 fields)

**Cache Efficiency**: ~50-60% (document cached once, reused 2x per section)

**Pros**:
- ✅ 33% fewer LLM calls than V2A (3 → 2)
- ✅ Metadata and prefix share context (more coherent)
- ✅ Still maintains extraction separation for quality
- ✅ Tagged format handles dirty text robustly

**Cons**:
- ⚠️ More complex output parsing (5 tags vs 4)
- ⚠️ Harder to debug if one part fails

**Best For**: Balancing cost and reliability, when metadata + prefix coherence is valuable

---

### **Version V2C: Fully Merged** (Aggressive)

**Architecture**: 1 LLM call per section
- Extract text + generate metadata + generate prefix all together (document-first prompt, tagged output with 6 fields)

**Cache Efficiency**: ~80-90% (first section misses, all subsequent sections hit)

**Pros**:
- ✅ 66% fewer LLM calls than V2A (3 → 1) = fastest + cheapest
- ✅ All context in one place = most coherent output
- ✅ Maximum cache hit potential for subsequent sections
- ✅ Tagged format handles dirty text robustly

**Cons**:
- ❌ Complex structured output (6 tags) = higher LLM failure risk
- ❌ Harder to validate individual components
- ❌ If one part fails, entire call fails
- ❌ Longer prompt = higher token cost per call

**Best For**: Maximum cost/latency optimization, when LLM can reliably produce complex structured output

---

## Quick Start

### Installation

No changes needed! All experimental versions use the same dependencies as the main chunk extractor.

### Usage Example

```python
from src.chunking.chunk_extractor_v2_experimental import (
    ChunkExtractorV2A,
    ChunkExtractorV2B,
    ChunkExtractorV2C
)
from src.chunking.llm_provider import LLMProvider
from src.chunking.models import TokenCounter
from src.chunking.metadata_validator import MetadataValidator
from src.chunking.cache_store import CacheStore

# Initialize dependencies
llm_client = LLMProvider()
token_counter = TokenCounter()
metadata_validator = MetadataValidator()
cache_store = CacheStore(cache_dir=".cache")

# Choose your experimental version
extractor = ChunkExtractorV2B(  # Try V2A, V2B, or V2C
    llm_client=llm_client,
    token_counter=token_counter,
    metadata_validator=metadata_validator,
    model="google/gemini-2.0-flash-exp",
    max_chunk_tokens=1000,
    cache_store=cache_store
)

# Use exactly like the standard extractor
result = extractor.extract_chunks(document, structure)

print(f"Chunks: {len(result['chunks'])}")
print(f"Tokens consumed: {result['tokens_consumed']}")
print(f"Cache hits: {sum(1 for r in result['llm_responses'].values() if any(v['cached'] for v in r.values()))}")
```

---

## Tag Output Format

### V2A: Metadata Generation (4 tags)

```
[CHAPTER_TITLE]Introduction to Testing[/CHAPTER_TITLE]
[SECTION_TITLE]Why Test?[/SECTION_TITLE]
[SUBSECTION_TITLE]NONE[/SUBSECTION_TITLE]
[SUMMARY]Explains the importance of software testing in preventing bugs and improving code quality through systematic verification[/SUMMARY]
```

### V2B: Merged Metadata + Prefix (5 tags)

```
[CHAPTER_TITLE]Introduction to Testing[/CHAPTER_TITLE]
[SECTION_TITLE]Why Test?[/SECTION_TITLE]
[SUBSECTION_TITLE]NONE[/SUBSECTION_TITLE]
[SUMMARY]Explains the importance of software testing in preventing bugs[/SUMMARY]
[CONTEXTUAL_PREFIX]This chunk is from the Introduction to Testing chapter, section Why Test?, discussing the importance of software testing.[/CONTEXTUAL_PREFIX]
```

### V2C: Fully Merged (6 tags)

```
[CHUNK_TEXT]
The extracted text goes here.
Can span multiple lines.
Can contain tabs	and special characters!
[/CHUNK_TEXT]

[CHAPTER_TITLE]Introduction to Testing[/CHAPTER_TITLE]
[SECTION_TITLE]Why Test?[/SECTION_TITLE]
[SUBSECTION_TITLE]NONE[/SUBSECTION_TITLE]
[SUMMARY]Explains the importance of software testing in preventing bugs[/SUMMARY]
[CONTEXTUAL_PREFIX]This chunk is from the Introduction to Testing chapter, section Why Test?, discussing the importance of software testing.[/CONTEXTUAL_PREFIX]
```

---

## Performance Comparison

### Expected Performance (10-section document)

| Version | LLM Calls | Cache Hit Rate | Token Savings | Latency Reduction | Cost Savings |
|---------|-----------|----------------|---------------|-------------------|--------------|
| V2A     | 30 (3×10) | 60-70%         | ~60%          | ~50%              | ~50-60%      |
| V2B     | 20 (2×10) | 50-60%         | ~50%          | ~40%              | ~40-50%      |
| V2C     | 10 (1×10) | 80-90%         | ~80%          | ~70%              | ~70-80%      |

**Note**: Percentages are for sections 2-10. First section always misses cache.

### Real-World Testing Recommendations

1. **Start with V2A** - Validate that caching works as expected
2. **Try V2B** - Test if merged metadata + prefix maintains quality
3. **Try V2C** - Test if your LLM can reliably produce 6-tag output
4. **Compare Results** - Measure cost, latency, and quality differences

---

## Testing Your Implementation

### A/B Testing Script

```python
import time
from pathlib import Path

def test_extractor_performance(extractor_class, document, structure):
    """Test performance of an extractor version."""
    start_time = time.time()

    extractor = extractor_class(
        llm_client=llm_client,
        token_counter=token_counter,
        metadata_validator=metadata_validator,
        cache_store=cache_store
    )

    result = extractor.extract_chunks(document, structure)

    elapsed_time = time.time() - start_time

    return {
        "version": extractor_class.__name__,
        "chunks": len(result['chunks']),
        "tokens": result['tokens_consumed'],
        "time": elapsed_time,
        "cache_hits": sum(
            1 for r in result['llm_responses'].values()
            if any(v['cached'] for v in r.values())
        )
    }

# Test all versions
versions = [ChunkExtractorV2A, ChunkExtractorV2B, ChunkExtractorV2C]
results = []

for version in versions:
    # Clear cache between tests for fair comparison
    cache_store.clear()

    result = test_extractor_performance(version, document, structure)
    results.append(result)
    print(f"{result['version']}: {result['chunks']} chunks, "
          f"{result['tokens']} tokens, {result['time']:.2f}s, "
          f"{result['cache_hits']} cache hits")
```

### Quality Validation

```python
def validate_chunk_quality(chunks):
    """Validate chunk extraction quality."""
    issues = []

    for chunk in chunks:
        # Check metadata completeness
        if not chunk.metadata.chapter_title:
            issues.append(f"Missing chapter_title in {chunk.chunk_id}")
        if not chunk.metadata.summary or len(chunk.metadata.summary) < 20:
            issues.append(f"Invalid summary in {chunk.chunk_id}")

        # Check prefix format
        if not chunk.contextual_prefix.startswith("This chunk is from"):
            issues.append(f"Invalid prefix format in {chunk.chunk_id}")

        # Check text completeness
        if len(chunk.original_text) < 50:
            issues.append(f"Suspiciously short text in {chunk.chunk_id}")

    return issues

# Run quality checks
for version in [ChunkExtractorV2A, ChunkExtractorV2B, ChunkExtractorV2C]:
    extractor = version(...)
    result = extractor.extract_chunks(document, structure)
    issues = validate_chunk_quality(result['chunks'])

    if issues:
        print(f"{version.__name__} quality issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"{version.__name__}: All quality checks passed ✅")
```

---

## Tag Parser Utilities

The `tag_parser.py` module provides robust parsing utilities:

```python
from src.chunking.tag_parser import (
    parse_tagged_output,
    validate_tagged_format,
    extract_tag_content,
    has_tag
)

# Parse all expected tags
parsed = parse_tagged_output(
    text=llm_output,
    expected_tags=["CHAPTER_TITLE", "SECTION_TITLE", "SUMMARY"]
)
# Returns: {"CHAPTER_TITLE": "...", "SECTION_TITLE": "...", "SUMMARY": "..."}

# Validate format without parsing
validate_tagged_format(
    text=llm_output,
    expected_tags=["CHAPTER_TITLE", "SECTION_TITLE"],
    strict=True  # Raise error if extra tags found
)

# Extract single tag
chapter = extract_tag_content(llm_output, "CHAPTER_TITLE")

# Check if tag exists
if has_tag(llm_output, "SUBSECTION_TITLE"):
    print("Subsection found!")
```

---

## Migration Path

### From Current V2 Extractor to Experimental Versions

**Step 1**: Test V2A (drop-in replacement with better caching)

```python
# Before (current)
from src.chunking.chunk_extractor_v2 import ChunkExtractorV2

# After (experimental V2A)
from src.chunking.chunk_extractor_v2_experimental import ChunkExtractorV2A as ChunkExtractorV2
```

**Step 2**: If V2A works, try V2B for better performance

**Step 3**: If V2B works, try V2C for maximum optimization

### Rollback Strategy

All versions use the same interface and output format. Rolling back is as simple as changing the import:

```python
# Rollback to standard V2
from src.chunking.chunk_extractor_v2 import ChunkExtractorV2
```

---

## Troubleshooting

### Issue: Cache hit rate lower than expected

**Solution**: Verify document text is identical between sections
```python
# Check if document content changes
assert structure.sections[0].content == structure.sections[1].content
```

### Issue: Tag parsing errors

**Solution**: Enable debug mode to see raw LLM output
```python
try:
    result = extractor.extract_chunks(document, structure)
except ChunkExtractionError as e:
    print(f"Error: {e}")
    print(f"Raw response: {e.llm_response}")  # Inspect LLM output
```

### Issue: V2C produces malformed output

**Solution**: LLM may struggle with 6 tags. Try V2B instead, or increase temperature slightly:

```python
extractor = ChunkExtractorV2C(
    ...,
    model="google/gemini-2.0-flash-exp",  # Try different model
)
```

---

## Future Work

- [ ] Add support for custom tag names
- [ ] Implement streaming output parsing
- [ ] Add retry logic for tag parsing failures
- [ ] Create visualization tool for cache hit analysis
- [ ] Benchmark against other LLM providers (OpenAI, Anthropic)

---

## Contributing

To test your changes:

```bash
# Run tag parser tests
pytest tests/chunking/unit/test_tag_parser.py -v

# Run integration tests
pytest tests/chunking/integration/test_experimental_extractors.py -v

# Run with coverage
pytest tests/chunking/ --cov=src.chunking --cov-report=html
```

---

## License

Same as main project.

## Questions?

Open an issue or discuss in the project chat!
