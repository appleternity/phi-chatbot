# Quickstart Guide: Multi-Query Expansion and Keyword Matching

**Feature**: 005-multi-query-keyword-search
**Date**: 2025-11-13
**Status**: Complete (Simplified)

---

## Setup (3 Steps)

### 1. Enable pg_trgm Extension

```bash
# Connect to PostgreSQL
psql -U postgres -d medical_knowledge

# Enable extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

# Create GIN index
CREATE INDEX IF NOT EXISTS idx_chunk_text_trgm
ON vector_chunks
USING GIN (chunk_text gin_trgm_ops);

# Verify
\di idx_chunk_text_trgm
```

**Expected**: Index creation takes ~1-2 minutes for 10K chunks.

---

### 2. Enable Keyword Search (Optional)

```bash
# Add to .env
ENABLE_KEYWORD_SEARCH=true
```

**Default**: `false` (vector-only, for testing baseline first)

---

### 3. Test It Works

```python
from langchain_core.messages import HumanMessage
from app.retrieval.advanced import AdvancedRetriever
from app.db.connection import DatabasePool
from app.embeddings.factory import create_embedding_provider
from app.core.qwen3_reranker import Qwen3Reranker
from app.config import settings

async with DatabasePool() as pool:
    encoder = create_embedding_provider(...)
    reranker = Qwen3Reranker(...)
    retriever = AdvancedRetriever(pool, encoder, reranker)

    # Simple query
    results = await retriever.search(
        [HumanMessage(content="What is aripiprazole?")],
        top_k=5
    )

    for r in results:
        print(f"Score: {r['rerank_score']:.3f}")
        print(f"Text: {r['chunk_text'][:100]}...")
```

**Expected**: Returns 5 results in ~1-2 seconds.

---

## Usage Examples

### Example 1: Simple Query

```python
query = [HumanMessage(content="What is aripiprazole?")]
results = await retriever.search(query, top_k=5)

# System generates 2-3 queries:
# - "aripiprazole"
# - "aripiprazole mechanism"
# - "what is aripiprazole"
```

**Latency**: ~1-2s

---

### Example 2: Comparison Query

```python
query = [HumanMessage(content="Compare aripiprazole and risperidone")]
results = await retriever.search(query, top_k=5)

# System generates 5-10 queries:
# - "aripiprazole"
# - "risperidone"
# - "aripiprazole mechanism"
# - "risperidone mechanism"
# - "aripiprazole side effects"
# - "risperidone side effects"
# - "aripiprazole vs risperidone"
# ... (up to 10)
```

**Latency**: ~2-3s

---

### Example 3: Chinese Query

```python
query = [HumanMessage(content="阿立哌唑的作用機制")]
results = await retriever.search(query, top_k=5)

# LLM automatically translates to English:
# - "aripiprazole mechanism"
# - "aripiprazole pharmacology"
# - "how aripiprazole works"
```

**Latency**: ~1.5-2s

---

## Debugging

### Check Multi-Query Generation

```python
# See what queries were generated
retriever = AdvancedRetriever(pool, encoder, reranker, max_queries=10)

queries = await retriever.expand_query(
    query="Compare Drug A and Drug B",
    conversation_context=None
)

print(f"Generated {len(queries)} queries:")
for q in queries:
    print(f"  - {q}")
```

---

### Test Keyword Search Only

```python
# Enable keyword search
import os
os.environ['ENABLE_KEYWORD_SEARCH'] = 'true'

# Test keyword search directly
keyword_results = await retriever._keyword_search(
    queries=["aripiprazole"],
    top_k_per_query=10
)

print(f"Found {len(keyword_results)} results")
for r in keyword_results:
    if 'keyword_score' in r:
        print(f"Keyword Score: {r['keyword_score']:.3f}")
```

---

### Performance Monitoring

```python
import time

start = time.time()
results = await retriever.search(query, top_k=5)
elapsed_ms = (time.time() - start) * 1000

print(f"Total Time: {elapsed_ms:.0f}ms")

# Check if within budget
assert elapsed_ms < 3000, f"Exceeded 3s budget: {elapsed_ms}ms"
```

---

## Troubleshooting

### Problem: `pg_trgm extension not found`

**Solution**:
```sql
-- Connect to database
psql -U postgres -d medical_knowledge

-- Enable extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

### Problem: Query expansion generates 0 queries

**Solution**: LLM fallback automatically uses original query. Check logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

results = await retriever.search(query)
# Look for: "Query expansion parsing incomplete" or "Using fallback strategy"
```

---

### Problem: Slow retrieval (>3 seconds)

**Debugging**:

1. **Check indexes exist**:
   ```sql
   -- Verify HNSW index
   SELECT * FROM pg_indexes WHERE indexname = 'idx_embedding_cosine';

   -- Verify GIN index
   SELECT * FROM pg_indexes WHERE indexname = 'idx_chunk_text_trgm';
   ```

2. **Disable keyword search temporarily**:
   ```bash
   ENABLE_KEYWORD_SEARCH=false
   ```

3. **Reduce max_queries**:
   ```python
   retriever = AdvancedRetriever(pool, encoder, reranker, max_queries=5)
   ```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_KEYWORD_SEARCH` | `false` | Enable pg_trgm keyword search |

**That's it.** No other config needed.

---

## Performance Tuning

**Faster retrieval** (prioritize speed):
- Set `max_queries=5` in AdvancedRetriever constructor
- Set `ENABLE_KEYWORD_SEARCH=false` (vector-only)

**Better coverage** (prioritize recall):
- Set `max_queries=10` (more queries)
- Set `ENABLE_KEYWORD_SEARCH=true` (hybrid search)

---

## What Changed?

### Before (Fixed 4 Queries)

```python
retriever = AdvancedRetriever(pool, encoder, reranker)
results = await retriever.search(query, top_k=5)
# Always generates exactly 4 queries with key prefixes:
# SPECIFIC: ...
# BROADER: ...
# KEYWORDS: ...
# CONTEXTUAL: ...
```

### After (Configurable, No Key Prefixes)

```python
retriever = AdvancedRetriever(pool, encoder, reranker, max_queries=10)
results = await retriever.search(query, top_k=5)
# Generates 2-10 queries depending on complexity, simple format:
# query 1
# query 2
# query 3
# ...
```

**Key Changes**:
- Configurable query count (2-10 vs fixed 4)
- Simpler parsing (split by '\n' vs complex key matching)
- Optional keyword search (pg_trgm)
- No backward compatibility needed (dev stage)

---

## Next Steps

- Review [research.md](research.md) for technical decisions
- Review [data-model.md](data-model.md) for database changes
- Ready to implement? Start with TDD tests first

---

## Support

**Logs**: Set `LOG_LEVEL=DEBUG` in .env
**Database**: Check indexes with `\di` in psql
**Tests**: Run `pytest tests/` to verify changes
