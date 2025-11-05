# Developer Guide - Semantic Search

This guide covers development workflows, database management, indexing operations, and advanced features for the semantic search system.

---

## Database Management

### Database Operations

```bash
# Start PostgreSQL container
docker-compose up -d

# Stop database
docker-compose down

# Stop and remove volumes (destructive - deletes all data!)
docker-compose down -v

# View database logs
docker-compose logs -f postgres-vector

# Restart database
docker-compose restart postgres-vector
```

### Backup Operations

```bash
# Create backup (timestamped)
docker exec langgraph-postgres-vector pg_dump \
  -U postgres \
  -d medical_knowledge \
  -Fc > backups/medical_knowledge-$(date +%Y%m%d-%H%M%S).dump

# Create backup (named)
docker exec langgraph-postgres-vector pg_dump \
  -U postgres \
  -d medical_knowledge \
  -Fc > backups/medical_knowledge-custom-name.dump
```

### Restore Operations

```bash
# Restore from latest backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# Restore from specific backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-20251105-101823.dump
```

### Database Inspection

```bash
# Connect to PostgreSQL
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge

# Common queries:
# List all tables
\dt

# Describe vector_chunks table
\d vector_chunks

# Check chunk count
SELECT COUNT(*) FROM vector_chunks;

# Check document distribution
SELECT source_document, COUNT(*) as chunks
FROM vector_chunks
GROUP BY source_document
ORDER BY chunks DESC;

# Check embedding dimensions
SELECT DISTINCT array_length(embedding::real[], 1) as dimensions
FROM vector_chunks;

# Exit
\q
```

---

## Indexing Management

### Indexing Operations

```bash
# Check indexing version
python -m src.embeddings.cli version

# Index all documents (skip existing chunks)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --skip-existing \
  --verbose

# Force re-index all documents (overwrites existing)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --no-skip-existing \
  --verbose

# Index with custom parameters
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --model-name Qwen/Qwen3-Embedding-0.6B \
  --device mps \
  --batch-size 16 \
  --max-length 1024 \
  --verbose
```

### Indexing Configuration

Edit `config/embedding_config.json`:

```json
{
  "model_name": "Qwen/Qwen3-Embedding-0.6B",
  "device": "mps",
  "batch_size": 16,
  "max_length": 1024,
  "normalize_embeddings": true,
  "instruction": null
}
```

### Indexing Validation

```bash
# Check for indexing errors
tail -n 50 indexing_errors.log

# Validate indexed chunks
python -m src.embeddings.cli validate \
  --input data/chunking_final \
  --check-embeddings
```

---

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/

# Run semantic search tests only
pytest tests/semantic-search/

# Run unit tests (fast, no database)
pytest tests/semantic-search/unit/

# Run integration tests (requires database)
pytest tests/semantic-search/integration/

# Run specific test file
pytest tests/semantic-search/unit/test_postgres_retriever.py

# Run with verbose output
pytest tests/semantic-search/ -v

# Run with specific test pattern
pytest tests/semantic-search/ -k "test_search"
```

### Test with Coverage

```bash
# Run all tests with coverage
pytest tests/ --cov=app --cov=src --cov-report=html

# Run semantic search tests with coverage
pytest tests/semantic-search/ \
  --cov=app.core \
  --cov=app.retrieval \
  --cov=src.embeddings \
  --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Linting and Type Checking

```bash
# Run type checking
mypy app/ src/ --ignore-missing-imports

# Run linting
ruff check app/ src/

# Auto-fix linting issues
ruff check app/ src/ --fix

# Format code
black app/ src/ tests/
```

---

## Development Workflows

### Adding New Documents

1. Place chunk JSON files in `data/chunking_final/`
2. Run indexing:
   ```bash
   python -m src.embeddings.cli index \
     --input data/chunking_final \
     --skip-existing \
     --verbose
   ```
3. Verify indexing:
   ```bash
   docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT COUNT(*) FROM vector_chunks;"
   ```

### Customizing Retrieval Strategy

Edit `app/config.py` or `.env`:

```bash
# Simple retrieval (fastest, no reranking)
RETRIEVAL_STRATEGY=simple

# Rerank retrieval (balanced, recommended)
RETRIEVAL_STRATEGY=rerank
SEMANTIC_RERANKER_CANDIDATE_COUNT=20
SEMANTIC_RERANKER_TOP_K=5

# Advanced retrieval (slowest, highest accuracy)
RETRIEVAL_STRATEGY=advanced
```

### Modifying Reranker Settings

Edit `.env`:

```bash
# Reranker configuration
SEMANTIC_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B
SEMANTIC_RERANKER_DEVICE=mps  # or 'cpu' or 'cuda'
SEMANTIC_RERANKER_BATCH_SIZE=8
SEMANTIC_RERANKER_TOP_K=5
SEMANTIC_RERANKER_CANDIDATE_COUNT=20
```

### Changing Embedding Model

Edit `.env`:

```bash
# Embedding configuration
SEMANTIC_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
SEMANTIC_EMBEDDING_DEVICE=mps  # or 'cpu' or 'cuda'
SEMANTIC_EMBEDDING_BATCH_SIZE=16
SEMANTIC_EMBEDDING_MAX_LENGTH=1024
```

**Note**: If you change the embedding model, you must re-index all documents.

---

## Advanced Features

### Query Expansion (Advanced Retrieval)

The advanced retrieval strategy uses LLM-based query expansion:

```python
# app/retrieval/advanced.py
# Generates 3 query variations for better coverage
# Retrieves candidates for each variation
# Deduplicates and reranks combined results
```

Enable in `.env`:
```bash
RETRIEVAL_STRATEGY=advanced
```

### Metadata Filtering

Filter search results by metadata:

```python
from app.core.postgres_retriever import PostgreSQLRetriever

# Search with source document filter
results = await retriever.search(
    query="side effects",
    top_k=5,
    filter_metadata={"source_document": "02_aripiprazole"}
)

# Search with chapter filter
results = await retriever.search(
    query="dosage",
    top_k=5,
    filter_metadata={"chapter_title": "Dosage and Administration"}
)
```

### Model Preloading

Load models at startup for faster first request:

```bash
# .env
PRELOAD_MODELS=True
```

**Trade-off**: Slower startup (~30s) but faster first request

---

## Performance Optimization

### Database Optimization

```bash
# Analyze database for query optimization
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "ANALYZE;"

# Check index usage
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "
  SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
  FROM pg_stat_user_indexes
  WHERE tablename = 'vector_chunks';
"
```

### HNSW Index Tuning

The HNSW index parameters can be tuned for your dataset:

```sql
-- Default parameters (m=16, ef_construction=64)
CREATE INDEX idx_embedding_cosine
ON vector_chunks
USING hnsw (embedding vector_cosine_ops);

-- Higher accuracy (slower indexing, faster search)
CREATE INDEX idx_embedding_cosine_high_accuracy
ON vector_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);

-- Faster indexing (lower accuracy)
CREATE INDEX idx_embedding_cosine_fast
ON vector_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 8, ef_construction = 32);
```

### Batch Size Tuning

Adjust batch sizes based on available memory:

```bash
# .env

# For systems with 8GB RAM
SEMANTIC_EMBEDDING_BATCH_SIZE=8
SEMANTIC_RERANKER_BATCH_SIZE=4

# For systems with 16GB+ RAM
SEMANTIC_EMBEDDING_BATCH_SIZE=32
SEMANTIC_RERANKER_BATCH_SIZE=16
```

---

## Monitoring and Debugging

### Application Logs

```bash
# View backend logs
python -m app.main

# View with debug logging
LOG_LEVEL=DEBUG python -m app.main
```

### Database Logs

```bash
# View PostgreSQL logs
docker-compose logs -f postgres-vector

# View last 100 lines
docker-compose logs --tail=100 postgres-vector
```

### Indexing Logs

```bash
# Check indexing errors
cat indexing_errors.log

# Monitor indexing in real-time
tail -f indexing_errors.log
```

---

## Deployment

### Production Checklist

Before deploying to production:

- [ ] Use managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database)
- [ ] Set `PRELOAD_MODELS=True` for faster response times
- [ ] Configure connection pooling (min=10, max=50 for production)
- [ ] Set up database backups (daily)
- [ ] Configure monitoring and alerting
- [ ] Use production-grade WSGI server (gunicorn, uvicorn with workers)
- [ ] Set up HTTPS/TLS for API
- [ ] Configure CORS appropriately
- [ ] Review and lock dependency versions

### Environment Variables for Production

```bash
# Production settings
ENVIRONMENT=production
LOG_LEVEL=INFO
PRELOAD_MODELS=True

# Database (use managed PostgreSQL)
POSTGRES_HOST=your-prod-db.region.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=medical_knowledge
POSTGRES_USER=prod_user
POSTGRES_PASSWORD=strong_password_here

# Connection pooling
DB_POOL_MIN_SIZE=10
DB_POOL_MAX_SIZE=50

# Performance
SEMANTIC_EMBEDDING_DEVICE=cuda  # or 'cpu' depending on infrastructure
SEMANTIC_RERANKER_DEVICE=cuda
```

---

## Reference

- **Feature Specification**: [spec.md](spec.md)
- **Testing Guide**: [testing.md](testing.md)
- **Implementation Plan**: [plan.md](plan.md)
- **Technical Research**: [research.md](research.md)
- **Data Model**: [data-model.md](data-model.md)
- **API Contracts**: [contracts/](contracts/)
