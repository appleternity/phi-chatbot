# Data Model: Multi-Query Expansion and Keyword Matching

**Feature**: 005-multi-query-keyword-search
**Date**: 2025-11-13
**Status**: Complete (Simplified)

## Overview

**Philosophy**: No over-engineering. Only document what actually changes in the database.

---

## Database Schema Changes

### 1. Enable pg_trgm Extension

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

**What it does**: Enables trigram-based similarity matching for fuzzy text search.

**Why**: Allows keyword matching for medical terms and drug names.

---

### 2. Create GIN Index on chunk_text

```sql
CREATE INDEX IF NOT EXISTS idx_chunk_text_trgm
ON vector_chunks
USING GIN (chunk_text gin_trgm_ops);
```

**Index Characteristics**:
- **Type**: GIN (Generalized Inverted Index)
- **Operator Class**: `gin_trgm_ops` (optimized for trigram similarity)
- **Build Time**: ~1-2 minutes for 10K chunks (one-time cost)
- **Index Size**: ~20-30% of text column size
- **Query Performance**: ~50ms for similarity search (vs ~20ms for HNSW vector index)

**Why**: Fast trigram similarity queries for keyword matching.

---

## Table Schema (No Changes)

Existing `vector_chunks` table remains unchanged:

```sql
-- Existing schema (no modifications)
CREATE TABLE vector_chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    chapter_title TEXT,
    section_title TEXT,
    subsection_title TEXT[],
    summary TEXT,
    token_count INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,              -- GIN index added here
    embedding vector(1024) NOT NULL,       -- Existing HNSW index
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**New Index**: `idx_chunk_text_trgm` on `chunk_text` column (see above)

---

## Configuration Changes

### app/config.py

Add ONE new configuration parameter:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Keyword Search Configuration (005-multi-query-keyword-search)
    enable_keyword_search: bool = Field(
        default=False,
        description="Enable pg_trgm keyword search alongside vector search"
    )
```

**That's it.** No other config needed.

**Why default=False?**:
- Allows testing vector-only behavior first
- Can enable after GIN index is created
- Fail-safe: If index missing, disable gracefully

---

## Query Examples

### Vector Search (Existing)

```sql
-- Cosine similarity search using pgvector
SELECT
    chunk_id,
    chunk_text,
    1 - (embedding <=> $1::vector) AS similarity_score
FROM vector_chunks
ORDER BY embedding <=> $1::vector
LIMIT 15;
```

### Keyword Search (New)

```sql
-- Trigram similarity search using pg_trgm
SELECT
    chunk_id,
    chunk_text,
    similarity(chunk_text, $1) AS keyword_score
FROM vector_chunks
WHERE chunk_text % $1  -- % is pg_trgm similarity operator (threshold ~0.3)
ORDER BY keyword_score DESC
LIMIT 15;
```

### Hybrid Search (Combined)

```python
# In AdvancedRetriever.search()
vector_results = await self._vector_search(queries)  # Uses HNSW index
keyword_results = await self._keyword_search(queries)  # Uses GIN index

# Merge and deduplicate by chunk_id
all_candidates = self._merge_results(vector_results, keyword_results)

# Rerank with Qwen3-Reranker
final_results = await self._rerank(all_candidates, top_k=5)
```

---

## Migration Script

### app/db/schema.py

Add migration function for pg_trgm:

```python
async def enable_keyword_search(conn: Connection) -> None:
    """Enable pg_trgm extension and create GIN index.

    This is idempotent - safe to run multiple times.
    """
    # Enable extension
    await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Create GIN index
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunk_text_trgm
        ON vector_chunks
        USING GIN (chunk_text gin_trgm_ops);
    """)

    print("✅ pg_trgm extension enabled and GIN index created")
```

**Usage**:
```bash
# Run migration
python -m app.db.schema enable-keyword-search
```

---

## Code Changes Summary

### Modified Files (3 files)

```
app/retrieval/advanced.py
├─ __init__(): Add max_queries parameter (default 10)
├─ expand_query(): Simplify prompt (no key prefixes), parse by '\n'
├─ _keyword_search(): NEW method using pg_trgm
├─ _merge_results(): NEW method for chunk_id deduplication
└─ search(): Integrate keyword search + merge results

app/db/schema.py
└─ enable_keyword_search(): NEW migration function

app/config.py
└─ enable_keyword_search: bool = False (NEW setting)
```

### No New Models

**Why?**: Internal logic doesn't need Pydantic models. Results are just dicts with:
- Existing fields: `chunk_id`, `chunk_text`, `similarity_score`, `rerank_score`, etc.
- Optional new field: `keyword_score` (if found via keyword search)

---

## Performance Impact

| Component | Baseline (Vector Only) | With Keyword Search | Delta |
|-----------|----------------------|---------------------|-------|
| Query Expansion | ~400ms (4 queries) | ~400ms (up to 10) | Same |
| Vector Search | ~80ms (4×20ms) | ~200ms (10×20ms) | +120ms |
| Keyword Search | N/A | ~500ms (10×50ms) | +500ms |
| Deduplication | ~5ms | ~10ms | +5ms |
| Reranking | ~600ms (20 candidates) | ~1500ms (40 candidates) | +900ms |
| **Total** | **~1.1s** | **~2.6s** | **+1.5s** |

**Conclusion**: Within 3s budget (SC-004). Acceptable.

---

## Summary

**Database Changes**: 2 SQL statements
1. `CREATE EXTENSION pg_trgm`
2. `CREATE INDEX idx_chunk_text_trgm`

**Config Changes**: 1 parameter
- `enable_keyword_search: bool = False`

**Code Changes**: ~100 lines across 3 files
- Modify AdvancedRetriever
- Add migration function
- Add config parameter

**No Pydantic Models**: Not needed for internal logic.

**Next Steps**: Simplify quickstart.md, update plan.md
