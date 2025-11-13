# Quickstart Guide: Cloud-Based Embedding Refactoring

**Branch**: `004-cloud-embedding-refactor` | **Date**: 2025-11-12

## Overview

This guide provides step-by-step instructions for:
1. Setting up embedding providers (local, OpenRouter, Aliyun)
2. Switching between providers via configuration
3. Testing provider functionality
4. A/B testing different embedding models with separate tables

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- API keys for cloud providers (OpenRouter, Aliyun)
- Existing medical chatbot codebase from main branch

## Setup

### 1. Install Dependencies

Update `pyproject.toml` with new dependency (if not already present):

```toml
[tool.poetry.dependencies]
openai = "^1.0.0"  # OpenAI Python client for OpenRouter and Aliyun
```

Install dependencies:

```bash
poetry install
```

### 2. Configure API Keys

Create or update `.env` file in project root:

```bash
# Existing OpenRouter/LLM configuration (reused for OpenRouter embeddings)
OPENAI_API_KEY=your_openrouter_api_key_here
OPENAI_API_BASE=https://openrouter.ai/api/v1

# New: Aliyun DashScope API key (separate from OpenRouter)
DASHSCOPE_API_KEY=your_aliyun_api_key_here

# Embedding provider selection (default: local)
EMBEDDING_PROVIDER=local  # Options: local, openrouter, aliyun

# Table name for vector storage (for A/B testing different models)
TABLE_NAME=vector_chunks  # Examples: qwen_local_vector, qwen_openrouter_vector, text_embedding_v4_vector

# Existing configuration
EMBEDDING_DIM=1024  # All providers use 1024-dim embeddings
```

### 3. Verify Configuration

Check that settings load correctly:

```bash
python -c "
from app.config import settings
print(f'Embedding Provider: {settings.embedding_provider}')
print(f'Table Name: {settings.table_name}')
print(f'Embedding Dimension: {settings.embedding_dim}')
"
```

Expected output:
```
Embedding Provider: local
Table Name: vector_chunks
Embedding Dimension: 1024
```

## Provider Switching Workflows

### Workflow 1: Switch from Local to OpenRouter

**Use Case**: Migrate to cloud API while maintaining same model (Qwen3-Embedding-0.6B)

**Steps**:

1. **Update configuration** (`.env`):
   ```bash
   # Change provider type
   EMBEDDING_PROVIDER=openrouter

   # Ensure OpenRouter API key is set
   OPENAI_API_KEY=your_openrouter_api_key_here

   # Optional: Use different table for A/B testing
   TABLE_NAME=qwen_openrouter_vector
   ```

2. **Create new table** (if using different table name):
   ```bash
   # Connect to PostgreSQL
   psql -U postgres -d medical_knowledge

   # Create table with same schema
   CREATE TABLE qwen_openrouter_vector (
       chunk_id TEXT PRIMARY KEY,
       chunk_text TEXT NOT NULL,
       embedding vector(1024),
       source_document TEXT,
       chapter_title TEXT,
       section_title TEXT,
       summary TEXT,
       token_count INTEGER
   );

   # Create index for fast similarity search
   CREATE INDEX qwen_openrouter_vector_embedding_idx
   ON qwen_openrouter_vector
   USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

3. **Restart service**:
   ```bash
   # Stop current service
   pkill -f uvicorn

   # Start with new provider
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Verify provider switch**:
   ```bash
   # Check logs for provider initialization
   # Should see: "Embedding provider: openrouter"

   # Test embedding generation
   curl -X POST http://localhost:8000/embed \
     -H "Content-Type: application/json" \
     -d '{"text": "What are side effects of aripiprazole?"}'
   ```

5. **Re-index documents** (if using new table):
   ```bash
   # Run indexing script with new provider and table
   python -m src.embeddings.cli index \
     --input data/chunking_final \
     --verbose
   ```

**Expected Behavior**:
- Embeddings generated via OpenRouter API (same Qwen3 model)
- Results stored in new table (`qwen_openrouter_vector`)
- Retrieval queries use new table
- >95% retrieval overlap with local provider for identical queries

---

### Workflow 2: Switch to Aliyun

**Use Case**: Test Aliyun's text-embedding-v4 embeddings for comparison

**Steps**:

1. **Update configuration** (`.env`):
   ```bash
   EMBEDDING_PROVIDER=aliyun
   DASHSCOPE_API_KEY=your_aliyun_api_key_here
   TABLE_NAME=text_embedding_v4_vector
   ```

2. **Create Aliyun table**:
   ```sql
   CREATE TABLE text_embedding_v4_vector (
       chunk_id TEXT PRIMARY KEY,
       chunk_text TEXT NOT NULL,
       embedding vector(1024),
       source_document TEXT,
       chapter_title TEXT,
       section_title TEXT,
       summary TEXT,
       token_count INTEGER
   );

   CREATE INDEX text_embedding_v4_vector_embedding_idx
   ON text_embedding_v4_vector
   USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

3. **Restart service and re-index**:
   ```bash
   # Restart with new provider
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000

   # Re-index documents
   python -m src.embeddings.cli index \
     --input data/chunking_final \
     --verbose
   ```

4. **Test retrieval**:
   ```bash
   curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "What are the side effects of aripiprazole?", "top_k": 5}'
   ```

---

## A/B Testing Workflow

**Scenario**: Compare retrieval quality between local Qwen3, OpenRouter Qwen3, and Aliyun text-embedding-v4

### Step 1: Index Same Corpus with All Providers

**Local Qwen3**:
```bash
EMBEDDING_PROVIDER=local
TABLE_NAME=qwen_local_vector
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m src.embeddings.cli index --input data/chunking_final
```

**OpenRouter Qwen3**:
```bash
EMBEDDING_PROVIDER=openrouter
TABLE_NAME=qwen_openrouter_vector
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m src.embeddings.cli index --input data/chunking_final
```

**Aliyun**:
```bash
EMBEDDING_PROVIDER=aliyun
TABLE_NAME=text_embedding_v4_vector
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m src.embeddings.cli index --input data/chunking_final
```

### Step 2: Run Comparison Queries

Create test query script (`scripts/compare_providers.py`):

```python
import asyncio
from app.core.postgres_retriever import PostgreSQLRetriever
from app.db.connection import get_pool, close_pool
from app.config import settings

async def compare_providers():
    pool = await get_pool()

    test_queries = [
        "What are the side effects of aripiprazole?",
        "How does aripiprazole work?",
        "Aripiprazole dosage for schizophrenia",
    ]

    tables = ["qwen_local_vector", "qwen_openrouter_vector", "text_embedding_v4_vector"]

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")

        for table in tables:
            # Update config to use specific table
            settings.table_name = table

            retriever = PostgreSQLRetriever(pool)
            results = await retriever.search(query, top_k=5)

            print(f"\n{table}:")
            for i, doc in enumerate(results[:3], 1):
                print(f"  {i}. {doc.metadata['chunk_id']} (score: {doc.metadata.get('score', 'N/A')})")

    await close_pool()

asyncio.run(compare_providers())
```

Run comparison:
```bash
poetry run python scripts/compare_providers.py
```

### Step 3: Analyze Results

**Metrics to Compare**:
- **Retrieval overlap**: How many top-5 results are identical across providers
- **Response time**: Latency differences (local < OpenRouter < Aliyun expected)
- **Relevance**: Manual review of result quality (medical accuracy, context match)

**Example Output**:
```
Query: What are the side effects of aripiprazole?
================================================================================

qwen_local_vector:
  1. aripiprazole_chunk_042 (score: 0.92)
  2. antipsychotic_effects_chunk_018 (score: 0.87)
  3. adverse_reactions_chunk_056 (score: 0.85)

qwen_openrouter_vector:
  1. aripiprazole_chunk_042 (score: 0.91)  # 95%+ overlap
  2. antipsychotic_effects_chunk_018 (score: 0.86)
  3. adverse_reactions_chunk_056 (score: 0.84)

text_embedding_v4_vector:
  1. aripiprazole_chunk_042 (score: 0.89)
  2. drug_interactions_chunk_073 (score: 0.83)  # Different model, different top-3
  3. antipsychotic_effects_chunk_018 (score: 0.82)
```

---

## Troubleshooting

### Issue: Service fails to start with "Invalid API key"

**Symptom**:
```
RuntimeError: OpenRouter authentication failed: Invalid API key
```

**Solution**:
1. Check `.env` file has correct API key variable name
2. For OpenRouter: `OPENAI_API_KEY`
3. For Aliyun: `DASHSCOPE_API_KEY`
4. Verify key format (no extra whitespace, quotes removed)
5. Test API key with curl:
   ```bash
   # OpenRouter
   curl https://openrouter.ai/api/v1/embeddings \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "qwen/qwen3-embedding-0.6b", "input": "test"}'

   # Aliyun
   curl https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "text-embedding-v4", "input": "test", "dimensions": 1024}'
   ```

---

### Issue: Dimension mismatch error

**Symptom**:
```
ValueError: Provider aliyun returns 1024-dim embeddings,
            but database expects 768-dim. Database re-indexing required.
```

**Solution**:
1. Check `EMBEDDING_DIM` in `.env` matches provider output (should be 1024 for all)
2. Verify database vector column dimension:
   ```sql
   SELECT column_name, data_type, udt_name
   FROM information_schema.columns
   WHERE table_name = 'your_table_name' AND column_name = 'embedding';
   ```
3. If mismatch, either:
   - Update `EMBEDDING_DIM` to match database
   - Or recreate table with correct dimension

---

### Issue: Slow indexing with cloud providers

**Symptom**:
- Local Qwen3: ~16 chunks/batch (fast)
- OpenRouter: ~5 chunks/batch (slow)
- Aliyun: ~3 chunks/batch (slowest)

**Solutions**:
1. **Enable batch processing parallelization** (if supported):
   - Use multiple workers for indexing
   - Process batches in parallel with asyncio

2. **Increase batch size** (if provider allows):
   - OpenRouter: Try batch_size=100 (no documented limit)
   - Aliyun: Try batch_size=100 (no documented limit)

3. **Run indexing overnight for large corpora**:
   ```bash
   nohup python -m src.embeddings.cli index \
     --input data/chunking_final \
     --verbose > indexing.log 2>&1 &
   ```

---

## Testing Provider Implementation

### Unit Tests

Test provider interface compliance:

```bash
# Test local provider
pytest tests/unit/test_local_encoder.py -v

# Test OpenRouter provider
pytest tests/integration/test_openrouter_provider.py -v

# Test Aliyun provider
pytest tests/integration/test_aliyun_provider.py -v

# Test provider factory
pytest tests/unit/test_embedding_factory.py -v
```

### Integration Tests

Test end-to-end retrieval with different providers:

```bash
# Test provider switching
pytest tests/integration/test_provider_switching.py -v
```

### Contract Tests

Verify all providers implement EmbeddingProvider protocol:

```bash
pytest tests/contract/test_embedding_provider_interface.py -v
```

---

## Next Steps

After completing this quickstart:

1. **Phase 2 Implementation**: Run `/speckit.tasks` to generate implementation task list
2. **TDD Workflow**: Write contract tests FIRST, then implement providers
3. **Manual Testing**: Use test query scripts to compare providers
4. **Production Deployment**: Choose optimal provider based on cost, latency, and retrieval quality

For detailed implementation guidance, see:
- `research.md`: Technology decisions and API integration patterns
- `data-model.md`: Entity definitions and relationships
- `contracts/`: API schemas and protocol definitions
- `tasks.md`: Step-by-step implementation tasks (generated by `/speckit.tasks`)
