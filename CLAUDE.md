# langgraph Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-29

## Active Technologies
- **Python 3.11+** with FastAPI 0.115+, LangGraph 0.6.0, LangChain-Core 0.3+, uvicorn 0.32+
- **Embeddings**: Multi-provider support (local Qwen3, OpenRouter API, Aliyun DashScope) via OpenAI Python client
- **Database**: PostgreSQL 15+ with pgvector extension for vector similarity search
- **ML Models**: transformers, torch (MPS support), sentence-transformers for local embedding generation
- **Streaming**: httpx 0.27+ for async SSE streaming
- **Authentication**: Bearer token with hmac constant-time comparison (stdlib)
- **LLM Chunking**: OpenRouter API, Pydantic 2.x, Tiktoken, Typer CLI
- **PostgreSQL**: pgvector + pg_trgm extensions (005-multi-query-keyword-search)
- **Python 3.11+**: LangChain-Core 0.3+, LangChain-OpenAI, Pydantic 2.x, pytest (006-centralized-llm)

## Project Structure

```text
src/
  chunking/                 # Document chunking module (2-phase architecture)
    structure_analyzer.py   # Phase 1: Structure analysis
    chunk_extractor.py      # Phase 2: Chunk extraction
    chunking_pipeline.py    # Main orchestrator
    cli.py                  # Command-line interface
    models.py               # Data models
    llm_provider.py         # LLM API client
    cache_store.py          # Caching layer
    metadata_validator.py   # Validation utilities
    text_aligner.py         # Coverage validation

app/
  embeddings/               # Cloud embedding refactor (004-cloud-embedding-refactor)
    base.py                 # EmbeddingProvider protocol interface
    factory.py              # Multi-provider factory (local/openrouter/aliyun)
    local_encoder.py        # LocalEmbeddingProvider (Qwen3-Embedding-0.6B on MPS/CUDA/CPU)
    openrouter_provider.py  # OpenRouterEmbeddingProvider (Qwen3-Embedding-0.6B API)
    aliyun_provider.py      # AliyunEmbeddingProvider (text-embedding-v4 API)
    utils.py                # Retry logic, error handling utilities

  core/
    postgres_retriever.py   # PostgreSQL + pgvector retriever
    qwen3_reranker.py       # Qwen3-Reranker-0.6B for reranking

  db/
    schema.py               # Database schema and migrations
    connection.py           # Connection pooling with asyncpg

tests/
  chunking/                 # Chunking tests
    unit/                   # Unit tests
    integration/            # Integration tests
    contract/               # Contract tests
```

## Authentication Setup (001-api-bearer-auth)

### Quick Start

**1. Generate API Token**:
```bash
# Generate 64-character hex token (256-bit entropy)
openssl rand -hex 32
```

**2. Configure Environment Variable**:
```bash
# Add to .env file
echo 'API_BEARER_TOKEN="your-generated-token-here"' >> .env
```

**3. Start Service**:
```bash
# Service will validate token at startup
python -m app.main
```

**Expected Startup Log**:
```
INFO:     Validating API Bearer Token configuration...
INFO:     ✅ API Bearer Token validated (64 characters)
```

### Making Authenticated Requests

**With Valid Token** (succeeds):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer your-generated-token-here" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Hello"}'
```

**Without Token** (fails with 401):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Hello"}'
# Returns: {"detail": "Missing Authorization header", "error_code": "MISSING_TOKEN"}
```

### Token Requirements

- **Format**: Hexadecimal characters only (0-9, a-f, A-F)
- **Length**: Minimum 64 characters (enforced by Pydantic validator)
- **Entropy**: 256-bit minimum for security
- **Storage**: Use .env file (already in .gitignore)

### Token Rotation

```bash
# 1. Generate new token
openssl rand -hex 32

# 2. Update .env
export API_BEARER_TOKEN="new-token-here"

# 3. Restart service (old token invalidated immediately)
python -m app.main
```

### Troubleshooting

**"Field required" error**:
```bash
# Verify token is set
echo $API_BEARER_TOKEN

# If empty, set it
export API_BEARER_TOKEN=$(openssl rand -hex 32)
```

**"Must be at least 64 hexadecimal characters"**:
```bash
# Regenerate with correct length
export API_BEARER_TOKEN=$(openssl rand -hex 32)  # 32 bytes = 64 hex chars
```

For detailed setup guide, see: `specs/001-api-bearer-auth/quickstart.md`

## Commands

### Chunking Commands

#### Full Pipeline (2-Phase Processing)

```bash
# Process a single document
python -m src.chunking.cli process --input chapter.txt --output output/

# Process a folder of documents
python -m src.chunking.cli process --input book_chapters/ --output output/

# Customize models (2-phase architecture)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --structure-model openai/gpt-4o \
  --extraction-model google/gemini-2.0-flash-exp \
  --max-tokens 1000 \
  --log-level DEBUG

# Force reprocessing (bypass cache)
python -m src.chunking.cli process \
  --input chapter.txt \
  --output output/ \
  --redo
```

#### Phase 1: Structure Analysis

Run structure analysis independently. Outputs structure JSON with sections and summaries.

```bash
# Analyze a single document
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --model openai/gpt-4o \
  --max-tokens 1000

# Analyze multiple documents
python -m src.chunking.cli analyze \
  --input book_chapters/ \
  --output analysis/ \
  --format jsonl

# Include token consumption statistics
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --stats

# Force reanalysis (bypass cache)
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --redo

# Output formats: json (default), jsonl, yaml
python -m src.chunking.cli analyze \
  --input chapter.txt \
  --output analysis/ \
  --format yaml
```

**Use Cases**:
- Manual structure review before chunk extraction
- Cost optimization (expensive model for structure, cheap for extraction)
- A/B testing different extraction models with same structure
- Debugging Phase 1 independently

#### Phase 2: Chunk Extraction

Run chunk extraction using pre-analyzed structure. Requires structure JSON from analyze command.

```bash
# Extract chunks using analyzed structure
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --model google/gemini-2.0-flash-exp

# Skip validation (faster but risky)
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --no-validate

# Custom coverage threshold (default: 0.99 = 99%)
python -m src.chunking.cli extract \
  --input chapter.txt \
  --structure analysis/chapter_structure.json \
  --output chunks/ \
  --min-coverage 0.95
```

**Use Cases**:
- Human-in-the-loop: review structure before extraction
- Cost optimization: reuse structure, try different extraction models
- Debugging Phase 2 independently
- Batch extraction with single structure analysis

#### Quality Validation

Validate structure or chunks for completeness and quality.

```bash
# Validate structure JSON
python -m src.chunking.cli validate structure_output.json --type structure

# Validate chunks JSONL
python -m src.chunking.cli validate chunks_output.jsonl --type chunks

# Auto-detect type from filename
python -m src.chunking.cli validate chapter_structure.json  # Auto: structure
python -m src.chunking.cli validate chapter_chunks.jsonl   # Auto: chunks

# Validate chunks with coverage check
python -m src.chunking.cli validate \
  chunks_output.jsonl \
  --type chunks \
  --document-path chapter.txt

# Strict mode (treat warnings as errors)
python -m src.chunking.cli validate \
  structure_output.json \
  --strict
```

**Exit Codes**:
- `0`: Validation passed
- `3`: Validation failed (errors found)

**Use Cases**:
- Pre-deployment quality checks
- Debugging malformed outputs
- Coverage verification
- CI/CD pipeline integration

### Semantic Search Commands

#### Database Setup

**Start PostgreSQL with pgvector extension**:

```bash
# Start PostgreSQL Docker container
docker-compose up -d

# Verify container is healthy
docker ps
# Should show: langgraph-postgres-vector (healthy)

# View logs
docker-compose logs -f postgres-vector

# Stop container
docker-compose down

# Stop and remove volumes (destructive)
docker-compose down -v
```

**Run database migration**:

```bash
# Create vector_chunks table and indexes (reads defaults from .env)
python -m src.db.schema_cli migrate

# Or override specific values
python -m src.db.schema_cli migrate \
  --database my_database \
  --embedding-dim 1024
```

**Verify database setup**:

```bash
# Connect to PostgreSQL
docker exec -it langgraph-postgres-vector psql -U postgres -d medical_knowledge

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Check vector_chunks table
\d vector_chunks

# Check indexes
\di
```

#### Indexing Commands

**Index documents (batch processing)**:

```bash
# Index all chunks from data directory (uses defaults)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --verbose

# Index with custom parameters
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --model-name Qwen/Qwen3-Embedding-0.6B \
  --device mps \
  --batch-size 32 \
  --max-length 1024

# Skip already indexed chunks (default behavior)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --skip-existing

# Disable embedding normalization
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --no-normalize
```

**Check indexing version**:

```bash
python -m src.embeddings.cli version
```

#### Search Testing

**Test semantic search in Python**:

```python
import asyncio
from app.core.postgres_retriever import PostgreSQLRetriever
from app.db.connection import DatabasePool

async def test_search():
    async with DatabasePool() as pool:
        retriever = PostgreSQLRetriever(pool)

        # Search with reranking (default)
        results = await retriever.search("aripiprazole mechanism of action", top_k=5)

        for i, doc in enumerate(results, 1):
            print(f"\n{i}. {doc.metadata['chunk_id']}")
            print(f"   Score: {doc.metadata['rerank_score']:.4f}")
            print(f"   Content: {doc.content[:200]}...")

asyncio.run(test_search())
```

**Smoke test (comprehensive pipeline validation)**:

```bash
# Run all tests: parse JSON, generate embeddings, database insertion
python test_indexing.py

# Tests include:
# 1. Parse chunk file (no database required)
# 2. Generate embeddings with Qwen3-Embedding-0.6B
# 3. Insert into PostgreSQL with duplicate handling
```

**Expected performance**:
- Indexing: ~16 chunks/batch on MPS (M1/M2/M3)
- Search: <100ms pgvector similarity search
- Reranking: <2s for 20 candidates (Qwen3-Reranker-0.6B)
- Total search latency: <2.1s for top-5 results

### Development Commands

```bash
# Run tests
pytest tests/chunking/
pytest tests/chunking/ --cov=src.chunking --cov-report=html

# Type checking
mypy src/chunking/ --ignore-missing-imports

# Linting
ruff check src/chunking/
ruff check src/chunking/ --fix

# Format code
black src/chunking/ tests/chunking/
```

## Code Style

Python 3.11+: Follow PEP 8, use type hints, Google-style docstrings
- Line length: 100 characters
- Use Pydantic models for data structures
- Fail-fast error handling with custom exceptions
- Comprehensive docstrings for all public methods

## Recent Changes

### Centralized LLM Instance Management (2025-11-13)

**Refactored LLM instance creation to singleton pattern with centralized management**:

**Architecture Changes**:
- **Centralized Module**: Created `app/llm/` module for LLM instance management
- **Singleton Pattern**: Pre-configured instances (`response_llm`, `internal_llm`) with module-level initialization
- **Factory Function**: `create_llm()` moved to `app/llm/factory.py` with environment-based switching
- **Fail-Fast Migration**: Deleted `app/agents/base.py` to force immediate adoption

**Configuration**:
- **response_llm**: User-facing responses (temp=0.7, streaming enabled)
- **internal_llm**: Internal operations (temp=1.0, streaming disabled, tags=["internal-llm"])
- **Automatic Switching**: `TESTING=true` → FakeChatModel, `TESTING=false` → ChatOpenAI

**Test Infrastructure**:
- **Response Registry**: Centralized fake response patterns in `tests/fakes/response_registry.py`
- **Organized Patterns**: Supervisor classification, RAG classification, medical responses, emotional responses
- **Maintainable Testing**: Adding new patterns requires only updating registry

**Refactored Files**:
- **Created**: `app/llm/__init__.py`, `app/llm/factory.py`, `app/llm/instances.py`, `tests/fakes/response_registry.py`, `tests/unit/llm/test_instances.py`
- **Updated**: `app/agents/supervisor.py`, `app/agents/emotional_support.py`, `app/agents/rag_agent.py`, `app/retrieval/advanced.py`, `tests/fakes/fake_chat_model.py`
- **Deleted**: `app/agents/base.py`

**Benefits**:
- **Zero Configuration Duplication**: 5 `create_llm()` calls → 1 centralized factory (80% reduction)
- **Simplified Testing**: Automatic test/prod switching with zero test infrastructure changes
- **Type Safety**: `BaseChatModel` protocol ensures compatibility across FakeChatModel and ChatOpenAI
- **Maintainable Responses**: Centralized registry makes adding new test patterns trivial
- **100% Test Coverage**: All LLM module functions have complete coverage

### CLI Tools Refactoring - Moved to src/ with .env Integration (2025-11-13)

**Moved database CLI tools from app/ to src/ with automatic .env configuration loading**:

- **Architecture Change**: Separated CLI commands from application code
  - Moved CLI commands from `app/db/schema.py` to `src/db/schema_cli.py`
  - Core schema functions remain in `app/db/schema.py` for application use
  - Follows project convention: CLI tools in `src/`, application code in `app/`

- **Improved User Experience**: Automatic configuration from .env
  - Reads `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from .env
  - No need to specify connection parameters for every command
  - Can still override any parameter via command-line flags

- **New Command Path**: `python -m src.db.schema_cli` (was: `python -m app.db.schema`)
  - `migrate`: Create database and schema
  - `verify`: Verify schema setup
  - `stats`: Display database statistics
  - `enable-keyword-search`: Enable pg_trgm for keyword search
  - `drop`: Drop all indexes and tables (destructive)

**Examples**:
```bash
# Use defaults from .env
python -m src.db.schema_cli migrate
python -m src.db.schema_cli enable-keyword-search

# Override specific values
python -m src.db.schema_cli migrate --database my_db --embedding-dim 8192
python -m src.db.schema_cli enable-keyword-search --table text-embedding-v4
```

**Files Modified**:
  - `app/db/schema.py`: Removed CLI commands, kept core schema functions
  - `CLAUDE.md`: Updated all command references

**Files Created**:
  - `src/db/schema_cli.py`: New CLI tool with .env integration
  - `src/db/__init__.py`: Module initialization

### Keyword Search Similarity Threshold Fix (005-multi-query-keyword-search, 2025-11-13)

**Fixed keyword search returning 0 results due to pg_trgm default threshold being too high**:

- **Root Cause**: Default `pg_trgm.similarity_threshold` of 0.3 was too high for short queries against long medical documents
  - "aripiprazole" scored below 0.1 (no matches with 0.3 threshold)
  - "aripiprazole mechanism of action" scored 0.1287 (below 0.3 threshold)
  - Trigram similarity inherently produces low scores for short queries vs. long documents

- **Solution**: Configurable similarity threshold with reasonable default (0.1)
  - Added `keyword_similarity_threshold: float = 0.1` to config.py
  - Changed SQL from `WHERE chunk_text % $1` (uses pg_trgm's 0.3) to `WHERE similarity(chunk_text, $1) > $2` (uses custom threshold)
  - Created GIN index on correct table (`text-embedding-v4`)

- **Threshold Tuning Guidance**:
  - 0.05: More results, more noise
  - 0.1: Balanced - recommended for medical terminology (default)
  - 0.15: Fewer results, higher precision

- **Expected Behavior**:
  - Multi-word queries work well: "aripiprazole mechanism of action" → 4 matches
  - Single-word queries may score too low: "aripiprazole" → 0 matches (expected for trigram similarity)
  - Use multi-word queries for better keyword matching results

**Files Modified**:
  - `app/config.py`: Added `keyword_similarity_threshold` configuration parameter
  - `app/retrieval/advanced.py`: Updated `_keyword_search()` to use custom threshold with `similarity()` function
  - `app/db/schema.py`: Added `--table` parameter to `enable-keyword-search` command

**Debugging Tools Created**:
  - `debug_keyword_search.py`: Full diagnostic tool with --table parameter support
  - `investigate_data.py`: Deep dive into similarity scores and threshold testing
  - `fix_keyword_index.py`: Create GIN index on correct table
  - `test_keyword_fix.py`: Test keyword search with various query patterns
  - `KEYWORD_SEARCH_FIX.md`: Comprehensive fix documentation

### Multi-Query Expansion and Hybrid Search (005-multi-query-keyword-search, 2025-11-13)

**Added intelligent multi-query expansion and hybrid vector+keyword search**:

- **Multi-Query Generation**: AdvancedRetriever now generates 1-10 diverse query variations using LLM
  - Simple queries: 2-3 variations
  - Comparative queries: 5-10 variations covering all entities
  - Strategies: entity decomposition, aspect coverage, perspective variation
  - Configuration: `max_queries` parameter (default: 10)

- **Query Quality Control**: Automatic validation and deduplication
  - Filters malformed queries (empty, punctuation-only)
  - Removes exact duplicates (preserves order)
  - Limits to max_queries threshold
  - Structured logging: filtered count, duplicates count, final count

- **Hybrid Vector+Keyword Search**: pg_trgm trigram-based keyword matching
  - Vector search: HNSW index for semantic similarity
  - Keyword search: GIN index with pg_trgm for lexical matching
  - Parallel execution: asyncio.gather() for all queries
  - Configuration: `ENABLE_KEYWORD_SEARCH` environment variable (default: false)
  - Graceful degradation: Falls back to vector-only if pg_trgm missing

- **Cross-Language Support**: Chinese→English translation in query expansion
  - Accurate medical term translation (阿立哌唑 → aripiprazole)
  - Preserves Latin/English terms in mixed queries (5-HT2A受体 → 5-HT2A receptor)
  - Language detection logging: chinese, mixed_chinese_latin

- **Database Migration**: New CLI command for pg_trgm setup
  - Command: `python -m src.db.schema_cli enable-keyword-search`
  - Creates: pg_trgm extension + GIN index on chunk_text
  - Idempotent: Safe to run multiple times

**Files Modified**:
  - `app/retrieval/advanced.py`: Complete rewrite with multi-query + hybrid search, now uses global `internal_llm`
  - `app/db/schema.py`: Added enable_keyword_search() migration function
  - `app/config.py`: Added enable_keyword_search configuration parameter

**Files Created**:
  - `tests/integration/test_advanced_retriever.py`: Multi-query tests
  - `tests/integration/test_keyword_search.py`: Hybrid search tests
  - `tests/integration/test_cross_language.py`: Cross-language tests
  - `tests/unit/test_query_validation.py`: Query validation unit tests

### API Bearer Authentication (2025-11-12)

**Added secure Bearer token authentication for all API endpoints**:

- **Security-first design**: Constant-time token comparison using `hmac.compare_digest`
- **Strict validation**: 64+ hexadecimal characters (256-bit entropy minimum)

**Configuration**:
  - `API_BEARER_TOKEN`: Required environment variable (validated at startup)
  - Generate: `openssl rand -hex 32` for 64-character token
  - Validation: Pydantic validator enforces format and length requirements

**Files Added**:
  - `app/core/auth/`: Authentication module (bearer_token.py, dependencies.py, logging.py, models.py)
  - `tests/contract/test_auth_contract.py`: Contract tests
  - `tests/integration/test_auth_integration.py`: Integration tests
  - `tests/unit/test_bearer_token.py`: Unit tests

### Cloud Embedding Refactor - Multi-Provider Architecture (2025-11-12)

**Refactored embedding system from `src/embeddings` to `app/embeddings` with multi-provider support**:

**Architecture**:
  - **Protocol-based design**: `EmbeddingProvider` ABC defines common interface
  - **Factory pattern**: `EmbeddingProviderFactory` creates providers based on `EMBEDDING_PROVIDER` environment variable
  - **Three providers**: Local (Qwen3 on MPS/CUDA/CPU), OpenRouter API, Aliyun DashScope
  - **Unified interface**: `encode()`, `get_provider_name()` - dimension detected dynamically from embeddings

**Providers**:
  - **LocalEmbeddingProvider**: Configurable HuggingFace models (default: Qwen3-Embedding-0.6B, 1024-dim) on MPS/CUDA/CPU
  - **OpenRouterEmbeddingProvider**: Configurable OpenRouter models (default: qwen/qwen3-embedding-0.6b, 1024-dim)
  - **AliyunEmbeddingProvider**: Configurable Aliyun DashScope models (default: text-embedding-v4, 1024-dim dense format)

**Configuration**:
  - `EMBEDDING_PROVIDER`: "local", "openrouter", or "aliyun"
  - `EMBEDDING_MODEL`: Model name/identifier (provider-specific format)
  - `OPENAI_API_KEY`: Required for OpenRouter provider
  - `ALIYUN_API_KEY`: Required for Aliyun provider
  - `device`: Device for local provider (mps/cuda/cpu, auto-fallback)
  - No API keys required for local provider

**Benefits**:
  - **Zero vendor lock-in**: Switch providers via environment variable
  - **Model flexibility**: Configure models per provider via `--model` parameter
  - **Dynamic dimensions**: No hardcoded dimensions, supports any embedding size
  - **Cost flexibility**: Local (free, hardware-dependent) vs Cloud (pay-per-use, scalable)
  - **Performance trade-offs**: Local (fast, requires GPU) vs Cloud (consistent, network latency)
  - **Reliability**: Retry logic with exponential backoff, batch processing, error handling

**Migration**:
  - Eliminated: `src/embeddings/` module (encoder.py, indexer.py, cli.py, models.py)
  - Created: `app/embeddings/` module with protocol-based design
  - Test coverage: 56 passing tests (contract, integration, unit), 66.8% coverage for app.embeddings
  - Type safety: mypy type checking with minimal errors

**Usage**:
```python
from app.embeddings.factory import create_embedding_provider
from app.config import settings

# Create provider with explicit parameters from settings
provider = create_embedding_provider(
    provider_type=settings.embedding_provider,
    embedding_model=settings.EMBEDDING_MODEL,  # Model name is now actually used!
    device=settings.device,
    batch_size=10,  # Optional, defaults to 10
    openai_api_key=settings.openai_api_key,
    aliyun_api_key=settings.aliyun_api_key,
)

# Unified interface across all providers
embedding = provider.encode("test query")  # Returns np.ndarray (dimension depends on model)
embeddings = provider.encode(["query 1", "query 2"])  # Returns List[np.ndarray]

# Get dimension dynamically from actual embedding
dimension = len(embedding)  # No hardcoded get_embedding_dimension() method!
```

### Router-Based RAG Architecture - Classification and Routing (2025-11-13)

**Refactored RAG agent from tool-based to router-based architecture with intelligent classification**:

  - **classify**: LLM-based intent classification ("retrieve" vs. "respond")
  - **retrieve**: Full RAG workflow (retrieve + format + generate)
  - **respond**: Direct response without retrieval (greetings, thank yous, etc.)

  - **Full State Access**: Retrieval node receives complete conversation state, not just string queries
  - **Type Safety**: Restores `List[BaseMessage]` interface for history-aware retrieval
  - **Intelligent Routing**: LLM classifies whether query needs knowledge base lookup
  - **Efficiency**: Skips unnecessary retrieval for conversational queries

  - `app/agents/rag_agent.py`: Complete rewrite with `create_rag_agent()` factory function
  - Classification uses low temperature (0.1) for consistent routing decisions
  - Generation uses higher temperature (1.0) for creative, natural responses
  - Conditional edges use state-based routing (`lambda state: state["__routing"]`)

  - `app/tools/medical_search.py`: Obsolete tool-based implementation removed
  - `app/tools/__init__.py`: Updated to reflect tool deletion

  - Comprehensive test suite verified all routing paths work correctly
  - Fixed FakeChatModel classification with word boundary matching
  - Validated history-aware retrieval with multi-turn conversations

  - Updated: `app/agents/rag_agent.py` (complete rewrite), `app/tools/__init__.py`
  - Deleted: `app/tools/medical_search.py`
  - Enhanced: `tests/fakes/fake_chat_model.py` (classification support, word boundaries)

### Simplified Supervisor - Removed Confidence Scores and Reasoning (2025-11-13)

**Simplified supervisor classification by removing unnecessary complexity**:

  - Supervisor now returns plain text agent name instead of Pydantic model
  - Removed `AgentClassification` model with `reasoning` and `confidence` fields
  - Added `VALID_AGENTS` set for explicit validation
  - Kept stream events for frontend integration

  - **Simpler Implementation**: Easier to debug and maintain
  - **Faster Classification**: No structured output parsing overhead
  - **More Robust**: Explicit validation instead of schema enforcement
  - **Cleaner Logs**: No unnecessary metadata cluttering logs

  - `app/agents/supervisor.py`: Use `llm.invoke()` instead of `llm.with_structured_output()`
  - `app/utils/prompts.py`: Updated to request plain text output only
  - Validation logic explicitly checks against `VALID_AGENTS` set
  - Stream events preserved for routing:started and routing:complete

  - Updated: `app/agents/supervisor.py`, `app/utils/prompts.py`

### History-Aware Retrieval - Conversation Context for Retrievers (2025-11-06)

**Enhanced retriever interface to accept conversation history for context-aware retrieval**:

  - Backward compatible: existing string queries still work
  - Context-aware: pass full conversation history for better retrieval
  - Strategy-specific: each retriever decides how much history to use

  - **SimpleRetriever**: Last message only (`max_history=1`) - fast, simple
  - **RerankRetriever**: Last message only (`max_history=1`) - reranker provides semantic richness
  - **AdvancedRetriever**: Last 5 messages (`max_history=5`) - rich context for LLM query expansion

  - `app/retrieval/utils.py`: New utility module with `extract_query_from_messages()` and `format_message_context()`
  - `app/retrieval/base.py`: Updated `RetrieverProtocol` signature to `Union[str, List[BaseMessage]]`
  - `app/retrieval/simple.py`, `rerank.py`, `advanced.py`: Updated to use message extraction utilities
  - `app/agents/rag_agent.py`: Now passes `state["messages"]` to retriever instead of just query string

  - **Context Resolution**: Handles follow-up questions like "What about children?" with implicit context
  - **Separation of Concerns**: Retrievers encapsulate their own history needs (no longer RAG agent's responsibility)
  - **Enhanced Query Expansion**: AdvancedRetriever uses conversation context for better LLM query variations
  - **Zero Performance Impact**: Simple/Rerank strategies unchanged, Advanced adds ~100-200ms for richer context

  - `tests/unit/test_retrieval_utils.py`: Comprehensive tests for utility functions
  - Verified backward compatibility with string inputs
  - Tested multi-turn conversations with context extraction

  - Created: `app/retrieval/utils.py`, `tests/unit/test_retrieval_utils.py`
  - Updated: `app/retrieval/base.py`, `simple.py`, `rerank.py`, `advanced.py`, `app/agents/rag_agent.py`

### Cache Removal - Output-Based Skip Logic (2025-11-01)

**Removed content-hash caching system and implemented simpler output-file-based skip logic**:

  - Check if structure.json exists → skip Phase 1 if valid
  - Check each chunk file → skip that chunk if valid (granular skip logic)
  - `--redo` flag forces reprocessing regardless of existing files

  - **Simplicity**: ~200 lines of cache code removed
  - **Transparency**: Output files are the source of truth (no hidden cache layer)
  - **Disk Space**: No duplicate storage (cache + output)
  - **Resumability**: Can resume interrupted extractions at chunk level
  - **Granular Control**: Delete specific chunk to regenerate just that section

  - **Phase 1 (Structure Analysis)**: Checks `{output_dir}/{document_id}/{document_id}_structure.json`
  - **Phase 2 (Chunk Extraction)**: Checks each `{document_id}_chunk_{NNN}.json` individually
  - **Validation**: Attempts to parse files before skipping (regenerates if corrupted)
  - **--redo flag**: Bypasses all skip checks and forces full reprocessing

  - **Phase 1 (Structure Analysis)**: 3 retries with 2s, 4s, 8s backoff
  - **Phase 2 (Chunk Extraction)**: 3 retries with 2s, 4s, 8s backoff
  - Handles LLM API timeouts and transient failures gracefully
  - Works seamlessly with skip logic (already-extracted chunks are skipped on retry)

  - `cli.py`: Removed FileCacheStore, updated --redo help text
  - `chunking_pipeline.py`: Removed cache_store parameter, added chunk extraction retry logic
  - `structure_analyzer.py`: Added output-based skip logic for structure files
  - `chunk_extractor.py`: Added granular per-chunk skip logic

  - `cache_store.py` → `research/cache_store.py` with deprecation notice
  - Research imports updated to reflect new location

  - `cache --stats`: No longer available
  - `cache --clear`: No longer needed

### V3 Experimental Architecture - Cache-Optimized Extractors (2025-10-31 - Late Evening)

**Created experimental chunk extractors optimized for LLM prompt caching**:

  - Metadata now derived from Phase 1 structure analysis (no LLM call needed!)
  - Single source of truth - perfect consistency between phases
  - Phase 1 already has all metadata: chapter_title, section_title, summary

  - Extract text → Generate contextual prefix
  - Metadata derived from Phase 1 structure
  - Cache efficiency: ~50-60%

  - Extract text + prefix merged in single call
  - Tagged output format for robust parsing
  - Cache efficiency: ~80-90%

  - Handles dirty text (tabs, newlines, special characters)
  - Clear field boundaries: `[TAG]content[/TAG]`
  - Robust error detection and parsing

  - `subsection_title`: Changed from `Optional[str]` to `List[str]`
  - Now captures ALL subsections, not just first one
  - Better hierarchical representation for RAG retrieval

  - `tag_parser.py`: XML-style tag parsing utilities
  - `chunk_extractor_v3_experimental.py`: V3A & V3B implementations
  - `V3_EXPERIMENTAL_README.md`: Comprehensive usage guide
  - `PROMPT_CACHING_TODO.md`: Implementation guide for prompt caching

  - Current: Document-first prompt structure (correct for caching)
  - Missing: `cache_control` breakpoints for actual caching
  - Remaining: Implement multipart message format with cache breakpoints
  - Expected savings: 80-90% cost reduction on multi-section documents


### Empty Field Sentinel Fix (2025-10-31 - Evening)

**Replaced invisible tabs with explicit [EMPTY] sentinel for title-only sections**:

  - Invisible characters easily destroyed by `.strip()` or other text processing
  - Difficult to debug (can't see empty fields in logs)
  - Ambiguous for LLMs (unclear if "empty" means "skip column" or "output nothing")

  - **Prompt Update**: Instruct LLM to output `[EMPTY]` for empty start_words/end_words
  - **Parser Update**: Convert `[EMPTY]` to empty string when creating SectionV2 objects
  - **Example**: `Title\t1\tROOT\tSummary\t[EMPTY]\t[EMPTY]` (6 columns, last two explicitly empty)

  - ✅ Explicit > Implicit (Python zen) - visible in logs and debugging
  - ✅ No whitespace ambiguity - can safely use `.strip()` everywhere
  - ✅ LLM-friendly - clearer instruction than "preserve invisible characters"
  - ✅ Robust - won't be destroyed by any text processing

  - Production errors eliminated: 4-column vs 6-column mismatch
  - Parser correctly handles empty fields with explicit sentinel

  - Updated: structure_analyzer_v2.py (prompt + parser with [EMPTY] conversion)
  - Updated: structure_analyzer.py (reverted unnecessary .rstrip() change for consistency)

### Title-Only Section Support (2025-10-31 - Morning)

**Enhanced SectionV2 to support title-only sections**:

  - Title-only sections (headers with no body content) now represented naturally as empty strings
  - Eliminates forced LLM hallucination when no content exists
  - Structure analyzer V2 prompt updated to guide LLMs to output empty values appropriately

  - Sections with both `start_words=""` and `end_words=""` are skipped
  - No chunk generated for title-only sections (content is in subsections)
  - Prevents extraction errors and unnecessary LLM API calls

  - `SectionV2.start_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - `SectionV2.end_words`: Changed from `Field(..., min_length=1)` to `Field(default="")`
  - Default values allow omitting fields entirely in section creation

  - Test cases cover: normal content, empty fields, default values, mixed sections

  - Updated: models.py, structure_analyzer_v2.py, chunk_extractor_v2.py
  - Tests: tests/chunking/unit/test_utilities.py (added TestSectionV2 class)

### Architecture Redesign (2025-10-30)

**Major architectural changes for 001-llm-contextual-chunking**:

  - Phase 1: Structure Analysis (structure_analyzer.py)
  - Phase 2: Chunk Extraction (chunk_extractor.py)
  - Removed: Phase 2 (boundary_detector.py) and Phase 3 (document_segmenter.py)

  - LLMs extract full text based on title + summary metadata
  - Eliminated unreliable character position output (start_char, end_char)
  - 3 LLM calls per section: extract text → metadata → contextual prefix

  - Cache persists until document content changes
  - SHA256-based cache keys for content addressability
  - Supports `--redo` flag to force reprocessing

  - `analyze`: Run Phase 1 structure analysis independently
  - `extract`: Run Phase 2 chunk extraction with pre-analyzed structure
  - `validate`: Quality validation for structures and chunks
  - Enables human-in-the-loop workflows and cost optimization

  - Removed position fields: `Section.start_char`, `Section.end_char`, `Chunk.character_span`
  - Added `Section.summary` field (10-200 chars) for extraction guidance
  - Deleted `BoundaryType` enum and `SegmentBoundary` model
  - Renamed `BoundaryDetectionError` → `ChunkExtractionError`

  - Updated: models.py, cache_store.py, structure_analyzer.py, chunking_pipeline.py, cli.py
  - Created: chunk_extractor.py
  - Deleted: boundary_detector.py, document_segmenter.py


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
