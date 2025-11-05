# Quickstart Guide

Get the medical chatbot running in 5-10 minutes.

**Target Audience**: New developers setting up the system for the first time
**Time to Complete**: 5-10 minutes (with backup) or 25-40 minutes (fresh install)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.11+** installed
- **Docker** and **Docker Compose** installed
- **Node.js 18+** and **npm/yarn** (for frontend)
- **OpenRouter API Key** for LLM calls

---

## Quick Setup Overview

**Two paths to get started:**

1. **Quick Start (Recommended)**: Restore from backup → 5-10 minutes
2. **Fresh Install**: Create schema + index documents → 25-40 minutes

Both paths lead to the same result: a fully functional medical chatbot with semantic search.

---

## Step 1: Environment Setup

### 1.1 Install Python Dependencies

```bash
# Install all dependencies from requirements.txt
pip install -r requirements.txt
```

### 1.2 Configure Environment Variables
We are not using .env to set the environment variable now.
I am using conda so I set these variables in the conda env directly.

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

# The rest of the settings can use defaults from .env.example
```

---

## Step 2: Database Setup

### Option A: Quick Start - Restore from Backup (RECOMMENDED - 5 minutes)

This is the fastest way to get started. The backup includes schema + pre-indexed chunks.
Please download the `medical_knowledge-latest.dump` from the shared drive.

```bash
# 1. Start PostgreSQL container
docker-compose up -d

# 2. Verify container is running
docker ps | grep langgraph-postgres-vector
# Expected: Container "langgraph-postgres-vector" running on port 5432

# 3. Restore database from backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# Expected output:
# ✅ PostgreSQL setup and restore complete!
# 📊 Database Statistics:
#    Total chunks: 1247
#    Total documents: 42
```

**You're done with database setup!** Skip to Step 3.

### Option B: Fresh Install - Create Schema + Index Documents (25-40 minutes)

Use this if you want to index fresh documents or the backup is not available.

```bash
# 1. Start PostgreSQL container
docker-compose up -d

# 2. Create database schema
python -m app.db.schema

# Expected output:
# ✓ Created extension: vector
# ✓ Created table: vector_chunks (1024-dim embeddings)
# ✓ Created index: idx_embedding_cosine (HNSW)

# 3. Index documents (20-30 minutes on Apple Silicon with MPS)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --device mps \
  --batch-size 16 \
  --verbose

# Expected: ~1247 chunks indexed successfully
```

---

## Step 3: Start Backend Server

```bash
# Start FastAPI + LangGraph backend
uvicorn app.main:app --reload --port 8000
```

**Backend is now running on http://localhost:8000**

### Verify Backend

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"0.1.0"}
```

---

## Step 4: Start Frontend Server

Open a **new terminal** window:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
npm install

# Configure frontend environment
cp .env.example .env
# Verify VITE_API_URL=http://localhost:8000

# Start development server
npm run dev

# Expected output:
# ➜  Local:   http://localhost:3000/
```

**Frontend is now running on http://localhost:3000**

---

## Access the Application

1. Open your browser to **http://localhost:3000**
2. You should see the medical chatbot interface
3. Try asking: "What are the side effects of aripiprazole?"
4. Observe the agent routing and responses

**Available endpoints:**
- Frontend UI: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Troubleshooting

### Database Connection Refused

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
1. Verify Docker container running: `docker ps | grep langgraph-postgres-vector`
2. Check port 5432 available: `lsof -i :5432`
3. Restart container: `docker-compose restart postgres-vector`

### Backend Fails to Start - "No documents indexed"

**Symptom**: Backend fails with error "No documents indexed"

**Solution**:
1. Verify database has data:
   ```bash
   docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT COUNT(*) FROM vector_chunks;"
   ```
2. If count is 0, restore from backup or run indexing (see Step 2)

### MPS Device Not Available (Apple Silicon only)

**Symptom**: `torch.backends.mps.is_available()` returns `False`

**Solution**:
1. Verify macOS version ≥ 12.3: `sw_vers`
2. Update PyTorch: `pip install --upgrade torch`
3. Fallback to CPU: Set `SEMANTIC_EMBEDDING_DEVICE=cpu` and `SEMANTIC_RERANKER_DEVICE=cpu` in `.env`

### Frontend Can't Connect to Backend

**Symptom**: "Network Error" or "Failed to fetch" in frontend

**Solution**:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check VITE_API_URL in `frontend/.env`: Should be `http://localhost:8000`
3. Restart both backend and frontend servers

---

## Next Steps

**You now have a fully functional medical chatbot running!** 🎉

For advanced features, testing, and development workflows:

- **Testing Guide**: [specs/002-semantic-search/testing.md](specs/002-semantic-search/testing.md)
- **Developer Guide**: [specs/002-semantic-search/developer-guide.md](specs/002-semantic-search/developer-guide.md)
- **Feature Specification**: [specs/002-semantic-search/spec.md](specs/002-semantic-search/spec.md)
- **Architecture Details**: [CLAUDE.md](CLAUDE.md)

---

**Estimated Total Time**:
- **Quick Start (with backup)**: 5-10 minutes
- **Fresh Install (with indexing)**: 25-40 minutes
