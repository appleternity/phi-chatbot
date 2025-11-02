# Quick Start: V3 Experimental Extractors + Prompt Caching

**⚡ TL;DR**: V3 extractors are 90% done. Need to add `cache_control` breakpoints for 80-90% cost savings.

---

## 📂 Key Files

| File | Purpose | Status |
|------|---------|--------|
| `PROMPT_CACHING_TODO.md` | **READ THIS FIRST** - Complete implementation guide | ✅ Ready |
| `chunk_extractor_v3_experimental.py` | V3A & V3B implementations | ⚠️ Missing cache_control |
| `tag_parser.py` | Tag parsing utilities | ✅ Complete |
| `V3_EXPERIMENTAL_README.md` | Usage documentation | ✅ Complete |
| `SESSION_SUMMARY.md` | What we built and why | ✅ Complete |

---

## 🎯 What V3 Offers

### V3A (Conservative)
```python
from src.chunking.chunk_extractor_v3_experimental import ChunkExtractorV3A

extractor = ChunkExtractorV3A(llm_client, token_counter, metadata_validator, cache_store)
result = extractor.extract_chunks(document, structure)
```

- **2 LLM calls**: extract → prefix
- **Metadata**: derived from Phase 1 (no LLM call!)
- **Best for**: Production, debugging

### V3B (Aggressive)
```python
from src.chunking.chunk_extractor_v3_experimental import ChunkExtractorV3B

extractor = ChunkExtractorV3B(llm_client, token_counter, metadata_validator, cache_store)
result = extractor.extract_chunks(document, structure)
```

- **1 LLM call**: extract + prefix merged
- **Metadata**: derived from Phase 1 (no LLM call!)
- **Best for**: Maximum efficiency

---

## ⚠️ Critical Missing Piece

### The Problem
```python
# ❌ Current: Single string (no caching)
messages = [{"role": "user", "content": full_prompt}]
```

### The Solution
```python
# ✅ Required: Multipart with cache_control
messages = [{
    "role": "user",
    "content": [
        {
            "type": "text",
            "text": f"DOCUMENT TEXT:\n{document_text}",
            "cache_control": {"type": "ephemeral"}  # ← ADD THIS!
        },
        {
            "type": "text",
            "text": f"\n---\n\n{instructions}"
        }
    ]
}]
```

### Where to Fix
1. `_extract_section_text()` - Line ~410
2. `_generate_contextual_prefix()` - Line ~460 (V3A only)
3. `_extract_and_generate_prefix()` - Line ~620 (V3B only)

---

## 📋 Implementation Checklist

- [ ] Read `PROMPT_CACHING_TODO.md` (5 min)
- [ ] Add `_build_cached_message()` helper
- [ ] Split prompts into instruction templates
- [ ] Update 3 LLM call sites with multipart messages
- [ ] Add `extra_body={"usage": {"include": True}}` to calls
- [ ] Parse cache metrics from response
- [ ] Test with real document
- [ ] Verify `cache_status: "hit"` for sections 2+

**Time**: 2-3 hours

---

## 🧪 How to Test

```python
# Run extractor
result = extractor.extract_chunks(document, structure)

# Check cache performance
for section, ops in result['llm_responses'].items():
    for op_name, metrics in ops.items():
        print(f"{section} - {op_name}: {metrics['cache_status']}")
        if metrics['cache_read_tokens'] > 0:
            print(f"  ✅ Cached {metrics['cache_read_tokens']} tokens!")
```

### Expected Results
```
Section 1 - extraction: write
Section 1 - prefix: write

Section 2 - extraction: hit
Section 2 - prefix: hit
  ✅ Cached 5000 tokens!

Section 3 - extraction: hit
Section 3 - prefix: hit
  ✅ Cached 5000 tokens!

...
```

---

## 💰 Expected Savings

### 10-Section Document

**Before (V2)**:
- 30 LLM calls
- ~$15
- ~30 minutes

**After (V3B + Caching)**:
- 10 LLM calls (-66%)
- ~$3 (-80%)
- ~8 minutes (-73%)

---

## 🆘 Need Help?

1. **Implementation details** → `PROMPT_CACHING_TODO.md`
2. **Design rationale** → `SESSION_SUMMARY.md`
3. **Usage examples** → `V3_EXPERIMENTAL_README.md`
4. **OpenRouter docs** → https://openrouter.ai/docs/features/prompt-caching

---

## 🎓 Key Concepts

### Cache Control Breakpoint
- Marks where caching boundary is
- Content before: cached (static)
- Content after: not cached (dynamic)

### Multipart Message
- Required format for cache_control
- Each part is dict with "type" and "text"
- Add "cache_control" to part you want cached

### Cache Metrics
- `cache_read_input_tokens > 0`: Cache hit!
- `cache_creation_input_tokens > 0`: Cache write
- `cache_discount > 0`: Cost savings
- `cache_discount < 0`: Write overhead

---

## ✅ Done When...

- [ ] Section 1 shows `cache_status: "write"`
- [ ] Sections 2+ show `cache_status: "hit"`
- [ ] `cache_read_tokens > 0` for cached sections
- [ ] Real cost reduction visible in OpenRouter

---

**Ready to implement? Start with `PROMPT_CACHING_TODO.md` →**
