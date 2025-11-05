# Testing Guide - Semantic Search

This guide covers testing the semantic search functionality, including retrieval, reranking, and performance validation.

---

## Test Search Functionality

### Test PostgreSQL Retriever

Create a test file `test_search.py`:

```python
import asyncio
from app.core.postgres_retriever import PostgreSQLRetriever
from app.db.connection import get_pool, close_pool

async def test_search():
    # Initialize database pool
    pool = await get_pool()

    # Create retriever (with reranking)
    retriever = PostgreSQLRetriever(pool)

    # Search for side effects
    query = "What are common side effects of aripiprazole?"
    results = await retriever.search(query, top_k=5)

    print(f"\n=== Search Results for: {query} ===\n")
    for i, doc in enumerate(results, 1):
        print(f"{i}. {doc.metadata['chunk_id']}")
        print(f"   Source: {doc.metadata['source_document']}")
        print(f"   Chapter: {doc.metadata.get('chapter_title', 'N/A')}")
        print(f"   Section: {doc.metadata.get('section_title', 'N/A')}")
        print(f"   Similarity Score: {doc.metadata.get('similarity_score', 0):.4f}")
        print(f"   Rerank Score: {doc.metadata.get('rerank_score', 0):.4f}")
        print(f"   Content: {doc.content[:200]}...")
        print()

    # Cleanup
    await close_pool()

if __name__ == "__main__":
    asyncio.run(test_search())
```

Run the test:

```bash
python test_search.py

# Expected output:
# === Search Results for: What are common side effects of aripiprazole? ===
#
# 1. 02_aripiprazole_chunk_042
#    Source: 02_aripiprazole
#    Chapter: Adverse Reactions
#    Section: Common Adverse Reactions
#    Similarity Score: 0.8234
#    Rerank Score: 0.9521
#    Content: Common adverse reactions (≥5% and at least twice the rate of placebo) include: nausea, vomiting, constipation...
```

### Verify Reranking Performance

The reranker improves result quality by re-scoring candidates:

```python
# Check that rerank_score is higher than similarity_score for top results
# This indicates reranking is working correctly
```

---

## Run Test Suite

### Unit Tests

Tests for individual components without database dependencies:

```bash
# Run all unit tests
pytest tests/semantic-search/unit/

# Run specific unit test file
pytest tests/semantic-search/unit/test_postgres_retriever.py

# Run with verbose output
pytest tests/semantic-search/unit/ -v
```

### Integration Tests

Tests that require database and full system integration:

```bash
# Run all integration tests (requires database running)
pytest tests/semantic-search/integration/

# Run specific integration test categories
pytest tests/semantic-search/integration/test_indexing.py
pytest tests/semantic-search/integration/test_retrieval_strategies.py
pytest tests/semantic-search/integration/test_retrieval_module.py
pytest tests/semantic-search/integration/test_comprehensive.py

# Run with verbose output
pytest tests/semantic-search/integration/ -v
```

### All Tests with Coverage

```bash
# Run all tests with coverage report
pytest tests/semantic-search/ --cov=app.core --cov=app.retrieval --cov=src.embeddings --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## Performance Benchmarking

### Search Performance

Test query response times:

```python
# benchmark_search.py
import asyncio
import time
from app.core.postgres_retriever import PostgreSQLRetriever
from app.db.connection import get_pool, close_pool

async def benchmark():
    pool = await get_pool()
    retriever = PostgreSQLRetriever(pool)

    queries = [
        "side effects of aripiprazole",
        "dosage for children",
        "drug interactions",
        "mechanism of action",
        "clinical trials"
    ]

    times = []
    for query in queries:
        start = time.time()
        await retriever.search(query, top_k=5)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Query: '{query}' - {elapsed:.2f}s")

    print(f"\nAverage query time: {sum(times)/len(times):.2f}s")
    print(f"p95 query time: {sorted(times)[int(len(times)*0.95)]:.2f}s")

    await close_pool()

if __name__ == "__main__":
    asyncio.run(benchmark())

# Expected output:
# Average query time: 2.1s
# p95 query time: 2.8s
```

---

## Success Criteria Checklist

Verify all these criteria after setup:

- [ ] **PostgreSQL Running**: Container `langgraph-postgres-vector` is healthy
- [ ] **Database Populated**: Contains 1247 indexed chunks from 42 documents
- [ ] **Backend Started**: Server running on http://localhost:8000
- [ ] **Frontend Started**: UI running on http://localhost:3000
- [ ] **Health Check Passes**: `curl http://localhost:8000/health` returns 200
- [ ] **Chat Endpoint Works**: Returns grounded answers using semantic search
- [ ] **Search Performance**: Queries return results in <100ms (pgvector similarity)
- [ ] **Reranking Performance**: Reranking completes in <2s for 20 candidates → top-5 results
- [ ] **Frontend Displays Correctly**: Conversation UI with session persistence
- [ ] **No Browser Errors**: Browser console shows no errors
- [ ] **Database Size Reasonable**: Database storage <50MB for 1247 chunks

---

## Validation Commands

### Check Database Statistics

```bash
# Connect to PostgreSQL
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Check chunk count
SELECT COUNT(*) FROM vector_chunks;
# Expected: 1247

# Check document count
SELECT COUNT(DISTINCT source_document) FROM vector_chunks;
# Expected: 42

# Check database size
SELECT pg_size_pretty(pg_database_size('medical_knowledge'));
# Expected: ~45 MB

# Exit
\q
```

### Verify Indexing Quality

```bash
# Check indexing version
python -m src.embeddings.cli version

# Validate indexed data
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "
  SELECT
    source_document,
    COUNT(*) as chunk_count,
    AVG(token_count) as avg_tokens
  FROM vector_chunks
  GROUP BY source_document
  ORDER BY chunk_count DESC
  LIMIT 10;
"
```

---

## Troubleshooting Tests

### Tests Fail - Database Not Running

**Solution**: Start PostgreSQL container
```bash
docker-compose up -d
```

### Tests Fail - No Data Indexed

**Solution**: Restore database or run indexing
```bash
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump
```

### Integration Tests Timeout

**Solution**: Increase timeout or reduce test dataset size
```bash
pytest tests/semantic-search/integration/ --timeout=300
```

---

## Next Steps

After validating the system:

1. **Customize Search**: Modify retrieval strategy in `app/config.py`
2. **Add Custom Tests**: Create tests for your specific use cases
3. **Monitor Performance**: Add logging and metrics collection
4. **Optimize Index**: Tune HNSW parameters for your dataset
5. **Deploy**: See [specs/002-semantic-search/spec.md](spec.md) for deployment guidelines
