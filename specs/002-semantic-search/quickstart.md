# Quickstart Guide: Semantic Search with PostgreSQL and pgvector

**Feature**: 002-semantic-search
**Target Audience**: Developers setting up the complete system (database + backend + frontend)
**Time to Complete**: 5-10 minutes (with backup) or 25-40 minutes (fresh install)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.11+** installed
- **Docker** and **Docker Compose** installed (for local PostgreSQL)
- **Node.js 18+** and **npm/yarn** (for frontend)
- **Apple Silicon Mac** (M1/M2/M3) with macOS 12.3+ for MPS support (recommended)
- **8GB+ RAM** recommended for embedding generation
- **OpenRouter API Key** for LLM calls

---

## Quick Setup Overview

**Two paths to get started:**

1. **Quick Start (Recommended)**: Restore from backup → 5-10 minutes
2. **Fresh Install**: Create schema + index documents → 25-40 minutes

Both paths lead to the same result: a fully functional medical chatbot with semantic search.

---

## Step 1: Environment Setup (3 minutes)

### 1.1 Install Python Dependencies

```bash
# Install all dependencies from requirements.txt
pip install -r requirements.txt

# Verify PyTorch MPS support (Apple Silicon only)
python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"
# Expected output: MPS available: True
```

### 1.2 Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your OpenRouter API key
# Required:
OPENROUTER_API_KEY=your_api_key_here

# PostgreSQL settings (defaults are fine for local development)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_knowledge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medical_knowledge

# Semantic Search - Embedding
SEMANTIC_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
SEMANTIC_EMBEDDING_DEVICE=mps  # or 'cpu' for non-Apple Silicon
SEMANTIC_EMBEDDING_BATCH_SIZE=16
SEMANTIC_EMBEDDING_MAX_LENGTH=1024

# Semantic Search - Reranker
SEMANTIC_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B
SEMANTIC_RERANKER_DEVICE=mps  # or 'cpu'
SEMANTIC_RERANKER_BATCH_SIZE=8
SEMANTIC_RERANKER_TOP_K=5
SEMANTIC_RERANKER_CANDIDATE_COUNT=20

# Retrieval Strategy
RETRIEVAL_STRATEGY=rerank  # Options: simple, rerank, advanced
PRELOAD_MODELS=False       # True = load at startup, False = lazy load
```

---

## Step 2: Database Setup (5-30 minutes)

### Option A: Quick Start - Restore from Backup (RECOMMENDED - 5 minutes)

This is the fastest way to get started. The backup includes schema + 1247 pre-indexed chunks.

```bash
# 1. Start PostgreSQL container
docker-compose up -d

# 2. Verify container is running
docker ps | grep langgraph-postgres-vector
# Expected: Container "langgraph-postgres-vector" running on port 5432

# 3. Restore database from backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# Expected output:
# 🔄 PostgreSQL Setup and Restore Starting...
# 📁 Backup file: backups/medical_knowledge-latest.dump
# 🗑️  Step 1: Dropping existing database (if exists)...
# 🏗️  Step 2: Creating new database...
# 🔌 Step 3: Installing pgvector extension...
# 📋 Step 4: Creating database schema...
# 📦 Step 5: Restoring data from backup...
# 📊 Step 6: Analyzing database (updating query statistics)...
# 🔍 Step 7: Verifying restoration...
# ✅ PostgreSQL setup and restore complete!
#
# 📊 Database Statistics:
#    pgvector version: 0.5.1
#    Total chunks: 1247
#    Total documents: 42
#    Database size: 45 MB
```

**You're done!** Skip to Step 3 (Start Backend Server).

### Option B: Fresh Install - Create Schema + Index Documents (25-40 minutes)

Use this if you want to index fresh documents or customize the indexing process.

#### 2B.1 Start PostgreSQL

```bash
# Start PostgreSQL with pgvector extension
docker-compose up -d

# Verify container is running and healthy
docker ps | grep langgraph-postgres-vector
# Expected: Container "langgraph-postgres-vector" (healthy) on port 5432

# View logs (optional)
docker-compose logs -f postgres-vector
```

#### 2B.2 Create Database Schema

```bash
# Create vector_chunks table with HNSW index
python -m app.db.schema \
  --host localhost \
  --port 5432 \
  --database medical_knowledge \
  --user postgres \
  --password postgres

# Or use DATABASE_URL from .env
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/medical_knowledge"
python -m app.db.schema

# Expected output:
# ✓ Created extension: vector
# ✓ Created table: vector_chunks (1024-dim embeddings)
# ✓ Created index: idx_embedding_cosine (HNSW)
# ✓ Created index: idx_source_document
# ✓ Created index: idx_chapter_title
# ✓ Created table: schema_metadata
```

#### 2B.3 Index Documents (20-30 minutes)

```bash
# Index all chunks from data/chunking_final
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --model-name Qwen/Qwen3-Embedding-0.6B \
  --device mps \
  --batch-size 16 \
  --max-length 1024 \
  --verbose

# Expected output (progress bar):
# Indexing chunks: 100%|████████████████| 1247/1247 [25:30<00:00, 1.23s/chunk]
# ✓ Successfully indexed: 1247 chunks
# ⏱ Total time: ~25-30 minutes on MPS (M1/M2/M3)
```

#### 2B.4 Verify Database

```bash
# Connect to PostgreSQL
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Check vector_chunks table
\d vector_chunks

# Check chunk count
SELECT COUNT(*) FROM vector_chunks;
# Expected: 1247

# Check document count
SELECT COUNT(DISTINCT source_document) FROM vector_chunks;
# Expected: 42

# Exit psql
\q
```

---

## Step 3: Start Backend Server (1 minute)

```bash
# Start FastAPI + LangGraph backend
python -m app.main

# Expected output:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# 🔧 Initializing database connection pool...
# ✓ Database connection pool initialized (min=5, max=20)
# 🔍 Verifying database setup...
# ✓ pgvector extension found (version 0.5.1)
# ✓ vector_chunks table exists
# ✓ Found 1247 indexed chunks
# 📦 Loading embedding encoder (Qwen3-Embedding-0.6B)...
# ✓ Embedding encoder loaded (device: mps)
# 🎯 Loading reranker (Qwen3-Reranker-0.6B)...
# ✓ Reranker loaded (device: mps)
# 🤖 Building medical chatbot graph...
# ✓ Medical chatbot graph built successfully
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Backend is now running on http://localhost:8000**

### Test Backend Health

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"0.1.0"}

# Test chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are side effects of aripiprazole?", "session_id": "test-123"}'

# Expected: JSON response with session_id, message, agent, metadata
```

---

## Step 4: Start Frontend Server (2 minutes)

Open a **new terminal** window:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
npm install
# Or: yarn install / pnpm install

# Configure frontend environment
cp .env.example .env
# Edit .env to set:
VITE_API_URL=http://localhost:8000

# Start development server
npm run dev

# Expected output:
# VITE v5.x.x  ready in XXX ms
#
# ➜  Local:   http://localhost:3000/
# ➜  Network: use --host to expose
# ➜  press h + enter to show help
```

**Frontend is now running on http://localhost:3000**

### Access the Application

1. Open your browser to **http://localhost:3000**
2. You should see the medical chatbot interface
3. Try asking: "What are the side effects of aripiprazole?"
4. Observe the agent switch between Emotional Support and Medical Info agents
5. Check the session persistence (refresh page, conversation should persist)

---

## Step 5: Test Search Functionality (Optional - 5 minutes)

### 5.1 Test PostgreSQL Retriever

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

### 5.2 Verify Reranking Performance

The reranker improves result quality by re-scoring candidates:

```python
# Check that rerank_score is higher than similarity_score for top results
# This indicates reranking is working correctly
```

---

## Troubleshooting

### Issue: Database Connection Refused

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
1. Verify Docker container running: `docker ps | grep langgraph-postgres-vector`
2. Check port 5432 available: `lsof -i :5432`
3. Restart container: `docker-compose restart postgres-vector`
4. Check DATABASE_URL in .env matches container settings

### Issue: MPS Device Not Available

**Symptom**: `torch.backends.mps.is_available()` returns `False`

**Solution**:
1. Verify macOS version ≥ 12.3: `sw_vers`
2. Update PyTorch: `pip install --upgrade torch`
3. Fallback to CPU: Set `SEMANTIC_EMBEDDING_DEVICE=cpu` and `SEMANTIC_RERANKER_DEVICE=cpu` in `.env`

### Issue: Backend Fails to Start - "No documents indexed"

**Symptom**: Backend fails with error "No documents indexed. Please run indexing first."

**Solution**:
1. Verify database has data: `docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT COUNT(*) FROM vector_chunks;"`
2. If count is 0, restore from backup or run indexing (see Step 2)

### Issue: Embedding Generation OOM (Out of Memory)

**Symptom**: `RuntimeError: MPS backend out of memory`

**Solution**:
1. Reduce batch size: Set `SEMANTIC_EMBEDDING_BATCH_SIZE=8` in `.env`
2. Close other applications to free RAM
3. Use CPU instead: `SEMANTIC_EMBEDDING_DEVICE=cpu` (slower but more stable)

### Issue: Slow Indexing (>1 hour for 1247 chunks)

**Symptom**: Indexing takes longer than expected

**Solution**:
1. Verify MPS acceleration: Check device in logs (should show "device: mps")
2. Increase batch size (if RAM permits): `SEMANTIC_EMBEDDING_BATCH_SIZE=32`
3. Disable verbose logging: Remove `--verbose` flag
4. Check network speed for model download (first run only)
5. **Recommended**: Use backup restore instead (5 minutes vs 25-30 minutes)

### Issue: Frontend Can't Connect to Backend

**Symptom**: "Network Error" or "Failed to fetch" in frontend

**Solution**:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check VITE_API_URL in frontend/.env: Should be `http://localhost:8000`
3. Check browser console for CORS errors
4. Restart both backend and frontend servers

### Issue: Low Search Result Relevance

**Symptom**: Search results don't match query intent

**Solution**:
1. Verify reranker is working: Check both similarity_score and rerank_score in results
2. Increase candidate count: Set `SEMANTIC_RERANKER_CANDIDATE_COUNT=40` in .env
3. Adjust top_k: Set `SEMANTIC_RERANKER_TOP_K=10` for more diverse results
4. Verify embeddings normalized: Should be enabled by default

---

## Development Commands

### Database Management

```bash
# Stop database
docker-compose down

# Stop and remove volumes (destructive - deletes all data!)
docker-compose down -v

# View database logs
docker-compose logs -f postgres-vector

# Create backup
docker exec langgraph-postgres-vector pg_dump -U postgres -d medical_knowledge -Fc > backups/medical_knowledge-$(date +%Y%m%d-%H%M%S).dump

# Restore from specific backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-20251105-101823.dump
```

### Indexing Management

```bash
# Check indexing version
python -m src.embeddings.cli version

# Re-index all documents (skip existing)
python -m src.embeddings.cli index --input data/chunking_final --skip-existing

# Force re-index all documents
python -m src.embeddings.cli index --input data/chunking_final --no-skip-existing
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/integration/
pytest tests/unit/

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Next Steps

After completing this quickstart:

1. **Explore the API**: Read [API Contracts](./contracts/) documentation
2. **Customize Retrieval**: Modify retrieval strategy in app/config.py
3. **Monitor Performance**: Add logging and metrics collection
4. **Optimize HNSW Index**: Tune `m` and `ef_construction` for your dataset
5. **Deploy to Production**: Migrate to managed PostgreSQL (AWS RDS, Google Cloud SQL)
6. **Add Hybrid Search**: Implement BM25 + vector search combination

---

## Reference Documentation

- [Feature Specification](./spec.md) - Complete feature design and architecture
- [Implementation Plan](./plan.md) - Development roadmap and milestones
- [Technical Research](./research.md) - Technology evaluation and decisions
- [Data Model](./data-model.md) - Database schema and data structures
- [API Contracts](./contracts/) - API endpoint specifications
- [Requirements Checklist](./checklists/requirements.md) - Implementation requirements

---

## Success Criteria Checklist

- [ ] PostgreSQL with pgvector running in Docker (container: langgraph-postgres-vector)
- [ ] Database contains 1247 indexed chunks from 42 documents
- [ ] Backend server starts successfully on http://localhost:8000
- [ ] Frontend server starts successfully on http://localhost:3000
- [ ] Health check endpoint returns 200: `curl http://localhost:8000/health`
- [ ] Chat endpoint returns grounded answers using semantic search
- [ ] Search queries return results in <100ms (pgvector similarity)
- [ ] Reranking completes in <2s for 20 candidates → top-5 results
- [ ] Frontend displays conversation with session persistence
- [ ] Browser console shows no errors
- [ ] Database storage <50MB for 1247 chunks

**Estimated Total Time**:
- **Quick Start (with backup)**: 5-10 minutes
- **Fresh Install (with indexing)**: 25-40 minutes

---

**Congratulations!** 🎉 You now have a fully functional medical chatbot with semantic search powered by PostgreSQL + pgvector + Qwen3 models.
