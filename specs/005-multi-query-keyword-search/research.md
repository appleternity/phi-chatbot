# Phase 0: Research - Multi-Query Expansion and Keyword Matching

**Feature**: 005-multi-query-keyword-search
**Date**: 2025-11-13
**Status**: Complete (Simplified)

## Research Questions

**Philosophy**: "Simplicity > Complexity | Evidence > Speculation | Working Code > Perfect Design"

---

## 1. PostgreSQL pg_trgm Extension

**Question**: How to add keyword matching alongside vector search?

**Decision**: Use pg_trgm with GIN indexes, similarity threshold 0.3

**Implementation**:
```sql
-- Enable extension (already in PostgreSQL 15+)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create GIN index on chunk_text
CREATE INDEX idx_chunk_text_trgm
ON vector_chunks
USING GIN (chunk_text gin_trgm_ops);

-- Query example
SELECT *, similarity(chunk_text, $1) AS keyword_score
FROM vector_chunks
WHERE chunk_text % $1  -- % is pg_trgm similarity operator
ORDER BY keyword_score DESC
LIMIT $2;
```

**Performance**: ~50ms per query with GIN index (acceptable for <3s total budget)

**Why not alternatives?**:
- Full-text search: No typo tolerance
- ElasticSearch: Infrastructure overkill

---

## 2. Multi-Query Prompt Design

**Question**: How to generate up to 10 diverse queries without complex parsing?

**Decision**: Simple newline-separated output, no key prefixes

**Prompt Structure**:
```
You are a medical search query assistant. Generate up to 10 diverse English queries.

User Query: {user_query}

Requirements:
1. Output ONLY queries, one per line (no numbering, no prefixes)
2. All queries MUST be in English (translate if needed)
3. Generate 2-10 queries depending on complexity:
   - Simple questions: 2-3 queries
   - Comparisons: 5-10 queries (cover both entities)
4. Diversity strategies:
   - Entity decomposition (Drug A, Drug B separately)
   - Aspect coverage (mechanism, side effects, efficacy)
   - Perspective variation (patient, clinician, pharmacist)

Example input: "Compare aripiprazole and risperidone"
Example output:
aripiprazole mechanism of action
risperidone mechanism of action
aripiprazole side effects
risperidone side effects
aripiprazole vs risperidone efficacy
atypical antipsychotics comparison

Generate queries:
```

**Parsing**: Simply `response.split('\n')` and filter empty lines. That's it.

**Why this works**:
- LLM can follow simple instructions
- No complex parsing logic
- No need to validate "key format"
- Fail-safe: If parsing fails, use original query

---

## 3. Parallel Query Execution

**Question**: How to execute multiple queries without overwhelming database?

**Decision**: `asyncio.gather()` with existing connection pool (default 10 connections)

**Implementation**:
```python
# Vector search for all queries (parallel)
vector_tasks = [self._vector_search(q, top_k=15) for q in queries]
vector_results = await asyncio.gather(*vector_tasks)

# Keyword search for all queries (parallel)
if settings.enable_keyword_search:
    keyword_tasks = [self._keyword_search(q, top_k=15) for q in queries]
    keyword_results = await asyncio.gather(*keyword_tasks)
else:
    keyword_results = []
```

**Performance**: 10 queries × 20ms (vector) + 10 queries × 50ms (keyword) = ~500ms total (parallel)

**Safety**: Connection pool automatically queues if >10 concurrent requests

---

## 4. Result Deduplication

**Question**: How to merge vector and keyword results?

**Decision**: Simple chunk_id dict, keep first occurrence

**Implementation**:
```python
def _merge_results(vector_results, keyword_results):
    """Deduplicate by chunk_id, keep first occurrence."""
    seen = {}
    for result in vector_results + keyword_results:
        chunk_id = result['chunk_id']
        if chunk_id not in seen:
            seen[chunk_id] = result
    return list(seen.values())
```

**That's it.** No semantic similarity, no complex scoring logic. Simple dict lookup.

---

## 5. Configuration Strategy

**Question**: What configuration do we need?

**Decision**: ONE environment variable

```bash
# .env
ENABLE_KEYWORD_SEARCH=false  # Default: off (can test vector-only first)
```

**Why not more?**:
- `max_queries=10`: Hardcode in AdvancedRetriever constructor (can change later if needed)
- `similarity_threshold=0.3`: Hardcode in SQL query (tuning is premature optimization)
- No separate retrieval strategy: Just modify AdvancedRetriever

---

## Summary

**What we're actually doing**:
1. ✅ Modify AdvancedRetriever to support up to 10 queries (change prompt + parsing)
2. ✅ Add `_keyword_search()` method using pg_trgm
3. ✅ Merge vector + keyword results by chunk_id
4. ✅ Add ONE config flag: `enable_keyword_search`
5. ✅ Create GIN index on chunk_text

**What we're NOT doing**:
- ❌ Query deduplication (waste of time, results already deduped)
- ❌ Complex Pydantic models (internal logic doesn't need exposure)
- ❌ New HybridRetriever class (just modify AdvancedRetriever)
- ❌ Special Chinese handling (already works)
- ❌ Multiple config parameters (YAGNI)

**Lines of code estimate**: ~100 lines (not 500)

**Next Steps**: Update data-model.md, delete contracts/, simplify quickstart.md
