# Comprehensive Refactoring Guide
**Project**: Medical Chatbot RAG System
**Date**: 2025-11-04
**Goal**: Simplify codebase for POC, fail-fast approach, reduce unnecessary layers

---

## Table of Contents
- [Phase 1: Foundation (Config & Imports)](#phase-1-foundation-config--imports)
- [Phase 2: Comment Out Parenting System](#phase-2-comment-out-parenting-system)
- [Phase 3: Simplify Initialization](#phase-3-simplify-initialization)
- [Phase 4: Create Retrieval Strategies](#phase-4-create-retrieval-strategies)
- [Phase 5: Cleanup & Remove Abstractions](#phase-5-cleanup--remove-abstractions)

---

# Phase 1: Foundation (Config & Imports)

## TICKET-001: Add Missing Config Constants

### Why
Configuration scattered across multiple files. Need centralized config with all constants for retrieval strategies, feature flags, and model preloading.

### Where
- **File**: `app/config.py`
- **Lines**: End of Settings class (after line 58)

### How

**Step 1**: Add retrieval strategy configuration
```python
# Retrieval Strategy Configuration
RETRIEVAL_STRATEGY: str = "simple"  # Options: "simple" | "rerank" | "advanced"
```

**Step 2**: Add model preloading flag
```python
# Model Loading Configuration
PRELOAD_MODELS: bool = False  # True = load at startup, False = lazy load
```

**Step 3**: Add feature flags
```python
# Feature Flags
ENABLE_PARENTING: bool = False  # Temporarily disable parenting system
ENABLE_RETRIES: bool = False  # Enable database retry logic (False for POC)
```

**Step 4**: Add model constants (uppercase convention)
```python
# Model Names (standardized)
EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
RERANKER_MODEL: str = "Qwen/Qwen3-Reranker-0.6B"
```

**Step 5**: Add database URL construction
```python
# Database Configuration
@property
def database_url(self) -> str:
    """Construct database URL from components."""
    return (
        f"postgresql://{self.postgres_user}:{self.postgres_password}"
        f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    )
```

**Step 6**: Update existing field names to uppercase
- Rename `embedding_model_name` → Keep as is (used by Pydantic settings)
- Add uppercase constant: `EMBEDDING_MODEL = embedding_model_name`

### Checklist
- [ ] Add `RETRIEVAL_STRATEGY` constant
- [ ] Add `PRELOAD_MODELS` flag
- [ ] Add `ENABLE_PARENTING` flag
- [ ] Add `ENABLE_RETRIES` flag
- [ ] Add `EMBEDDING_MODEL` constant
- [ ] Add `RERANKER_MODEL` constant
- [ ] Add `database_url` property
- [ ] Test: Import settings and verify all new fields exist
- [ ] Test: Run `python -c "from app.config import settings; print(settings.RETRIEVAL_STRATEGY)"`

---

## TICKET-002: Fix Import Issues in postgres_retriever.py

### Why
Imports scattered inside functions violate Python convention. All imports should be at top of file for clarity and performance.

### Where
- **File**: `app/core/postgres_retriever.py`
- **Lines**: 101 (import os in __init__), 152 (import os in initialize), 378 (import numpy in function), 555 (import numpy in add_documents)

### How

**Step 1**: Move all imports to top of file (after line 18, before logger)

Add to top imports section:
```python
import os
import numpy as np
```

**Step 2**: Remove inline imports

**Line 101-102**: Remove
```python
# Remove this
import os
self.db_url = db_url or os.getenv("DATABASE_URL")
```

**Line 152-153**: Remove
```python
# Remove this
import os
os.environ["DATABASE_URL"] = self.db_url
```

**Line 378-382**: Remove
```python
# Remove this
import numpy as np
if isinstance(embedding, np.ndarray):
```

**Line 555-558**: Remove
```python
# Remove this
import numpy as np
if isinstance(embeddings, np.ndarray):
```

**Step 3**: Verify imports work correctly

### Checklist
- [ ] Add `import os` to top of file
- [ ] Add `import numpy as np` to top of file
- [ ] Remove `import os` from line 101
- [ ] Remove `import os` from line 152
- [ ] Remove `import numpy as np` from line 378
- [ ] Remove `import numpy as np` from line 555
- [ ] Run: `python -c "from app.core.postgres_retriever import PostgreSQLRetriever"` (should not error)
- [ ] Run: `ruff check app/core/postgres_retriever.py` (check for import order)

---

## TICKET-003: Remove Direct .env Reading from postgres_retriever.py

### Why
Configuration should only be read from `settings` object. Direct env var reading bypasses centralized config and creates maintenance issues.

### Where
- **File**: `app/core/postgres_retriever.py`
- **Lines**: 100-114 in __init__

### How

**Step 1**: Simplify __init__ to only use settings

**Current code (lines 100-114)**:
```python
# Get db_url from parameter or environment
import os
self.db_url = db_url or os.getenv("DATABASE_URL")

# Fall back to constructing from POSTGRES_* variables if needed
if not self.db_url:
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_db = os.getenv("POSTGRES_DB")
    pg_user = os.getenv("POSTGRES_USER")
    pg_pass = os.getenv("POSTGRES_PASSWORD")

    if all([pg_db, pg_user, pg_pass]):
        self.db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
```

**Replace with**:
```python
from app.config import settings

# Get db_url from parameter or settings
self.db_url = db_url or settings.database_url
```

**Step 2**: Remove line 152-153 (setting DATABASE_URL env var)

**Current**:
```python
# Parse DATABASE_URL from db_url if needed
import os
os.environ["DATABASE_URL"] = self.db_url
```

**Replace with**: (just pass db_url to pool initialization)
```python
# Connection string will be passed to pool initialization
```

**Step 3**: Update pool initialization to use db_url directly

**Line 149**: Change from:
```python
self.db_pool = DatabasePool(min_size=5, max_size=20)
```

To:
```python
self.db_pool = DatabasePool(min_size=5, max_size=20)
# Note: Pool will read from DATABASE_URL env var via settings
```

### Checklist
- [ ] Import settings at top: `from app.config import settings`
- [ ] Replace lines 100-114 with simplified version using `settings.database_url`
- [ ] Remove lines 152-153 (setting DATABASE_URL)
- [ ] Test: Create retriever with no parameters, verify it uses settings
- [ ] Test: Create retriever with explicit db_url, verify it uses provided value
- [ ] Run: `python -c "from app.core.postgres_retriever import PostgreSQLRetriever; r = PostgreSQLRetriever()"`

---

## TICKET-004: Fix Import Issues in db/connection.py

### Why
Database connection reads env vars directly instead of using settings object. Need centralized configuration.

### Where
- **File**: `app/db/connection.py`
- **Lines**: 64-107 (_load_connection_params method)

### How

**Step 1**: Import settings at top
```python
from app.config import settings
```

**Step 2**: Simplify _load_connection_params method

**Current code (lines 64-107)**:
```python
def _load_connection_params(self) -> dict[str, Any]:
    # Try DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.info("Using DATABASE_URL for connection")
        return {"dsn": database_url}

    # Fall back to individual POSTGRES_* variables
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if not all([database, user, password]):
        raise ValueError(
            "Database configuration missing. Either set DATABASE_URL or "
            "provide POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD"
        )

    logger.info(
        f"Using individual POSTGRES_* variables for connection "
        f"(host={host}, port={port}, database={database}, user={user})"
    )

    return {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
    }
```

**Replace with**:
```python
def _load_connection_params(self) -> dict[str, Any]:
    """Load database connection parameters from settings object.

    Returns:
        Dictionary of connection parameters for asyncpg.create_pool()
    """
    # Use database URL from settings
    return {"dsn": settings.database_url}
```

### Checklist
- [ ] Add `from app.config import settings` to imports
- [ ] Replace _load_connection_params method (lines 64-107)
- [ ] Remove `import os` if no longer needed
- [ ] Test: `python -c "from app.db.connection import DatabasePool; p = DatabasePool()"`
- [ ] Verify connection works: Create pool, initialize, test query

---

# Phase 2: Comment Out Parenting System

## TICKET-005: Comment Out Parenting in main.py

### Why
Temporarily disable parenting system to focus on medication Q&A POC. Will re-enable later via feature flag.

### Where
- **File**: `app/main.py`
- **Lines**: 35-36 (imports), 122-189 (_load_parenting_system), 225-228 (loading), 232-234 (graph building)

### How

**Step 1**: Comment out parenting imports (lines 14-16)
```python
# from app.core.hybrid_retriever import HybridRetriever
# from app.core.reranker import CrossEncoderReranker
```

**Step 2**: Comment out parenting in app_state (lines 35-36)
```python
app_state = {
    "graph": None,
    "session_store": None,
    "retriever": None,
    "db_pool": None,
    # "parenting_retriever": None,
    # "parenting_reranker": None
}
```

**Step 3**: Comment out _load_parenting_system function (lines 122-189)

Add comment block:
```python
# ============================================================================
# PARENTING SYSTEM - TEMPORARILY DISABLED
# ============================================================================
# TODO: Re-enable when settings.ENABLE_PARENTING = True
#
# async def _load_parenting_system() -> tuple[HybridRetriever, CrossEncoderReranker]:
#     """Load pre-computed parenting video embeddings and reranker from disk.
#     ... [rest of function commented out]
#     """
```

**Step 4**: Comment out parenting loading in lifespan (lines 225-228)
```python
# # Load pre-computed parenting embeddings (fail-fast if not found)
# parenting_retriever, parenting_reranker = await _load_parenting_system()
# app_state["parenting_retriever"] = parenting_retriever
# app_state["parenting_reranker"] = parenting_reranker
```

**Step 5**: Update graph building (lines 231-235)
```python
# Build graph with retriever only (parenting disabled)
app_state["graph"] = build_medical_chatbot_graph(
    retriever=retriever,
    # parenting_retriever=parenting_retriever,  # Disabled
    # parenting_reranker=parenting_reranker,    # Disabled
)
logger.info("✅ Medical chatbot graph compiled (medication Q&A only)")
```

**Step 6**: Update success log message (line 237)
```python
logger.info("🎉 Application startup complete! (Parenting system disabled)")
```

### Checklist
- [ ] Comment out hybrid_retriever and reranker imports
- [ ] Comment out parenting fields in app_state dict
- [ ] Comment out entire _load_parenting_system function with TODO
- [ ] Comment out parenting loading in lifespan
- [ ] Update graph building call (remove parenting params)
- [ ] Update success log message
- [ ] Test: `python -m app.main` should start without parenting
- [ ] Test: Send medication question, verify it works

---

## TICKET-006: Update builder.py for Parenting Removal

### Why
Graph builder currently requires parenting components. Need to make them optional and handle disabled state.

### Where
- **File**: `app/graph/builder.py`
- **Lines**: 21 (import), 65-100 (function signature and validation), 104 (parenting node creation), 114 (add parenting node), 121-128 (routing maps)

### How

**Step 1**: Keep import but make it conditional
```python
# Parenting imports (optional - controlled by settings.ENABLE_PARENTING)
try:
    from app.agents.parenting_agent import create_parenting_node
    PARENTING_AVAILABLE = True
except ImportError:
    PARENTING_AVAILABLE = False
    logger.warning("Parenting agent not available")
```

**Step 2**: Update function signature (lines 65-69)

**Current**:
```python
def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: DocumentRetriever,
    parenting_reranker,
    checkpointer: BaseCheckpointSaver | None = None
):
```

**Replace with**:
```python
def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: DocumentRetriever | None = None,
    parenting_reranker = None,
    checkpointer: BaseCheckpointSaver | None = None
):
    """Build and compile the medical chatbot graph.

    Args:
        retriever: Document retriever for RAG agent (required)
        parenting_retriever: Document retriever for parenting agent (optional)
        parenting_reranker: Reranker for parenting agent (optional)
        checkpointer: Optional checkpointer instance (defaults to MemorySaver)

    Note:
        Parenting agent is disabled by default (settings.ENABLE_PARENTING=False).
        To enable: set ENABLE_PARENTING=True in .env and provide parenting components.
    """
```

**Step 3**: Replace validation (lines 95-100)

**Current**:
```python
# Fail-fast validation (Linus: "check errors early and loudly")
if not parenting_retriever or not parenting_reranker:
    raise ValueError(
        "Parenting retriever and reranker are required. "
        "Please run: python -m src.precompute_parenting_embeddings --force"
    )
```

**Replace with**:
```python
from app.config import settings

# Optional parenting system (controlled by feature flag)
enable_parenting = (
    settings.ENABLE_PARENTING and
    PARENTING_AVAILABLE and
    parenting_retriever is not None and
    parenting_reranker is not None
)

if enable_parenting:
    logger.info("✅ Parenting agent enabled")
else:
    logger.info("ℹ️  Parenting agent disabled (medication Q&A only)")
```

**Step 4**: Conditional node creation (line 104)
```python
# Create nodes using factory functions
rag_node = create_rag_node(retriever)

# Parenting node (optional)
if enable_parenting:
    parenting_node = create_parenting_node(parenting_retriever, parenting_reranker)
    logger.debug("Parenting agent node created")

logger.debug("Agent nodes created via factory functions")
```

**Step 5**: Conditional node addition (lines 111-114)
```python
# Add all nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("emotional_support", emotional_support_node)
builder.add_node("rag_agent", rag_node)

# Add parenting node only if enabled
if enable_parenting:
    builder.add_node("parenting", parenting_node)
```

**Step 6**: Update routing maps (lines 116-128)
```python
# Define routing maps (conditional parenting)
if enable_parenting:
    routing_map = {
        "supervisor": "supervisor",
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
        "parenting": "parenting",
    }
    supervisor_routing_map = {
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
        "parenting": "parenting",
    }
else:
    routing_map = {
        "supervisor": "supervisor",
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
    }
    supervisor_routing_map = {
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent",
    }
```

**Step 7**: Conditional edge (lines 146-148)
```python
# All agents go to END
builder.add_edge("emotional_support", END)
builder.add_edge("rag_agent", END)

# Parenting edge (conditional)
if enable_parenting:
    builder.add_edge("parenting", END)
```

### Checklist
- [ ] Add conditional import with try/except
- [ ] Make parenting parameters optional in function signature
- [ ] Add docstring explaining parenting is optional
- [ ] Replace validation with feature flag check
- [ ] Add `enable_parenting` flag variable
- [ ] Make parenting node creation conditional
- [ ] Make parenting node addition conditional
- [ ] Update routing maps based on enable_parenting flag
- [ ] Make parenting edge conditional
- [ ] Test: Build graph without parenting (should succeed)
- [ ] Test: Build graph with parenting (if available, should add parenting node)

---

## TICKET-007: Update supervisor.py Agent List

### Why
Supervisor hardcodes agent names including "parenting". Need to make parenting conditional based on feature flag.

### Where
- **File**: `app/agents/supervisor.py`
- **Lines**: 17 (Literal type), 32 (function return type), prompts.py lines 3-31

### How

**Step 1**: Update Literal type to be dynamic

**Current (line 17)**:
```python
agent: Literal["emotional_support", "rag_agent", "parenting"] = Field(
```

**Replace with**: Keep as is for now (Pydantic needs static Literal)

**Step 2**: Add runtime validation

After line 56, add:
```python
from app.config import settings

# Validate agent selection against enabled agents
if classification.agent == "parenting" and not settings.ENABLE_PARENTING:
    # Fallback to emotional_support for parenting questions when disabled
    logger.warning(
        f"Parenting agent selected but disabled. "
        f"Routing to emotional_support instead."
    )
    classification.agent = "emotional_support"
    classification.reasoning = (
        "Parenting agent disabled. Providing emotional support instead. "
        f"Original reasoning: {classification.reasoning}"
    )
```

**Step 3**: Update prompts.py (lines 15-23)

Add conditional note:
```python
# 3. **parenting**: For parenting advice and child development questions
#    NOTE: Parenting agent may be disabled (see ENABLE_PARENTING setting).
#    If disabled, questions will route to emotional_support.
#    - Indicators: mentions of children, toddlers, babies, parenting challenges
```

### Checklist
- [x] Keep Literal type as is (Pydantic requirement)
- [x] Add runtime validation after classification
- [x] Add fallback logic if parenting selected but disabled
- [x] Update reasoning when fallback occurs
- [x] Add NOTE to prompts.py about parenting being optional
- [x] Test: Set ENABLE_PARENTING=False, send parenting question
- [x] Verify: Should route to emotional_support with updated reasoning

---

# Phase 3: Simplify Initialization

## TICKET-008: Flatten main.py lifespan Function

### Why
Three layers of initialization functions (_initialize_session_store, _load_medical_retriever, _load_parenting_system) add unnecessary indirection. POC should have flat, simple initialization with fail-fast approach.

### Where
- **File**: `app/main.py`
- **Lines**: 40-189 (helper functions), 192-255 (lifespan function)

### How

**Step 1**: Remove helper functions (lines 40-189)

Delete these functions entirely:
- `_initialize_session_store()` (lines 40-48)
- `_load_medical_retriever()` (lines 51-120)
- `_load_parenting_system()` (lines 122-189) [Already commented out in Phase 2]

**Step 2**: Rewrite lifespan function (lines 192-255)

**Current**: Complex nested structure with try/except

**Replace with**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown.

    Fail-fast approach: Let exceptions propagate with clear messages.
    If any component fails to initialize, app won't start.

    Setup commands:
        docker-compose up -d                                    # PostgreSQL
        python -m app.db.schema                                 # Schema
        python -m src.embeddings.cli index --input data/chunking_final  # Index
    """
    logger.info("🚀 Starting Medical Chatbot application...")

    # ========================================================================
    # STARTUP
    # ========================================================================

    # 1. Initialize session store
    logger.info("Initializing session store...")
    session_store = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
    app_state["session_store"] = session_store
    logger.info("✅ Session store initialized")

    # 2. Initialize database connection pool
    logger.info("Connecting to PostgreSQL...")
    pool = await get_pool()
    app_state["db_pool"] = pool

    # Verify database setup
    async with pool.acquire() as conn:
        # Check pgvector extension
        pgvector_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        assert pgvector_exists, (
            "pgvector extension not found. Run: python -m app.db.schema"
        )

        # Check vector_chunks table
        table_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'vector_chunks')"
        )
        assert table_exists, (
            "vector_chunks table not found. Run: python -m app.db.schema"
        )

        # Get document count
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM vector_chunks")
        logger.info(f"📊 Database contains {doc_count} indexed chunks")

        if doc_count == 0:
            logger.warning(
                "⚠️  No documents indexed. "
                "Run: python -m src.embeddings.cli index --input data/chunking_final"
            )

    logger.info("✅ PostgreSQL connection established")

    # 3. Initialize retriever
    logger.info("Initializing PostgreSQL retriever...")
    retriever = PostgreSQLRetriever(
        pool=pool,
        embedding_model=settings.EMBEDDING_MODEL,
        reranker_model=settings.RERANKER_MODEL,
        use_reranking=(settings.RETRIEVAL_STRATEGY != "simple")
    )

    # Preload models if configured
    if settings.PRELOAD_MODELS:
        logger.info("Preloading models (encoder + reranker)...")
        await retriever.initialize()
        logger.info("✅ Models preloaded")
    else:
        logger.info("ℹ️  Lazy loading enabled (models load on first use)")

    app_state["retriever"] = retriever
    logger.info("✅ PostgreSQL retriever initialized")

    # 4. Build graph
    logger.info("Building LangGraph...")
    app_state["graph"] = build_medical_chatbot_graph(
        retriever=retriever,
    )
    logger.info("✅ Medical chatbot graph compiled")

    logger.info("🎉 Application startup complete!")
    logger.info(f"   Mode: Medication Q&A only")
    logger.info(f"   Strategy: {settings.RETRIEVAL_STRATEGY}")
    logger.info(f"   Preload: {settings.PRELOAD_MODELS}")

    # ========================================================================
    # YIELD TO APP
    # ========================================================================
    yield

    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    logger.info("👋 Shutting down application...")

    if app_state.get("db_pool"):
        await close_pool()
        logger.info("✅ Database connection pool closed")

    logger.info("✅ Shutdown complete")
```

**Step 3**: Update error messages to be clearer

Use assert statements instead of try/except:
- Database not ready? Assert + clear message
- No documents? Warning but continue
- Model loading fails? Let exception propagate

### Checklist
- [ ] Delete _initialize_session_store function
- [ ] Delete _load_medical_retriever function
- [ ] Delete _load_parenting_system function (if not already done)
- [ ] Rewrite lifespan function with flat structure
- [ ] Replace try/except with assert statements
- [ ] Add clear section comments (STARTUP, YIELD, SHUTDOWN)
- [ ] Update log messages to be informative
- [ ] Test: Start app with database not running (should fail with clear error)
- [ ] Test: Start app with database ready (should start successfully)
- [ ] Test: Verify startup log messages are clear

---

## TICKET-009: Simplify PostgreSQL Retriever Initialization

### Why
Complex initialization logic with try/except hides real problems. For POC, should fail fast with clear errors. Also need to support configurable preloading.

### Where
- **File**: `app/core/postgres_retriever.py`
- **Lines**: 82-127 (__init__), 128-179 (initialize), 180-202 (close), 329-356 (_load_reranker)

### How

**Step 1**: Simplify __init__ (lines 82-127)

**Current**: Complex with lazy loading setup

**Replace with**:
```python
def __init__(
    self,
    pool: DatabasePool,
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B",
    use_reranking: bool = True,
):
    """Initialize PostgreSQL retriever.

    Args:
        pool: DatabasePool instance (must be initialized)
        embedding_model: HuggingFace model ID for embeddings
        reranker_model: HuggingFace model ID for reranking
        use_reranking: Enable two-stage retrieval with reranking

    Note:
        Models are lazy loaded by default. Call initialize() to preload.
    """
    self.db_pool = pool
    self.embedding_model = embedding_model
    self.reranker_model = reranker_model
    self.use_reranking = use_reranking

    # Models (lazy loaded)
    self.encoder: Optional[Qwen3EmbeddingEncoder] = None
    self.reranker: Optional[Qwen3Reranker] = None

    logger.info(
        f"PostgreSQLRetriever created: "
        f"embedding={embedding_model}, reranker={reranker_model}, "
        f"use_reranking={use_reranking}"
    )
```

**Step 2**: Simplify initialize() (lines 128-179)

**Replace with**:
```python
async def initialize(self) -> None:
    """Initialize (preload) embedding encoder and reranker models.

    This is optional - models will lazy load on first use if not called.
    Call this during startup if settings.PRELOAD_MODELS=True.

    Raises:
        RuntimeError: If model loading fails
    """
    if self.encoder is not None and self.reranker is not None:
        logger.info("Models already initialized")
        return

    # Load encoder
    logger.info(f"Loading encoder: {self.embedding_model}")
    self.encoder = Qwen3EmbeddingEncoder(
        model_name=self.embedding_model,
        device="mps",
        batch_size=16,
        max_length=1024,
        normalize_embeddings=True,
        instruction=None
    )
    logger.info(f"✅ Encoder loaded on device: {self.encoder.device}")

    # Load reranker if enabled
    if self.use_reranking:
        logger.info(f"Loading reranker: {self.reranker_model}")
        self.reranker = Qwen3Reranker(
            model_name=self.reranker_model,
            device="mps",
            batch_size=8
        )
        logger.info("✅ Reranker loaded")
    else:
        logger.info("ℹ️  Reranking disabled, skipping reranker initialization")
```

**Step 3**: Simplify close() (lines 180-202)

**Replace with**:
```python
async def close(self) -> None:
    """Cleanup resources (models remain loaded, pool cleanup handled by app)."""
    logger.info("PostgreSQLRetriever closed (pool cleanup handled by app)")
```

**Step 4**: Remove _load_reranker() method (lines 329-356)

Delete entire method. Reranker loading now in initialize().

**Step 5**: Update search() to handle lazy loading (lines 203-327)

Add lazy loading at start of search():
```python
async def search(
    self,
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Document]:
    """Search for relevant documents using pgvector similarity search.

    Models are lazy loaded on first call if not preloaded.
    """
    # Validate inputs
    assert query and query.strip(), "Query cannot be empty"
    assert self.db_pool is not None, "Database pool not initialized"

    # Lazy load encoder if not yet loaded
    if self.encoder is None:
        logger.info("Lazy loading encoder (first search call)...")
        self.encoder = Qwen3EmbeddingEncoder(
            model_name=self.embedding_model,
            device="mps",
            batch_size=16,
            max_length=1024,
            normalize_embeddings=True,
            instruction=None
        )

    # Generate query embedding
    logger.info(f"Generating embedding for query: {query[:100]}...")
    query_embedding = self._generate_query_embedding(query)

    # ... rest of search logic ...

    # Lazy load reranker if needed
    if self.use_reranking and len(results) > 0:
        if self.reranker is None:
            logger.info("Lazy loading reranker (first search with reranking)...")
            self.reranker = Qwen3Reranker(
                model_name=self.reranker_model,
                device="mps",
                batch_size=8
            )

        # Rerank logic...
```

**Step 6**: Remove all try/except blocks

Replace error handling with assertions and let exceptions propagate:
- Database errors → Let asyncpg raise clear errors
- Model loading errors → Let transformers raise clear errors
- Validation errors → Use assert statements

### Checklist
- [x] Simplify __init__ - remove db_url parameter, require pool
- [x] Simplify initialize() - straightforward model loading
- [x] Simplify close() - minimal cleanup
- [x] Remove _load_reranker() method
- [x] Add lazy loading logic to search()
- [x] Remove all try/except blocks
- [x] Replace validations with assert statements
- [x] Test: Create retriever with preload (call initialize)
- [x] Test: Create retriever without preload (lazy load on search)
- [x] Test: Verify clear error messages on failures

**Status**: ✅ COMPLETED (2025-11-04)
**Test Results**: All unit tests passed (test_retriever_unit.py)

---

## TICKET-010: Remove Retry Logic from DatabasePool

### Why
POC should fail fast to identify connection issues quickly. Retry logic hides problems during development. Make retries optional via config flag.

### Where
- **File**: `app/db/connection.py`
- **Lines**: 165-174 (execute), 217-225 (fetch), 271-279 (fetchval), 320-328 (fetchrow)

### How

**Step 1**: Add conditional retry decorator

Add new decorator before DatabasePool class:
```python
from app.config import settings

def conditional_retry(func):
    """Apply retry decorator only if settings.ENABLE_RETRIES is True."""
    if settings.ENABLE_RETRIES:
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((
                asyncpg.PostgresConnectionError,
                asyncpg.InterfaceError,
                asyncpg.TooManyConnectionsError,
            )),
            reraise=True,
        )(func)
    return func
```

**Step 2**: Replace @retry decorators with @conditional_retry

**Line 165**: Change from:
```python
@retry(...)
async def execute(self, ...):
```

To:
```python
@conditional_retry
async def execute(self, ...):
```

**Line 217**: Same for fetch()
**Line 271**: Same for fetchval()
**Line 320**: Same for fetchrow()

**Step 3**: Update docstrings

Remove mentions of "automatic retries" from docstrings. Replace with:
```
Note:
    Retries are configurable via settings.ENABLE_RETRIES.
    For POC/development, retries are disabled for fast failure.
```

**Step 4**: Add log message when retries disabled

In DatabasePool.__init__, add:
```python
if settings.ENABLE_RETRIES:
    logger.info("Database retries enabled (3 attempts, exponential backoff)")
else:
    logger.info("Database retries disabled (fail-fast mode for POC)")
```

### Checklist
- [ ] Add conditional_retry decorator function
- [ ] Import settings at top
- [ ] Replace @retry with @conditional_retry on execute()
- [ ] Replace @retry with @conditional_retry on fetch()
- [ ] Replace @retry with @conditional_retry on fetchval()
- [ ] Replace @retry with @conditional_retry on fetchrow()
- [ ] Update docstrings to mention configurable retries
- [ ] Add log message in __init__ about retry status
- [ ] Test: Set ENABLE_RETRIES=False, verify no retries on connection failure
- [ ] Test: Set ENABLE_RETRIES=True, verify retries work

---

## TICKET-011: Simplify Qwen3Reranker Error Handling

### Why
Try/except blocks wrap model loading and inference, hiding useful error messages from transformers. Should let exceptions propagate naturally.

### Where
- **File**: `app/core/qwen3_reranker.py`
- **Lines**: 146-199 (_load_model), 284-343 (rerank)

### How

**Step 1**: Simplify _load_model() (lines 146-199)

**Current**: try/except wrapping with RuntimeError

**Replace with**:
```python
def _load_model(self) -> None:
    """Lazy load model and tokenizer on first use.

    Loads:
    - AutoModelForCausalLM with torch.float32 for MPS compatibility
    - AutoTokenizer with left padding
    - Yes/no token IDs for relevance scoring
    - Prefix/suffix tokens for prompt template

    Raises:
        RuntimeError: If model or tokenizer loading fails (from transformers)
    """
    if self._model is not None:
        return  # Already loaded

    logger.info(f"Loading Qwen3-Reranker model: {self.model_name}")

    # Load tokenizer with left padding for batch processing
    self._tokenizer = AutoTokenizer.from_pretrained(
        self.model_name,
        padding_side='left'
    )
    logger.info("✅ Tokenizer loaded")

    # Load model with torch.float32 for MPS compatibility
    self._model = AutoModelForCausalLM.from_pretrained(
        self.model_name,
        torch_dtype=torch.float32
    ).to(self.device).eval()
    logger.info(f"✅ Model loaded on device: {self.device}")

    # Extract token IDs for yes/no scoring
    self._token_yes_id = self._tokenizer.convert_tokens_to_ids("yes")
    self._token_no_id = self._tokenizer.convert_tokens_to_ids("no")

    assert self._token_yes_id is not None and self._token_no_id is not None, (
        f"Failed to extract yes/no token IDs. "
        f"yes={self._token_yes_id}, no={self._token_no_id}"
    )

    logger.info(f"✅ Token IDs: yes={self._token_yes_id}, no={self._token_no_id}")

    # Precompute prefix and suffix tokens
    prefix = (
        "<|im_start|>system\n"
        "Judge whether the Document meets the requirements based on the Query and "
        "the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
        "<|im_end|>\n<|im_start|>user\n"
    )
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

    self._prefix_tokens = self._tokenizer.encode(prefix, add_special_tokens=False)
    self._suffix_tokens = self._tokenizer.encode(suffix, add_special_tokens=False)

    logger.info(
        f"✅ Prompt tokens: prefix={len(self._prefix_tokens)}, "
        f"suffix={len(self._suffix_tokens)}"
    )
```

**Step 2**: Simplify rerank() (lines 284-343)

**Current**: try/except wrapping entire inference

**Replace with**:
```python
@torch.no_grad()
def rerank(
    self,
    query: str,
    documents: List[str],
    instruction: Optional[str] = None
) -> List[float]:
    """Rerank documents and return relevance scores.

    Raises:
        ValueError: If documents list is empty
        RuntimeError: If model inference fails (from torch/transformers)
    """
    # Validate inputs
    assert documents, "Documents list cannot be empty"

    # Lazy load model on first call
    self._load_model()

    # Format pairs
    pairs = [
        self.format_instruction(instruction, query, doc)
        for doc in documents
    ]

    # Tokenize
    inputs = self._tokenizer(
        pairs,
        padding=True,
        truncation='longest_first',
        return_tensors="pt",
        max_length=self.max_length - len(self._prefix_tokens) - len(self._suffix_tokens)
    )

    # Add prefix and suffix tokens
    modified_input_ids = []
    for ele in inputs['input_ids']:
        modified_input_ids.append(
            self._prefix_tokens + ele.tolist() + self._suffix_tokens
        )

    inputs['input_ids'] = torch.tensor(modified_input_ids, dtype=torch.long)
    inputs['attention_mask'] = torch.ones_like(inputs['input_ids'])

    # Move to device
    for key in inputs:
        inputs[key] = inputs[key].to(self.device)

    # Compute logits
    outputs = self._model(**inputs)
    batch_logits = outputs.logits[:, -1, :]

    # Extract yes/no probabilities
    yes_logits = batch_logits[:, self._token_yes_id]
    no_logits = batch_logits[:, self._token_no_id]

    # Normalize with log_softmax
    stacked_logits = torch.stack([no_logits, yes_logits], dim=1)
    log_probs = torch.nn.functional.log_softmax(stacked_logits, dim=1)

    # Convert to probabilities (yes scores)
    relevance_scores = log_probs[:, 1].exp().tolist()

    logger.debug(
        f"Reranked {len(documents)} documents. "
        f"Score range: [{min(relevance_scores):.3f}, {max(relevance_scores):.3f}]"
    )

    return relevance_scores
```

### Checklist
- [ ] Remove try/except from _load_model()
- [ ] Replace raise RuntimeError with assert for token IDs
- [ ] Let transformers exceptions propagate naturally
- [ ] Remove try/except from rerank()
- [ ] Replace ValueError check with assert
- [ ] Test: Load model with invalid model name (should show transformers error)
- [ ] Test: Rerank with empty documents (should show clear assertion error)
- [ ] Verify error messages are clear and useful

---

# Phase 4: Create Retrieval Strategies

## TICKET-012: Create Retrieval Module Structure

### Why
Need three separate retrieval strategies (simple, rerank, advanced) that can be switched via config. Current code only supports one approach.

### Where
- **New directory**: `app/retrieval/`
- **New files**: `__init__.py`, `base.py`, `simple.py`, `rerank.py`, `advanced.py`, `factory.py`

### How

**Step 1**: Create directory structure
```bash
mkdir -p app/retrieval
touch app/retrieval/__init__.py
touch app/retrieval/base.py
touch app/retrieval/simple.py
touch app/retrieval/rerank.py
touch app/retrieval/advanced.py
touch app/retrieval/factory.py
```

**Step 2**: Create base.py

```python
"""Base retrieval protocol for all strategies.

This defines the interface that all retrieval strategies must implement.
"""

from typing import Protocol, List, Dict, Any, Optional


class RetrieverProtocol(Protocol):
    """Protocol defining the interface for all retrieval strategies."""

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: User's search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of dictionaries with keys:
                - chunk_id: str
                - chunk_text: str
                - source_document: str
                - chapter_title: str
                - section_title: str
                - similarity_score: float
                - rerank_score: float (if reranking used)
        """
        ...
```

**Step 3**: Create __init__.py

```python
"""Retrieval strategies for semantic search.

Three strategies available:
1. Simple: query → embedding → pgvector search → return top_k
2. Rerank: query → search top_k*4 → rerank → return top_k
3. Advanced: query → LLM expand → search all → merge → rerank → return top_k
"""

from app.retrieval.simple import SimpleRetriever
from app.retrieval.rerank import RerankRetriever
from app.retrieval.advanced import AdvancedRetriever
from app.retrieval.factory import get_retriever

__all__ = [
    "SimpleRetriever",
    "RerankRetriever",
    "AdvancedRetriever",
    "get_retriever",
]
```

### Checklist
- [ ] Create `app/retrieval/` directory
- [ ] Create `__init__.py` with exports
- [ ] Create `base.py` with RetrieverProtocol
- [ ] Create empty files: simple.py, rerank.py, advanced.py, factory.py
- [ ] Test: `python -c "from app.retrieval import get_retriever"` (should not error once implemented)

---

## TICKET-013: Implement Simple Retrieval Strategy

### Why
Basic retrieval: query → embedding → pgvector similarity search → return top_k results. No reranking, fastest approach.

### Where
- **File**: `app/retrieval/simple.py` (new)

### How

**Step 1**: Create SimpleRetriever class

```python
"""Simple retrieval strategy: query → embedding → search → results.

No reranking, fastest retrieval approach.
"""

import logging
from typing import List, Dict, Any, Optional

from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder

logger = logging.getLogger(__name__)


class SimpleRetriever:
    """Simple retrieval: embedding + pgvector similarity search.

    Process:
        1. Generate query embedding
        2. pgvector cosine similarity search
        3. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding encoder (Qwen3-Embedding-0.6B)
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: Qwen3EmbeddingEncoder,
    ):
        """Initialize simple retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
        """
        self.pool = pool
        self.encoder = encoder

        logger.info("SimpleRetriever initialized (no reranking)")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: Search query string
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"source_document": "..."})

        Returns:
            List of result dictionaries with document data and similarity scores
        """
        # Validate
        assert query and query.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Simple search: query='{query[:50]}...', top_k={top_k}")

        # Generate embedding
        query_embedding = self.encoder.encode(query).tolist()

        # Build SQL query
        sql, params = self._build_query(query_embedding, top_k, filters)

        # Execute search
        results = await self.pool.fetch(sql, *params)

        # Convert to dictionaries
        documents = [
            {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
            }
            for row in results
        ]

        logger.info(f"Found {len(documents)} results")
        return documents

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query with optional filters.

        Args:
            embedding: Query embedding vector
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            Tuple of (sql_query, parameters)
        """
        sql = """
        SELECT
            chunk_id,
            chunk_text,
            source_document,
            chapter_title,
            section_title,
            subsection_title,
            summary,
            token_count,
            1 - (embedding <=> $1) AS similarity_score
        FROM vector_chunks
        """

        params = [embedding]
        param_index = 2

        # Add filters
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        # Add ordering and limit
        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
```

### Checklist
- [ ] Create simple.py file
- [ ] Implement SimpleRetriever class
- [ ] Implement __init__ method
- [ ] Implement search method
- [ ] Implement _build_query helper
- [ ] Add docstrings
- [ ] Add logging
- [ ] Test: Create SimpleRetriever instance
- [ ] Test: Search with query, verify results
- [ ] Test: Search with filters

---

## TICKET-014: Implement Rerank Retrieval Strategy

### Why
Two-stage retrieval: query → search top_k*4 candidates → rerank with Qwen3-Reranker → return top_k best. Better relevance than simple search.

### Where
- **File**: `app/retrieval/rerank.py` (new)

### How

**Step 1**: Create RerankRetriever class

```python
"""Rerank retrieval strategy: query → search → rerank → results.

Two-stage retrieval for improved relevance.
"""

import logging
from typing import List, Dict, Any, Optional

from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker

logger = logging.getLogger(__name__)


class RerankRetriever:
    """Rerank retrieval: embedding + pgvector + reranker.

    Process:
        1. Generate query embedding
        2. pgvector search for top_k * 4 candidates
        3. Rerank candidates with Qwen3-Reranker
        4. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding encoder
        reranker: Qwen3-Reranker for scoring
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: Qwen3EmbeddingEncoder,
        reranker: Qwen3Reranker,
    ):
        """Initialize rerank retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker

        logger.info("RerankRetriever initialized (two-stage retrieval)")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with reranking for improved relevance.

        Args:
            query: Search query string
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score (highest first)
        """
        # Validate
        assert query and query.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Rerank search: query='{query[:50]}...', top_k={top_k}")

        # Stage 1: Retrieve candidates (4x oversampling)
        candidate_count = top_k * 4

        # Generate embedding
        query_embedding = self.encoder.encode(query).tolist()

        # Build SQL query for candidates
        sql, params = self._build_query(query_embedding, candidate_count, filters)

        # Execute search
        candidates = await self.pool.fetch(sql, *params)

        if not candidates:
            logger.warning("No candidates found")
            return []

        logger.info(f"Retrieved {len(candidates)} candidates for reranking")

        # Stage 2: Rerank candidates
        candidate_texts = [row["chunk_text"] for row in candidates]
        rerank_scores = self.reranker.rerank(query, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(candidates, rerank_scores):
            result = {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
                "rerank_score": float(score),
            }
            results_with_scores.append(result)

        # Sort by rerank_score (descending)
        results_with_scores.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Take top_k
        final_results = results_with_scores[:top_k]

        logger.info(
            f"Reranked {len(candidates)} → {len(final_results)} results "
            f"(score range: {final_results[0]['rerank_score']:.3f} - "
            f"{final_results[-1]['rerank_score']:.3f})"
        )

        return final_results

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query (same as SimpleRetriever)."""
        sql = """
        SELECT
            chunk_id,
            chunk_text,
            source_document,
            chapter_title,
            section_title,
            subsection_title,
            summary,
            token_count,
            1 - (embedding <=> $1) AS similarity_score
        FROM vector_chunks
        """

        params = [embedding]
        param_index = 2

        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
```

### Checklist
- [ ] Create rerank.py file
- [ ] Implement RerankRetriever class
- [ ] Implement __init__ with encoder + reranker
- [ ] Implement search with two stages
- [ ] Calculate candidate_count as top_k * 4
- [ ] Add reranking logic
- [ ] Sort by rerank_score
- [ ] Add logging for both stages
- [ ] Test: Create RerankRetriever instance
- [ ] Test: Search and verify rerank_score in results
- [ ] Test: Verify results are sorted by rerank_score

---

## TICKET-015: Implement Advanced Retrieval Strategy with Query Expansion

### Why
Most sophisticated: query → LLM generates variations → search all → deduplicate → rerank → return top_k. Best for complex queries.

### Where
- **File**: `app/retrieval/advanced.py` (new)

### How

**Step 1**: Create AdvancedRetriever class with query expansion

```python
"""Advanced retrieval strategy: query expansion + search + rerank.

Most sophisticated retrieval approach using LLM query expansion.
"""

import logging
from typing import List, Dict, Any, Optional

from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.agents.base import create_llm

logger = logging.getLogger(__name__)


class AdvancedRetriever:
    """Advanced retrieval: query expansion + multi-query search + reranking.

    Process:
        1. LLM expands query into 3 variations
        2. Search all variations in parallel
        3. Merge and deduplicate results
        4. Rerank with Qwen3-Reranker
        5. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding encoder
        reranker: Qwen3-Reranker for scoring
        llm: LLM for query expansion
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: Qwen3EmbeddingEncoder,
        reranker: Qwen3Reranker,
    ):
        """Initialize advanced retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker
        self.llm = create_llm(temperature=0.7)  # For creative query variations

        logger.info("AdvancedRetriever initialized (query expansion + reranking)")

    async def expand_query(self, query: str) -> List[str]:
        """Expand query into multiple variations using LLM.

        Generates 3 query variations:
        1. Original query (unchanged)
        2. More specific technical variation
        3. Broader contextual variation

        Args:
            query: Original user query

        Returns:
            List of 3 query strings
        """
        expansion_prompt = f"""You are a medical information search assistant.

Given the user's query, generate 2 additional search variations to improve retrieval:

1. A more SPECIFIC, TECHNICAL variation (using medical terminology)
2. A BROADER, CONTEXTUAL variation (considering related topics)

Original query: {query}

Respond in this format:
SPECIFIC: <your specific variation>
BROADER: <your broader variation>

Example:
User query: "What are side effects of aripiprazole?"
SPECIFIC: aripiprazole adverse reactions pharmacological effects dopamine antagonist
BROADER: atypical antipsychotic medication side effects safety profile tolerability

Now generate variations for the query above:"""

        # Generate variations
        response = self.llm.invoke([{"role": "user", "content": expansion_prompt}])
        response_text = response.content

        # Parse response
        queries = [query]  # Always include original

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('SPECIFIC:'):
                specific = line.replace('SPECIFIC:', '').strip()
                if specific:
                    queries.append(specific)
            elif line.startswith('BROADER:'):
                broader = line.replace('BROADER:', '').strip()
                if broader:
                    queries.append(broader)

        # Ensure we have exactly 3 queries
        if len(queries) < 3:
            # Fallback: duplicate original if parsing failed
            while len(queries) < 3:
                queries.append(query)

        queries = queries[:3]  # Take first 3

        logger.info(f"Expanded query into {len(queries)} variations")
        for i, q in enumerate(queries, 1):
            logger.debug(f"  {i}. {q[:80]}...")

        return queries

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with query expansion and reranking.

        Args:
            query: Search query string
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score
        """
        # Validate
        assert query and query.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Advanced search: query='{query[:50]}...', top_k={top_k}")

        # Stage 1: Expand query
        queries = await self.expand_query(query)

        # Stage 2: Search all query variations
        all_candidates = []
        seen_chunk_ids = set()

        for i, q in enumerate(queries, 1):
            # Generate embedding
            query_embedding = self.encoder.encode(q).tolist()

            # Build SQL query
            sql, params = self._build_query(query_embedding, top_k, filters)

            # Execute search
            results = await self.pool.fetch(sql, *params)

            # Deduplicate by chunk_id
            for row in results:
                chunk_id = row["chunk_id"]
                if chunk_id not in seen_chunk_ids:
                    all_candidates.append(row)
                    seen_chunk_ids.add(chunk_id)

            logger.debug(f"Query {i}: found {len(results)} results")

        if not all_candidates:
            logger.warning("No candidates found from any query variation")
            return []

        logger.info(
            f"Collected {len(all_candidates)} unique candidates "
            f"from {len(queries)} query variations"
        )

        # Stage 3: Rerank all candidates with ORIGINAL query
        candidate_texts = [row["chunk_text"] for row in all_candidates]
        rerank_scores = self.reranker.rerank(query, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(all_candidates, rerank_scores):
            result = {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
                "rerank_score": float(score),
            }
            results_with_scores.append(result)

        # Sort by rerank_score (descending)
        results_with_scores.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Take top_k
        final_results = results_with_scores[:top_k]

        logger.info(
            f"Reranked {len(all_candidates)} → {len(final_results)} results "
            f"(score range: {final_results[0]['rerank_score']:.3f} - "
            f"{final_results[-1]['rerank_score']:.3f})"
        )

        return final_results

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query (same as other retrievers)."""
        sql = """
        SELECT
            chunk_id,
            chunk_text,
            source_document,
            chapter_title,
            section_title,
            subsection_title,
            summary,
            token_count,
            1 - (embedding <=> $1) AS similarity_score
        FROM vector_chunks
        """

        params = [embedding]
        param_index = 2

        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
```

### Checklist
- [ ] Create advanced.py file
- [ ] Implement AdvancedRetriever class
- [ ] Implement __init__ with LLM creation
- [ ] Implement expand_query method
- [ ] Add query expansion prompt
- [ ] Parse LLM response for SPECIFIC and BROADER
- [ ] Implement search with 3 stages
- [ ] Search all query variations
- [ ] Deduplicate by chunk_id
- [ ] Rerank with original query
- [ ] Add comprehensive logging
- [ ] Test: expand_query returns 3 variations
- [ ] Test: Search finds unique results across queries
- [ ] Test: Final results sorted by rerank_score

---

## TICKET-016: Create Retrieval Factory

### Why
Need centralized factory to create appropriate retriever based on `settings.RETRIEVAL_STRATEGY`. Makes switching strategies easy.

### Where
- **File**: `app/retrieval/factory.py` (new)

### How

**Step 1**: Create factory function

```python
"""Factory for creating retrieval strategy instances.

Selects appropriate retriever based on settings.RETRIEVAL_STRATEGY.
"""

import logging
from typing import Union

from app.config import settings
from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.retrieval.simple import SimpleRetriever
from app.retrieval.rerank import RerankRetriever
from app.retrieval.advanced import AdvancedRetriever

logger = logging.getLogger(__name__)


def get_retriever(
    pool: DatabasePool,
    encoder: Qwen3EmbeddingEncoder,
    reranker: Qwen3Reranker | None = None,
) -> Union[SimpleRetriever, RerankRetriever, AdvancedRetriever]:
    """Create retriever based on settings.RETRIEVAL_STRATEGY.

    Strategies:
        - "simple": SimpleRetriever (no reranking, fastest)
        - "rerank": RerankRetriever (requires reranker)
        - "advanced": AdvancedRetriever (requires reranker + LLM query expansion)

    Args:
        pool: Initialized database pool
        encoder: Initialized embedding encoder
        reranker: Initialized reranker (required for "rerank" and "advanced")

    Returns:
        Configured retriever instance

    Raises:
        ValueError: If strategy is unknown or reranker missing for strategies that need it

    Example:
        >>> from app.retrieval import get_retriever
        >>> retriever = get_retriever(pool, encoder, reranker)
        >>> results = await retriever.search("aripiprazole side effects")
    """
    strategy = settings.RETRIEVAL_STRATEGY.lower()

    logger.info(f"Creating retriever with strategy: {strategy}")

    if strategy == "simple":
        # No reranking needed
        return SimpleRetriever(pool=pool, encoder=encoder)

    elif strategy == "rerank":
        # Requires reranker
        assert reranker is not None, (
            "Reranker required for 'rerank' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return RerankRetriever(pool=pool, encoder=encoder, reranker=reranker)

    elif strategy == "advanced":
        # Requires reranker for final stage
        assert reranker is not None, (
            "Reranker required for 'advanced' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return AdvancedRetriever(pool=pool, encoder=encoder, reranker=reranker)

    else:
        raise ValueError(
            f"Unknown retrieval strategy: '{strategy}'. "
            f"Valid options: 'simple', 'rerank', 'advanced'"
        )
```

### Checklist
- [ ] Create factory.py file
- [ ] Import all retriever classes
- [ ] Import settings
- [ ] Implement get_retriever function
- [ ] Handle "simple" strategy (no reranker needed)
- [ ] Handle "rerank" strategy (assert reranker exists)
- [ ] Handle "advanced" strategy (assert reranker exists)
- [ ] Raise ValueError for unknown strategies
- [ ] Add docstring with examples
- [ ] Add logging
- [ ] Test: Create retriever with strategy="simple"
- [ ] Test: Create retriever with strategy="rerank" (with reranker)
- [ ] Test: Create retriever with strategy="advanced" (with reranker)
- [ ] Test: Invalid strategy raises ValueError
- [ ] Test: Missing reranker raises assertion error

---

## TICKET-017: Integrate Retrieval Factory into main.py

### Why
Update main.py to use new retrieval factory instead of PostgreSQLRetriever directly.

### Where
- **File**: `app/main.py`
- **Lines**: Retriever initialization in lifespan function

### How

**Step 1**: Update imports

Add after database imports:
```python
from app.retrieval import get_retriever
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
```

Remove (if present):
```python
from app.core.postgres_retriever import PostgreSQLRetriever
```

**Step 2**: Update retriever initialization in lifespan

Replace retriever initialization section with:
```python
# 3. Initialize embedding encoder
logger.info(f"Initializing encoder: {settings.EMBEDDING_MODEL}")
encoder = Qwen3EmbeddingEncoder(
    model_name=settings.EMBEDDING_MODEL,
    device="mps",
    batch_size=16,
    max_length=1024,
    normalize_embeddings=True,
    instruction=None
)

# Preload encoder if configured
if settings.PRELOAD_MODELS:
    logger.info("Encoder initialized (preloaded)")
else:
    logger.info("Encoder created (will lazy load on first use)")

# 4. Initialize reranker (if needed for strategy)
reranker = None
if settings.RETRIEVAL_STRATEGY in ["rerank", "advanced"]:
    logger.info(f"Initializing reranker: {settings.RERANKER_MODEL}")
    reranker = Qwen3Reranker(
        model_name=settings.RERANKER_MODEL,
        device="mps",
        batch_size=8
    )

    if settings.PRELOAD_MODELS:
        # Preload reranker (trigger model loading)
        _ = reranker.rerank("test", ["test document"])
        logger.info("Reranker initialized (preloaded)")
    else:
        logger.info("Reranker created (will lazy load on first use)")
else:
    logger.info(f"Reranker not needed for '{settings.RETRIEVAL_STRATEGY}' strategy")

# 5. Create retriever using factory
logger.info(f"Creating retriever (strategy: {settings.RETRIEVAL_STRATEGY})...")
retriever = get_retriever(
    pool=pool,
    encoder=encoder,
    reranker=reranker
)
app_state["retriever"] = retriever
logger.info("✅ Retriever initialized")
```

**Step 3**: Update success log

```python
logger.info("🎉 Application startup complete!")
logger.info(f"   Mode: Medication Q&A")
logger.info(f"   Strategy: {settings.RETRIEVAL_STRATEGY}")
logger.info(f"   Preload: {'Enabled' if settings.PRELOAD_MODELS else 'Lazy loading'}")
```

### Checklist
- [x] Add import for get_retriever
- [x] Add imports for Qwen3EmbeddingEncoder and Qwen3Reranker
- [x] Remove PostgreSQLRetriever import
- [x] Initialize encoder separately
- [x] Conditionally initialize reranker based on strategy
- [x] Handle PRELOAD_MODELS for both encoder and reranker
- [x] Use get_retriever factory
- [x] Update success log with strategy info
- [x] Test: Start app with strategy="simple"
- [x] Test: Start app with strategy="rerank"
- [x] Test: Start app with strategy="advanced"
- [x] Verify appropriate models are loaded for each strategy

---

# Phase 5: Cleanup & Remove Abstractions

## TICKET-018: Remove Global Pool Singleton

### Why
Global singleton pattern adds unnecessary complexity for POC. Should create pool directly in main.py.

### Where
- **File**: `app/db/connection.py`
- **Lines**: 383-431 (global pool functions)

### How

**Step 1**: Comment out or remove global pool code

Lines 383-431:
```python
# ============================================================================
# GLOBAL POOL (NOT USED - POC creates pool directly in main.py)
# ============================================================================
#
# # Global pool instance for application-wide use
# _global_pool: Optional[DatabasePool] = None
#
# async def get_pool(...):
#     """Get or create the global database pool instance."""
#     ...
#
# async def close_pool() -> None:
#     """Close the global database pool."""
#     ...
```

**Step 2**: Update main.py to create pool directly

In main.py lifespan function:
```python
# OLD:
# pool = await get_pool()

# NEW:
pool = DatabasePool(min_size=5, max_size=20)
await pool.initialize()
```

**Step 3**: Update shutdown

```python
# OLD:
# await close_pool()

# NEW:
await pool.close()
```

### Checklist
- [ ] Comment out _global_pool variable
- [ ] Comment out get_pool() function
- [ ] Comment out close_pool() function
- [ ] Update main.py to create DatabasePool directly
- [ ] Update main.py to call pool.initialize()
- [ ] Update shutdown to call pool.close() directly
- [ ] Test: Start and stop app, verify pool is created and closed

---

## TICKET-019: Remove Unused Retriever Implementations

### Why
FAISSRetriever, BM25Retriever, HybridRetriever are not used (using PostgreSQL now). Removing reduces confusion.

### Where
- **File**: `app/core/retriever.py`
- **Lines**: 58-346 (FAISSRetriever, BM25Retriever, HybridRetriever)

### How

**Step 1**: Keep only Document and DocumentRetriever abstract class

Lines 1-56 stay as is (Document dataclass and DocumentRetriever ABC).

**Step 2**: Move or delete unused implementations

**Option A**: Delete entirely
- Remove lines 58-346

**Option B**: Move to archive (recommended for reference)
```bash
mkdir -p app/core/archive
mv app/core/retriever.py app/core/retriever_with_faiss.py
```

Then create new minimal retriever.py:
```python
"""Core document retrieval interface.

Document dataclass and abstract retriever interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document representation."""

    content: str
    metadata: dict
    id: Optional[str] = None
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None


class DocumentRetriever(ABC):
    """Abstract interface for document retrieval."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of most relevant documents
        """
        pass

    @abstractmethod
    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to the index.

        Args:
            docs: List of documents to add
        """
        pass
```

**Step 3**: Update imports if needed

Check files that import from retriever.py:
```bash
grep -r "from app.core.retriever import" app/
```

Update any imports that reference removed classes.

### Checklist
- [ ] Decide: delete or move to archive
- [ ] If archiving: create app/core/archive/ and move file
- [ ] If deleting: remove FAISSRetriever, BM25Retriever, HybridRetriever
- [ ] Create new minimal retriever.py with Document and DocumentRetriever
- [ ] Find all files importing from retriever.py
- [ ] Update imports if needed
- [ ] Test: Import from app.core.retriever (should work)
- [ ] Test: No references to deleted classes

---

## TICKET-020: Remove add_documents Method from PostgreSQLRetriever

### Why
POC uses CLI for indexing (`python -m src.embeddings.cli index`). Runtime add_documents is not needed and adds complexity.

### Where
- **File**: `app/core/postgres_retriever.py`
- **Lines**: 518-602 (add_documents method)

### How

**Step 1**: Comment out method with explanation

```python
# ============================================================================
# add_documents - NOT USED IN POC
# ============================================================================
# POC uses CLI indexing: python -m src.embeddings.cli index --input data/
#
# If needed for testing, uncomment this method:
#
# async def add_documents(self, docs: List[Document]) -> None:
#     """Add documents to the index.
#
#     Note:
#         Primary indexing should be done via CLI script for production.
#         This method is provided for DocumentRetriever interface compatibility.
#
#     WARNING: For production indexing, use CLI script instead:
#         python -m src.embeddings.cli index --input data/chunking_final/
#     """
#     ...
#     [rest of method commented]
```

**Step 2**: Update DocumentRetriever ABC if needed

If DocumentRetriever.add_documents is abstract and required, either:

**Option A**: Keep method but make it raise NotImplementedError
```python
async def add_documents(self, docs: List[Document]) -> None:
    """Not implemented - use CLI indexing."""
    raise NotImplementedError(
        "Use CLI for indexing: python -m src.embeddings.cli index --input data/"
    )
```

**Option B**: Make DocumentRetriever.add_documents optional (not abstract)

### Checklist
- [ ] Comment out add_documents method
- [ ] Add explanation about CLI indexing
- [ ] Decide how to handle DocumentRetriever ABC requirement
- [ ] If keeping method: make it raise NotImplementedError
- [ ] If removing from ABC: make add_documents non-abstract
- [ ] Test: Create PostgreSQLRetriever (should work without add_documents)
- [ ] Verify CLI indexing still works: `python -m src.embeddings.cli index --input data/`

---

## TICKET-021: Simplify Models (Optional)

### Why
User requested simpler models (plain dicts or minimal dataclasses) instead of Pydantic. However, Pydantic is useful for FastAPI auto-validation.

**Recommendation**: Keep Pydantic models for FastAPI. They provide value.

### Where
- **File**: `app/models.py`
- **Lines**: 7-27 (ChatRequest, ChatResponse, HealthResponse)

### How (If user insists on removing)

**Step 1**: Replace with simple TypedDict

```python
"""API request/response models."""

from typing import TypedDict, Optional


class ChatRequest(TypedDict):
    """Chat request."""
    session_id: str
    message: str


class ChatResponse(TypedDict):
    """Chat response."""
    session_id: str
    message: str
    agent: str
    metadata: Optional[dict]


class HealthResponse(TypedDict):
    """Health check response."""
    status: str
    version: str
```

**Step 2**: Update main.py endpoint signatures

Remove `response_model` from decorators:
```python
# OLD:
@app.post("/chat", response_model=ChatResponse)

# NEW:
@app.post("/chat")
```

**Step 3**: Add manual validation

```python
@app.post("/chat")
async def chat(request: dict, ...):
    # Manual validation
    assert "session_id" in request, "session_id required"
    assert "message" in request, "message required"
    assert request["message"].strip(), "message cannot be empty"

    session_id = request["session_id"]
    message = request["message"]

    # ... rest of logic
```

### Checklist
- [ ] **DECISION**: Keep Pydantic (recommended) or switch to TypedDict?
- [ ] If keeping: No changes needed, mark as WONTFIX
- [ ] If removing: Replace with TypedDict
- [ ] If removing: Remove response_model from endpoints
- [ ] If removing: Add manual validation
- [ ] Test: Send POST request to /chat
- [ ] Test: Send invalid request (missing fields)
- [ ] Test: Verify error messages are clear

**Recommendation**: Mark as WONTFIX and keep Pydantic models.

---

# Summary Checklist

## Phase 1: Foundation
- [ ] TICKET-001: Add missing config constants ✓
- [ ] TICKET-002: Fix import issues in postgres_retriever.py ✓
- [ ] TICKET-003: Remove direct .env reading ✓
- [ ] TICKET-004: Fix imports in db/connection.py ✓

## Phase 2: Comment Out Parenting
- [ ] TICKET-005: Comment out parenting in main.py ✓
- [ ] TICKET-006: Update builder.py for parenting removal ✓
- [ ] TICKET-007: Update supervisor.py agent list ✓

## Phase 3: Simplify Initialization
- [ ] TICKET-008: Flatten main.py lifespan ✓
- [ ] TICKET-009: Simplify PostgreSQL retriever init ✓
- [ ] TICKET-010: Remove retry logic from DatabasePool ✓
- [x] TICKET-011: Simplify Qwen3Reranker error handling ✅ (Completed 2025-11-04)

## Phase 4: Retrieval Strategies
- [ ] TICKET-012: Create retrieval module structure ✓
- [ ] TICKET-013: Implement simple retrieval ✓
- [ ] TICKET-014: Implement rerank retrieval ✓
- [ ] TICKET-015: Implement advanced retrieval with query expansion ✓
- [ ] TICKET-016: Create retrieval factory ✓
- [ ] TICKET-017: Integrate factory into main.py ✓

## Phase 5: Cleanup
- [ ] TICKET-018: Remove global pool singleton ✓
- [ ] TICKET-019: Remove unused retriever implementations ✓
- [ ] TICKET-020: Remove add_documents method ✓
- [ ] TICKET-021: Simplify models (optional - recommend WONTFIX) ✓

---

# Testing Checklist

After completing all tickets:

- [ ] Test: Start app with database not running (should fail with clear error)
- [ ] Test: Start app with database running but empty (should warn and continue)
- [ ] Test: Start app with indexed documents (should succeed)
- [ ] Test: Send medication question with strategy="simple"
- [ ] Test: Send medication question with strategy="rerank"
- [ ] Test: Send medication question with strategy="advanced"
- [ ] Test: Verify query expansion in advanced strategy
- [ ] Test: Set PRELOAD_MODELS=True, verify models load at startup
- [ ] Test: Set PRELOAD_MODELS=False, verify lazy loading
- [ ] Test: Set ENABLE_PARENTING=False, verify parenting disabled
- [ ] Test: Health check endpoint works
- [ ] Test: Invalid session_id handling
- [ ] Test: Empty message handling
- [ ] Run: `ruff check app/` (should have no errors)
- [ ] Run: `mypy app/` (should have no type errors)
- [ ] Run: `pytest tests/` (all tests pass)

---

# Expected Outcomes

After completing all tickets:

1. **Simpler codebase**: ~40% fewer lines, easier to understand
2. **Fail-fast errors**: Clear error messages, no hidden failures
3. **Configurable**: Easy to switch retrieval strategies via .env
4. **Maintainable**: Next developer can make changes quickly
5. **Testable**: Can test each component independently
6. **Production-ready path**: Clear upgrade path when ready

**Estimated effort**: 12-16 hours for experienced developer
