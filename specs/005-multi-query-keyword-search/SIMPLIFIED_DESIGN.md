# Simplified Design Summary

**Date**: 2025-11-13
**Philosophy**: "Simple > Complex | Working Code > Perfect Design | Evidence > Speculation"

---

## What We're Actually Doing

### 1. Modify AdvancedRetriever (~100 lines)

```python
class AdvancedRetriever:
    def __init__(self, pool, encoder, reranker, max_queries: int = 10):
        self.max_queries = max_queries  # NEW: configurable (was fixed 4)
    
    async def expand_query(self, query: str, ...) -> List[str]:
        # Simplified prompt: no key prefixes (SPECIFIC:, BROADER:, etc.)
        # Just newline-separated queries
        prompt = f"Generate up to {self.max_queries} diverse English queries..."
        response = self.llm.invoke(prompt)
        
        # Simple parsing
        queries = [q.strip() for q in response.split('\n') if q.strip()]
        return queries[:self.max_queries]  # Truncate to max
    
    async def _keyword_search(self, queries: List[str]) -> List[Dict]:
        # NEW method: pg_trgm keyword matching
        sql = """
        SELECT *, similarity(chunk_text, $1) AS keyword_score
        FROM vector_chunks
        WHERE chunk_text % $1
        ORDER BY keyword_score DESC
        LIMIT $2
        """
        # Execute all queries in parallel with asyncio.gather()
    
    def _merge_results(self, vector_results, keyword_results) -> List[Dict]:
        # NEW method: simple dict deduplication
        seen = {}
        for r in vector_results + keyword_results:
            if r['chunk_id'] not in seen:
                seen[r['chunk_id']] = r
        return list(seen.values())
    
    async def search(self, query, top_k=5, filters=None):
        # 1. Expand queries (up to 10)
        queries = await self.expand_query(...)
        
        # 2. Vector search (parallel)
        vector_results = await self._parallel_vector_search(queries)
        
        # 3. Keyword search (parallel, optional)
        if settings.enable_keyword_search:
            keyword_results = await self._keyword_search(queries)
        else:
            keyword_results = []
        
        # 4. Merge by chunk_id
        candidates = self._merge_results(vector_results, keyword_results)
        
        # 5. Rerank
        return await self._rerank(candidates, top_k)
```

---

### 2. Database Migration (2 SQL Statements)

```sql
-- Enable extension (already in PostgreSQL 15+)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create GIN index for fast trigram matching
CREATE INDEX IF NOT EXISTS idx_chunk_text_trgm
ON vector_chunks
USING GIN (chunk_text gin_trgm_ops);
```

---

### 3. Configuration (1 Parameter)

```python
# app/config.py
class Settings(BaseSettings):
    enable_keyword_search: bool = False  # NEW: default off
```

```bash
# .env
ENABLE_KEYWORD_SEARCH=true  # Enable when ready
```

---

## What We're NOT Doing (Over-Engineering Removed)

| ❌ Deleted | Why Unnecessary |
|-----------|-----------------|
| Query deduplication | Results already deduped by chunk_id |
| HybridRetriever class | Just modify AdvancedRetriever |
| Pydantic models | Internal logic doesn't need exposure |
| Multiple config params | One flag is enough |
| Complex protocol contracts | No new interface |
| Chinese translation logic | Already works in LLM prompt |
| Query validation | LLM output is good enough |

---

## Code Changes Summary

| File | Changes | Lines Added |
|------|---------|-------------|
| `app/retrieval/advanced.py` | Add max_queries, _keyword_search(), _merge_results() | ~100 |
| `app/db/schema.py` | Add enable_keyword_search() migration | ~20 |
| `app/config.py` | Add enable_keyword_search: bool | ~5 |
| **Total** | **3 files modified** | **~125 lines** |

**Test Files**:
- `tests/integration/test_advanced_retriever.py` (add multi-query + keyword tests)
- `tests/unit/test_result_deduplication.py` (new, test _merge_results())

---

## Performance Budget

| Component | Time | Method |
|-----------|------|--------|
| Query Expansion | ~400ms | LLM generates up to 10 queries |
| Vector Search | ~200ms | 10 queries × 20ms (HNSW, parallel) |
| Keyword Search | ~500ms | 10 queries × 50ms (GIN, parallel) |
| Deduplication | ~10ms | Dict lookup by chunk_id |
| Reranking | ~1500ms | Qwen3-Reranker (40 candidates) |
| **Total** | **~2.6s** | Within 3s budget ✅ |

---

## Usage Example (Before vs After)

### Before (Fixed 4 Queries with Keys)

```python
retriever = AdvancedRetriever(pool, encoder, reranker)
results = await retriever.search(query, top_k=5)

# LLM output:
# SPECIFIC: aripiprazole mechanism
# BROADER: antipsychotic medications
# KEYWORDS: aripiprazole schizophrenia
# CONTEXTUAL: treating psychosis with aripiprazole
```

### After (Configurable, No Keys)

```python
retriever = AdvancedRetriever(pool, encoder, reranker, max_queries=10)
results = await retriever.search(query, top_k=5)

# LLM output (simple):
# aripiprazole
# aripiprazole mechanism
# aripiprazole side effects
# aripiprazole dosage
# how aripiprazole works
# ... (up to 10 queries)
```

---

## Constitution Compliance

**All 6 Principles**: ✅ PASS

| Principle | Status | Why |
|-----------|--------|-----|
| Agent-First | ✅ | Changes isolated to retrieval layer |
| State Management | ✅ | No LangGraph state changes |
| Test-First | ✅ | Integration + unit tests planned |
| Observability | ✅ | Logging with query_count, search_time |
| Abstraction | ✅ | Uses existing interfaces |
| **Simplicity (YAGNI)** | **✅✅✅** | **No over-engineering!** |

---

## Ready to Implement?

**Next Steps**:
1. Review this simplified design
2. Run `/speckit.tasks` to generate implementation tasks
3. Start with TDD: write tests first, then implementation

**Files to Review**:
- `research.md` - Technical decisions (5 research questions)
- `data-model.md` - Database changes (2 SQL statements)
- `quickstart.md` - Usage guide (3 examples)
- `plan.md` - Complete design plan

**Estimated Time**: ~4-6 hours implementation (not days)
