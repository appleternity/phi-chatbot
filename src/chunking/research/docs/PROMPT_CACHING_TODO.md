# Prompt Caching Implementation TODO

**Status**: 90% complete - Final step needed to enable actual prompt caching
**Priority**: High - Will unlock 80-90% cost savings
**Estimated Time**: 2-3 hours

---

## 🎯 Mission

Enable **actual prompt caching** for Anthropic and Gemini models to achieve 80-90% cost reduction on multi-section documents.

**Current Problem**: Our V3 experimental extractors have document-first prompt structure (correct for caching), but don't use the required `cache_control` breakpoints, so **caching isn't actually happening**.

---

## 📚 Background Context

### What We Built (V3 Experimental Architecture)

Created `chunk_extractor_v3_experimental.py` with two versions:
- **V3A** (Conservative): 2 LLM calls per section - extract → prefix
- **V3B** (Aggressive): 1 LLM call per section - extract+prefix merged

**Key Innovation**: Eliminated redundant metadata generation by deriving metadata from Phase 1 structure analysis (no LLM call needed!).

### Why Prompt Caching Matters

**Without caching** (10-section document):
- Section 1: 5500 tokens @ full cost
- Section 2: 5500 tokens @ full cost
- ...
- Section 10: 5500 tokens @ full cost
- **Total: 55,000 tokens @ full cost**

**With caching** (10-section document):
- Section 1: 5500 tokens @ full cost + cache write overhead
- Section 2: 500 tokens @ full cost + 5000 tokens @ 0.1x cost (Anthropic) or 0.25x (Gemini)
- ...
- Section 10: 500 tokens @ full cost + 5000 tokens @ 0.1x cost
- **Total savings: ~80-90% on document tokens!**

---

## 🔍 The Problem

### Current Implementation (Doesn't Trigger Caching)

```python
# ❌ Single string content - no cache_control possible
response = self.llm_client.chat_completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt_string}],
    temperature=0.3
)
```

### What's Required (Both Anthropic & Gemini via OpenRouter)

```python
# ✅ Multipart content with cache_control breakpoint
response = self.llm_client.chat_completion(
    model=self.model,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"DOCUMENT TEXT:\n{document_text}",
                "cache_control": {"type": "ephemeral"}  # ← Cache breakpoint!
            },
            {
                "type": "text",
                "text": f"\n---\n\n{instructions_with_params}"
            }
        ]
    }],
    temperature=0.3,
    extra_body={"usage": {"include": True}}  # ← Enable cache metrics
)
```

---

## 🛠️ Implementation Plan

### Step 1: Create Message Builder Helper

Add this method to both `ChunkExtractorV3A` and `ChunkExtractorV3B`:

```python
def _build_cached_message(
    self,
    document_text: str,
    instructions: str
) -> List[Dict[str, Any]]:
    """
    Build multipart message with cache_control for OpenRouter.

    Args:
        document_text: Full document content (STATIC - will be cached)
        instructions: Operation instructions with params (DYNAMIC - not cached)

    Returns:
        Message list with cache_control breakpoint

    Structure:
        Part 1: Document text with cache_control (CACHED after first call)
        Part 2: Instructions (NOT CACHED, changes per section)
    """
    return [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"DOCUMENT TEXT:\n{document_text}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"\n---\n\n{instructions}"
            }
        ]
    }]
```

---

### Step 2: Split Prompts into Instruction Templates

**Remove these monolithic prompts**:
- `TEXT_EXTRACTION_PROMPT_V3`
- `CONTEXTUAL_PREFIX_PROMPT_V3`
- `EXTRACT_AND_PREFIX_MERGED_PROMPT_V3`

**Replace with instruction-only templates** (no document text embedded):

```python
# Extraction instructions (no document text)
EXTRACTION_INSTRUCTIONS_V3 = """You are extracting a specific section of text from the above document for chunking purposes.

Your task: Extract and format the complete text for the section described below. Output EXACTLY as it appears in the document, preserving all content but with clean formatting.

TARGET SECTION:
- Title: {section_title}
- Summary: {section_summary}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"
- Section ENDS near: "{end_words}"

Note: These boundary hints are approximate guides, not exact quotes. The actual text may have minor variations in capitalization, punctuation, or word order. Use them to locate the general boundaries, then extract the complete section content.

EXTRACTION RULES:
1. Output the COMPLETE text for this section - do NOT summarize or paraphrase
2. Include ALL content from this section
3. Use the boundary hints to identify where this section starts and ends:
   - Find text that closely matches the start_words (allowing for minor variations)
   - Find text that closely matches the end_words (allowing for minor variations)
   - Extract everything between these boundaries
4. You MAY clean up formatting:
   - Normalize whitespace and line breaks
   - Fix obvious typos
   - Add markdown structure (headers, lists) if helpful
5. Do NOT:
   - Summarize or condense content
   - Skip any content from the target section
   - Add content not in the original section
   - Include content from other sections (respect the boundaries!)
6. Output ONLY the extracted text, no explanations or preamble

OUTPUT (extracted section text):"""

# Prefix instructions (no document text)
PREFIX_INSTRUCTIONS_V3 = """You are generating a contextual prefix for a document chunk to improve RAG retrieval.

Your task: Write a concise sentence that situates this chunk within the overall document.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}
- Subsections: {subsection_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Plain text (single sentence, 20-50 words, no special formatting)

EXAMPLE OUTPUT:
This chunk is from the Introduction chapter, Section "Why Test?", discussing the importance of software testing in preventing bugs and improving code quality.

IMPORTANT RULES:
1. Output ONLY the contextual sentence, no explanations
2. Start with "This chunk is from..."
3. Include chapter, section, and main topic
4. Be specific but concise (20-50 words)
5. Do not include the full chunk text in the prefix

OUTPUT (contextual prefix):"""

# Merged instructions for V3B (no document text)
MERGED_INSTRUCTIONS_V3 = """You are processing a document chunk for a RAG pipeline. Your task: extract the section text AND create a contextual prefix - both in one operation.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Target Section: {section_title}
- Section Summary: {section_summary}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"
- Section ENDS near: "{end_words}"

Note: These boundary hints are approximate guides, not exact quotes. Use them to locate the general boundaries, then extract the complete section content.

OUTPUT FORMAT: Tagged structure with exactly 2 fields:

[CHUNK_TEXT]
The complete extracted text for the target section goes here.
Extract EXACTLY as it appears in the document, preserving all content.
Include ALL content from this section.
You MAY clean up formatting (normalize whitespace, fix typos, add markdown structure).
Do NOT summarize, condense, or skip any content.
[/CHUNK_TEXT]

[CONTEXTUAL_PREFIX]Concise sentence situating chunk in document (20-50 words, starts with "This chunk is from...")[/CONTEXTUAL_PREFIX]

IMPORTANT RULES:
1. Use EXACT tag names as shown above (case-sensitive)
2. Include both opening [TAG] and closing [/TAG] for each field
3. CHUNK_TEXT must be complete - do NOT summarize or truncate
4. Prefix must start with "This chunk is from..."
5. Output ALL 2 fields in the order shown
6. Output ONLY the tagged structure, no explanations or preambles

OUTPUT (tagged extraction + prefix):"""
```

---

### Step 3: Update LLM Call Sites (3 locations)

#### Location 1: `_extract_section_text()` (Both V3A & V3B)

**Find this**:
```python
prompt = TEXT_EXTRACTION_PROMPT_V3.format(...)
response = self.llm_client.chat_completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)
```

**Replace with**:
```python
# Build instructions with dynamic params
instructions = EXTRACTION_INSTRUCTIONS_V3.format(
    section_title=section_title,
    section_summary=section_summary,
    max_tokens=max_tokens,
    start_words=start_words,
    end_words=end_words
)

# Build cached message (document + instructions)
messages = self._build_cached_message(document.content, instructions)

# Make LLM call with cache metrics enabled
response = self.llm_client.chat_completion(
    model=self.model,
    messages=messages,
    temperature=0.3,
    extra_body={"usage": {"include": True}}  # Enable cache metrics
)
```

#### Location 2: `_generate_contextual_prefix()` (V3A only)

**Find this**:
```python
prompt = CONTEXTUAL_PREFIX_PROMPT_V3.format(...)
response = self.llm_client.chat_completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)
```

**Replace with**:
```python
# Build instructions
instructions = PREFIX_INSTRUCTIONS_V3.format(
    document_id=document_id,
    chapter_title=chapter_title,
    section_title=section_title,
    subsection_title=subsection_display,
    chunk_text=chunk_text
)

# Build cached message
messages = self._build_cached_message(document_text, instructions)

# Make LLM call
response = self.llm_client.chat_completion(
    model=self.model,
    messages=messages,
    temperature=0.3,
    extra_body={"usage": {"include": True}}
)
```

#### Location 3: `_extract_and_generate_prefix()` (V3B only)

**Find this**:
```python
prompt = EXTRACT_AND_PREFIX_MERGED_PROMPT_V3.format(...)
response = self.llm_client.chat_completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)
```

**Replace with**:
```python
# Build instructions
instructions = MERGED_INSTRUCTIONS_V3.format(
    document_id=document.document_id,
    chapter_title=chapter_title,
    section_title=section_title,
    section_summary=section_summary,
    max_tokens=max_tokens,
    start_words=start_words,
    end_words=end_words
)

# Build cached message
messages = self._build_cached_message(document.content, instructions)

# Make LLM call
response = self.llm_client.chat_completion(
    model=self.model,
    messages=messages,
    temperature=0.3,
    extra_body={"usage": {"include": True}}
)
```

---

### Step 4: Parse Cache Metrics from Response

In **all 3 locations**, after getting the response, add cache metrics parsing:

```python
# Extract standard usage
tokens_consumed = response.get("usage", {}).get("total_tokens", 0)

# Extract cache metrics (OpenRouter specific)
usage = response.get("usage", {})
cache_discount = response.get("cache_discount", 0)
cache_read_tokens = usage.get("cache_read_input_tokens", 0)
cache_write_tokens = usage.get("cache_creation_input_tokens", 0)

# Determine cache status
if cache_read_tokens > 0:
    cache_status = "hit"
elif cache_write_tokens > 0:
    cache_status = "write"
else:
    cache_status = "miss"
```

---

### Step 5: Return Cache Metrics

Update return dicts in all 3 locations:

```python
return {
    "extracted_text": extracted_text,  # or "prefix": prefix
    "tokens_consumed": tokens_consumed,
    "cache_discount": cache_discount,
    "cache_read_tokens": cache_read_tokens,
    "cache_write_tokens": cache_write_tokens,
    "cache_status": cache_status,
    "llm_response": extracted_text,  # or response_text
    "llm_response_cached": cache_read_tokens > 0
}
```

And update where these are collected:

```python
llm_responses[section.title] = {
    "extraction": {
        "response": extraction_result.get("llm_response"),
        "cached": extraction_result.get("llm_response_cached", False),
        "cache_discount": extraction_result.get("cache_discount", 0),
        "cache_read_tokens": extraction_result.get("cache_read_tokens", 0),
        "cache_write_tokens": extraction_result.get("cache_write_tokens", 0),
        "cache_status": extraction_result.get("cache_status", "unknown")
    },
    # ... similar for "prefix" (V3A) or merge into "merged" (V3B)
}
```

---

## 🧪 Testing & Validation

### How to Test

```python
from src.chunking.chunk_extractor_v3_experimental import ChunkExtractorV3A

# Initialize
extractor = ChunkExtractorV3A(
    llm_client=llm_client,
    token_counter=token_counter,
    metadata_validator=metadata_validator,
    model="anthropic/claude-3.5-sonnet",  # or google/gemini-2.0-flash-exp
    cache_store=cache_store
)

# Process document with multiple sections
result = extractor.extract_chunks(document, structure)

# Inspect cache performance
for section_title, ops in result['llm_responses'].items():
    for op_name, metrics in ops.items():
        print(f"{section_title} - {op_name}:")
        print(f"  Status: {metrics['cache_status']}")
        print(f"  Read tokens: {metrics['cache_read_tokens']}")
        print(f"  Write tokens: {metrics['cache_write_tokens']}")
        print(f"  Discount: ${metrics['cache_discount']:.4f}")
```

### Expected Results (10-section document)

**Section 1** (cache write):
```
Status: write
Read tokens: 0
Write tokens: 5000
Discount: -0.05 (overhead for Anthropic)
```

**Sections 2-10** (cache hit):
```
Status: hit
Read tokens: 5000
Write tokens: 0
Discount: +0.45 (savings! 90% off for Anthropic)
```

---

## 📊 Cache Metrics Reference

### Anthropic via OpenRouter

| Metric | Cache Write | Cache Hit |
|--------|-------------|-----------|
| `cache_creation_input_tokens` | >0 (e.g., 5000) | 0 |
| `cache_read_input_tokens` | 0 | >0 (e.g., 5000) |
| `cache_discount` | Negative (overhead, 1.25x cost) | Positive (savings, 0.9x savings) |

**Cost Formula**:
- Write: base_cost × 1.25
- Read: base_cost × 0.1

### Gemini via OpenRouter

| Metric | Cache Write | Cache Hit |
|--------|-------------|-----------|
| `cache_creation_input_tokens` | >0 | 0 |
| `cache_read_input_tokens` | 0 | >0 |
| `cache_discount` | Varies | Positive (0.75x savings) |

**Cost Formula**:
- Write: base_cost + (storage × 5min/60min)
- Read: base_cost × 0.25

### Cache TTL

- **Anthropic**: 5 minutes (doesn't refresh)
- **Gemini**: 3-5 minutes average (varies)

**Important**: Cache doesn't refresh! If processing takes >5 minutes, later sections might miss cache.

---

## 🚨 Common Pitfalls

### 1. ❌ Forgetting `extra_body` Parameter

```python
# Wrong - no cache metrics returned
response = self.llm_client.chat_completion(
    model=self.model,
    messages=messages
)

# Right - cache metrics included
response = self.llm_client.chat_completion(
    model=self.model,
    messages=messages,
    extra_body={"usage": {"include": True}}
)
```

### 2. ❌ Embedding Document in Instructions Template

```python
# Wrong - document text in both places!
instructions = f"DOCUMENT:\n{document_text}\n\n{params}"
messages = self._build_cached_message(document_text, instructions)

# Right - document only in cached part
instructions = f"{params}"
messages = self._build_cached_message(document_text, instructions)
```

### 3. ❌ Not Checking Cache Status

Cache might not work if:
- Model doesn't support caching
- Document too small (<1024 tokens for Anthropic, <1028/2048 for Gemini)
- OpenRouter API issues

**Solution**: Always check `cache_status` in results!

---

## 📁 Files to Modify

**Primary**:
- `src/chunking/chunk_extractor_v3_experimental.py` (only file needing changes)

**Optional** (update after verification):
- `src/chunking/V3_EXPERIMENTAL_README.md` (add cache metrics examples)

---

## 🎯 Success Criteria

After implementation:

1. ✅ First section shows `cache_status: "write"`
2. ✅ Subsequent sections show `cache_status: "hit"`
3. ✅ `cache_read_tokens > 0` for sections 2+
4. ✅ `cache_discount > 0` for sections 2+ (cost savings!)
5. ✅ Real cost reduction visible in OpenRouter dashboard

---

## 📖 Reference Links

- **OpenRouter Prompt Caching Docs**: https://openrouter.ai/docs/features/prompt-caching
- **Anthropic Caching**: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- **Gemini Caching**: https://ai.google.dev/gemini-api/docs/caching
- **OpenRouter Usage API**: https://openrouter.ai/docs/api-reference/generation

---

## 🔄 Context Preservation

### What We've Built So Far

1. **Tag Parser** (`tag_parser.py`): Robust XML-style tag parsing for dirty text
2. **V3 Experimental Extractors** (`chunk_extractor_v3_experimental.py`):
   - V3A: 2 calls (extract, prefix) + derived metadata
   - V3B: 1 call (extract+prefix) + derived metadata
3. **Metadata Derivation** (`derive_metadata_from_structure()`): Eliminates redundant LLM call
4. **Documentation** (`V3_EXPERIMENTAL_README.md`): Usage guide and migration path

### What's Missing

**Only remaining task**: Implement actual prompt caching with `cache_control` breakpoints.

Once this is done, the V3 experimental architecture will be **production-ready** with:
- 33-66% fewer LLM calls (vs V2)
- 80-90% cost reduction through caching
- Perfect metadata consistency (from Phase 1)
- Robust parsing (tag-based)

---

## 💡 Final Notes

- **Fail fast**: No complex error handling needed per user request
- **Document is long**: No need to validate minimum token requirements
- **Keep it simple**: Focus on getting cache metrics working
- **Observable**: Return all metrics for user inspection

**Estimated implementation time**: 2-3 hours
**Expected cost savings**: 80-90% on multi-section documents
**Production readiness**: High (after this final step)

---

Good luck! 🚀
