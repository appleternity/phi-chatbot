# Document Chunking System Redesign Plan

**Date**: 2025-10-30
**Status**: Implementation approved, ready to execute
**Context**: User identified fundamental architectural flaws after initial implementation

---

## Executive Summary

The initial implementation is fundamentally flawed because it asks LLMs to output exact character positions (start_char, end_char), which LLMs cannot reliably do. This document outlines a complete architectural redesign that eliminates position-based processing in favor of text extraction.

**Key Changes**:
1. Remove cache TTL mechanism, add --redo flag for user control
2. Complete CLI pipeline integration (currently has TODO blocking usage)
3. Redesign from 3-phase to 2-phase architecture (eliminate position reliance)

---

## Problem Analysis

### Critical Issue: LLM Character Position Unreliability

**Current Broken Flow**:
```
Phase 1: Document → LLM → Structure (title, level, START_CHAR, END_CHAR, parent)
Phase 2: Document + Structure → LLM → Boundaries (POSITION, type, justification)
Phase 3: Document[positions] → Extract text → LLM → Metadata
```

**Why This Fails**:
- LLMs think in tokens, not characters
- Character counting requires arithmetic during generation (not how LLMs work)
- For long documents, LLMs can't "see" exact positions accurately
- Results in: wrong positions → wrong text extraction → garbage chunks

**User's Key Insight** (from TODO notes):
> "I don't think LLM can handle start_char and end_char accurately enough. We should identify title, level, parent_title, and a quick summary instead... ask it to generate the full text in the second phase. And that's why we need a text alignment to check that the texts are not randomly modified."

### Secondary Issues

**Issue 2: Cache TTL is Unnecessary**
- Content-based caching (SHA256 hash) already ensures validity
- 24-hour expiration causes unnecessary reprocessing for unchanged documents
- No user control to force re-processing when desired

**Issue 3: CLI is Non-Functional**
- Critical TODO at line 168 in cli.py blocks all usage
- ChunkingPipeline instantiation commented out
- No JSONL output writing implemented

**Issue 4: Phase 2 & 3 Overlap**
- BoundaryDetector asks LLM for positions → unreliable
- DocumentSegmenter depends on those positions → garbage in, garbage out
- DocumentSegmenter already has LLM context → should extract text directly

---

## Redesigned Architecture

### New 2-Phase Flow

```
Phase 1: StructureAnalyzer (Good LLM - GPT-4o/Claude)
  Input: Full document text
  Process: Identify semantic segments ≤ max_chunk_tokens
  Output: List of {title, level, parent, summary} - NO POSITIONS
  LLM Prompt: "Segment this document into meaningful chunks ≤1000 tokens"

Phase 2: ChunkExtractor (Smaller LLM - Gemini Flash)
  Input: Full document + segment metadata from Phase 1
  Process: For each segment {title, summary}:
    - Prompt: "Extract and format the text for section titled '{title}' with summary '{summary}'"
    - LLM outputs FULL TEXT (not positions)
    - Generate metadata (chapter, section, subsection, summary)
    - Generate contextual prefix
    - Combine: prefix + extracted_text
  Output: List of Chunks with full text

Phase 3: TextAligner (Validation - No LLM)
  Input: Original document + all chunks
  Process: Use difflib.SequenceMatcher to verify coverage
  Validate: 99%+ of original text covered by chunks
  Fail: If coverage < 99% → TextCoverageError
```

**Key Philosophy**: Ask LLMs to do what they're good at (text understanding and generation), avoid what they're bad at (exact numeric positions).

---

## File-by-File Change Specification

### 1. cache_store.py - Remove TTL Mechanism

**Current State**:
- Has TTL with default 86400 seconds (24 hours)
- Stores _cache_metadata with cached_at, expires_at, ttl
- get() checks expiration and deletes expired entries
- cleanup_expired() method removes old entries

**Required Changes**:
- Remove default_ttl parameter from __init__()
- Remove all TTL-related code from get()
- Remove ttl parameter from set()
- Remove _cache_metadata entirely - store pure data
- Remove cleanup_expired() method
- Keep get_stats() but remove expired_count
- Simplify to pure content-hash based key-value store

**Rationale**: Content hash (SHA256) already ensures cache validity. Cache is valid until document content changes.

---

### 2. cli.py - Complete Integration & Add --redo

**Current State**:
- Lines 168+: Essential TODO blocking all functionality
- ChunkingPipeline instantiation commented out
- No result processing or JSONL output

**Required Changes**:

**Part A: Add --redo flag**
```
In process() command parameters, add:
redo: Annotated[bool, typer.Option(
    "--redo",
    help="Bypass cache and force reprocessing"
)] = False
```

**Part B: Uncomment and complete pipeline integration**
- Uncomment ChunkingPipeline instantiation
- Pass redo flag as parameter to pipeline
- Call process_document() or process_folder() based on input type
- Write results as JSONL: one Chunk per line in output file

**Part C: JSONL output writer**
```
For single file:
  output_file = output_dir / f"{doc_id}_chunks.jsonl"

For folder:
  output_file = output_dir / f"{folder_name}_chunks_{timestamp}.jsonl"

For each chunk:
  output_file.write_text(chunk.json() + "\n", append=True)
```

**Part D: Error handling**
- Catch ChunkingError subclasses
- Exit with code 1 for processing errors
- Exit with code 2 for validation errors
- Display rich error messages with context

---

### 3. structure_analyzer.py - Remove Position Output

**Current State**:
- TSV format: title | level | start_char | end_char | parent_title (5 columns)
- Asks LLM to determine character positions
- Creates Section objects with start_char, end_char

**Required Changes**:

**Part A: Update TSV prompt template**
```
OLD (5 columns): title | level | start_char | end_char | parent_title
NEW (4 columns): title | level | parent_title | summary

Example output:
Introduction to Testing	1	ROOT	Overview of software testing fundamentals
Why Test?	2	Introduction to Testing	Explains benefits of early bug detection
Types of Testing	2	Introduction to Testing	Covers unit, integration, and e2e testing
```

**Part B: Update prompt instructions**
- Focus: "Segment document into meaningful chunks ≤ max_chunk_tokens"
- Remove: Any mention of character positions or boundaries
- Add: "Each segment should be semantically coherent and self-contained"
- Add: "Provide a 10-50 word summary for each segment"
- Emphasize: Segments can be nested (subsections within sections)

**Part C: Update parse_structure_response()**
- Change from 5-column to 4-column TSV parsing
- Remove start_char, end_char extraction
- Add summary field extraction
- Validation: Check for 4 columns, not 5

**Part D: Add max_chunk_tokens parameter**
- Add to __init__() and analyze() method signatures
- Pass to LLM in prompt context
- Default: 1000 tokens

**Part E: Add redo parameter**
- Add to analyze() signature: redo: bool = False
- If redo=True, skip cache lookup (don't call cache_store.get())
- Still cache result after generation (call cache_store.set())

---

### 4. boundary_detector.py - DELETE FILE

**Current State**: 350-line file implementing Phase 2 boundary detection

**Required Action**: Delete entire file

**Rationale**:
- This component asks LLMs for character positions → fundamentally flawed
- Its functionality is replaced by ChunkExtractor's text extraction approach
- Keeping it would be confusing and invite future bugs

---

### 5. document_segmenter.py → chunk_extractor.py - Major Redesign

**Current State**:
- Name: DocumentSegmenter in document_segmenter.py
- Takes: Document + Structure + Boundaries (all with positions)
- Uses: Character positions to slice document.content[start:end]
- Asks LLM: Generate metadata and prefix for extracted text

**Required Changes**:

**Part A: Rename file and class**
- File: document_segmenter.py → chunk_extractor.py
- Class: DocumentSegmenter → ChunkExtractor

**Part B: Change method signature**
```
OLD: segment(document, structure, boundaries) → List[Chunk]
NEW: extract_chunks(document, structure) → List[Chunk]
```
(No boundaries parameter - we don't have positions anymore)

**Part C: Redesign extraction logic**

For each section in structure.sections:
1. **Format extraction prompt**:
   ```
   Input:
   - Full document text: {document.content}
   - Target section title: {section.title}
   - Target section summary: {section.summary}
   - Maximum tokens: {max_chunk_tokens}

   Instruction:
   "Extract and format the complete text for the section titled '{section.title}'
   which covers: {section.summary}.

   Output the text exactly as it appears in the document, but you may:
   - Clean up formatting (normalize whitespace, fix obvious typos)
   - Add markdown structure (headers, lists) if helpful
   - Ensure the text is coherent and complete

   Do NOT:
   - Summarize or paraphrase
   - Skip any content
   - Add content not in the original

   Output just the extracted text, nothing else."
   ```

2. **Call LLM to extract text**:
   - Model: self.model (default: google/gemini-2.0-flash-exp)
   - Parse response: Get content from LLM response
   - Store as: extracted_text

3. **Generate metadata** (separate LLM call):
   - Use existing metadata generation prompt (TSV format)
   - Input: extracted_text + section.title
   - Output: chapter_title, section_title, subsection_title, summary

4. **Generate contextual prefix** (separate LLM call):
   - Use existing contextual prefix prompt
   - Input: extracted_text + metadata
   - Output: prefix string

5. **Create Chunk object**:
   - chunk_text: prefix + extracted_text
   - original_text: extracted_text (without prefix)
   - contextual_prefix: prefix
   - metadata: ChunkMetadata from step 3
   - token_count: count_tokens(chunk_text)
   - Validate: token_count ≤ max_chunk_tokens

**Part D: Remove position-based logic**
- Delete all code that uses boundary.position
- Delete character span calculation
- Delete boundary pair iteration

---

### 6. models.py - Remove Position Fields and Models

**Required Changes**:

**Part A: Update Section model**
```
Remove fields:
- start_char: int
- end_char: int

Add field:
- summary: str = Field(..., min_length=10, max_length=200)

Remove validator:
- end_after_start (no longer applicable)
```

**Part B: Delete models entirely**
```
Remove:
- class BoundaryType(str, Enum)
- class SegmentBoundary(BaseModel)
```

**Part C: Update Structure model**
```
Remove validator: sections_non_overlapping
(No positions to check for overlaps)

Optional: Add new validator to ensure sections form valid hierarchy
(Check parent references are valid)
```

**Part D: Update Chunk model**
```
Remove field:
- character_span: Tuple[int, int]

Rationale: We don't track positions anymore
```

---

### 7. chunking_pipeline.py - Simplify to 2-Phase

**Current State**:
- Phase 1: StructureAnalyzer
- Phase 2: BoundaryDetector
- Phase 3: DocumentSegmenter
- Tracks tokens for all 3 phases

**Required Changes**:

**Part A: Remove BoundaryDetector integration**
- Delete import: from .boundary_detector import BoundaryDetector
- Remove from __init__: boundary_model parameter
- Remove: self.boundary_detector instantiation

**Part B: Update to ChunkExtractor**
- Change import: from .chunk_extractor import ChunkExtractor
- Update __init__: Keep segmentation_model parameter
- Instantiate: self.chunk_extractor = ChunkExtractor(...)

**Part C: Update process_document() method**
```
OLD flow:
1. structure = structure_analyzer.analyze(document)
2. boundaries = boundary_detector.detect_boundaries(document, structure)
3. chunks = document_segmenter.segment(document, structure, boundaries)
4. Validate coverage
5. Validate metadata

NEW flow:
1. structure = structure_analyzer.analyze(document, redo=redo_flag)
2. chunks = chunk_extractor.extract_chunks(document, structure)
3. Validate coverage with text_aligner
4. Validate metadata
```

**Part D: Update token tracking**
```
OLD: phase_1_tokens, phase_2_tokens, phase_3_tokens
NEW: phase_1_tokens (structure), phase_2_tokens (extraction)

Update ProcessingReport:
- Keep phase_1_tokens, phase_2_tokens
- Set phase_3_tokens = 0 (or remove field)
```

**Part E: Add redo parameter**
- Add to process_document() signature: redo: bool = False
- Pass to structure_analyzer.analyze(document, redo=redo)

---

### 8. text_aligner.py - No Changes Required

**Status**: This component is already correct!

**Current Functionality**:
- Takes original document text
- Takes list of chunks
- Uses difflib.SequenceMatcher to calculate coverage ratio
- Identifies missing segments
- Raises TextCoverageError if < 99%

**Why It Still Works**:
- Doesn't depend on positions
- Works with full text comparison
- Validates that chunk extraction captured all content

---

### 9. Update Test Files

**tests/chunking/fixtures/llm_responses.py**:
- Update MOCK_STRUCTURE_TSV to 4 columns (remove start_char, end_char)
- Remove MOCK_BOUNDARIES_TSV (no longer used)
- Remove MOCK_BOUNDARIES_RESPONSE
- Add MOCK_TEXT_EXTRACTION responses for ChunkExtractor

**tests/chunking/conftest.py**:
- Remove mock_boundaries_response fixture
- Add mock_extraction_response fixture

**tests/chunking/contract/test_components.py**:
- Remove all BoundaryDetector tests
- Update StructureAnalyzer tests for 4-column TSV
- Update DocumentSegmenter tests for ChunkExtractor API
- Test new extraction-based approach

**tests/chunking/integration/test_end_to_end_chunking.py**:
- Update to expect 2-phase pipeline
- Update mock LLM responses
- Test extraction instead of position-based slicing

**tests/chunking/unit/test_utilities.py**:
- TextAligner tests: No changes (still valid)
- MetadataValidator tests: No changes (still valid)
- TokenCounter tests: No changes (still valid)

---

## Implementation Order

**Critical Path** (must be done in order):

1. **models.py** - Remove position fields first (foundation change)
2. **cache_store.py** - Remove TTL (simple, independent)
3. **structure_analyzer.py** - Update to 4-column TSV and add redo
4. **document_segmenter.py → chunk_extractor.py** - Rename and redesign
5. **boundary_detector.py** - DELETE
6. **chunking_pipeline.py** - Update to 2-phase architecture
7. **cli.py** - Complete integration and add --redo
8. **Test files** - Update mocks and expectations

**Parallelizable** (can be done independently):
- Steps 2 and 3 can be parallel
- Test updates can happen during component updates

---

## Testing Strategy

### Unit Tests
1. **StructureAnalyzer**: Test 4-column TSV parsing, summary extraction
2. **ChunkExtractor**: Test text extraction from document + metadata
3. **Cache**: Test redo flag bypasses cache, content changes invalidate

### Integration Tests
1. **2-Phase Pipeline**: Document → Structure → Chunks
2. **Text Coverage**: Verify TextAligner catches missing content
3. **Extraction Accuracy**: LLM extracts correct text for given metadata
4. **redo Flag**: Verify cache bypass works end-to-end

### Validation Tests
1. **Coverage >= 99%**: TextAligner validation works
2. **Metadata Complete**: All chunks have valid metadata
3. **Token Limits**: All chunks ≤ max_chunk_tokens

---

## Edge Cases & Error Handling

### Extraction Failures
- **What if LLM can't find matching text?**
  - Prompt should fail gracefully
  - ChunkExtractor should raise SegmentationError with context
  - Include section title/summary in error message

### Coverage Failures
- **What if extracted text < 99% coverage?**
  - TextAligner raises TextCoverageError (existing behavior)
  - Error message shows missing segments
  - User can inspect which sections failed extraction

### Overlapping Extractions
- **What if LLM extracts overlapping text?**
  - TextAligner will detect duplicates (ratio > 1.0)
  - Should we add explicit duplicate detection?
  - Consider: Add chunk text deduplication step

---

## Performance Considerations

### Token Consumption

**Current (3-phase)**:
- Phase 1: ~5000 tokens (structure analysis)
- Phase 2: ~3000 tokens per oversized section (boundaries)
- Phase 3: ~2000 tokens per chunk (metadata + prefix)

**New (2-phase)**:
- Phase 1: ~5000 tokens (structure analysis, same)
- Phase 2: ~4000 tokens per chunk (text extraction + metadata + prefix)

**Net Change**: Slightly higher per-chunk cost, but eliminates unreliable Phase 2

### Caching Impact
- Phase 1 caching unchanged (structure analysis)
- No TTL = cache persists until content changes
- redo flag allows forced reprocessing when needed
- Should result in fewer unnecessary cache invalidations

---

## Risk Mitigation

### Risk 1: LLM Modifies Text During Extraction
**Mitigation**:
- Prompt emphasizes "exact as-is extraction"
- TextAligner validates 99%+ coverage
- If coverage fails, we know extraction was inaccurate

### Risk 2: LLM Can't Find Matching Content
**Mitigation**:
- Good LLM (GPT-4o) in Phase 1 provides accurate summaries
- Summaries help smaller LLM (Gemini) locate content in Phase 2
- If extraction fails, clear error with section context

### Risk 3: Increased Token Costs
**Mitigation**:
- Use cheaper model for Phase 2 (Gemini Flash vs GPT-4o)
- Caching reduces Phase 1 costs on reprocessing
- Net cost similar but with better reliability

---

## Success Criteria

### Functional Requirements
- ✅ No character positions in any data structures
- ✅ LLMs only do text understanding and generation
- ✅ 99%+ text coverage validated
- ✅ CLI is functional with --redo flag
- ✅ Cache persists until content changes

### Quality Requirements
- ✅ All integration tests pass
- ✅ Coverage validation catches missing content
- ✅ Error messages provide actionable context
- ✅ Documentation updated to reflect new architecture

---

## Open Questions for Next Session

1. **Chunking Strategy**: Should Phase 1 output hierarchical segments or flat list?
   - Current: Hierarchical (sections, subsections, subsubsections)
   - Alternative: Flat list of semantic chunks
   - Trade-off: Hierarchy preserves structure but complicates extraction

2. **Metadata Generation**: Generate in Phase 1 or Phase 2?
   - Current plan: Phase 2 (during extraction)
   - Alternative: Phase 1 (with structure analysis)
   - Trade-off: Phase 1 = 1 LLM call, but no extracted text context

3. **Duplicate Detection**: Add explicit check for overlapping extractions?
   - TextAligner catches this indirectly (ratio > 1.0)
   - Could add: Check for text overlap between chunks
   - Trade-off: Extra computation vs explicit validation

4. **Model Selection**: Should Phase 1 and Phase 2 use different models?
   - Current: Yes (GPT-4o for analysis, Gemini for extraction)
   - Reasoning: Phase 1 needs reasoning, Phase 2 needs cheap generation
   - Alternative: Same model for both (simpler but more expensive)

---

## Files Modified Summary

**Modified (8 files)**:
1. cache_store.py - Remove TTL
2. cli.py - Add --redo, complete integration
3. structure_analyzer.py - 4-column TSV, add redo
4. document_segmenter.py → chunk_extractor.py - Rename & redesign
5. models.py - Remove positions, BoundaryType, SegmentBoundary
6. chunking_pipeline.py - 2-phase architecture
7. text_aligner.py - NO CHANGES (already correct)
8. Test files - Update for new architecture

**Deleted (1 file)**:
1. boundary_detector.py

**Impact**: ~2000 lines modified, ~350 lines deleted, architecture fundamentally sound

---

## Next Steps for Implementation

1. Review this document thoroughly
2. Start with models.py (foundation change)
3. Work through files in implementation order
4. Run tests after each major change
5. Update documentation as you go
6. Test with real documents before declaring complete

**Estimated Time**: 4-6 hours for experienced developer

**Critical Success Factor**: Understand WHY LLMs can't do positions before coding. This redesign only works if you embrace text extraction instead of position tracking.
