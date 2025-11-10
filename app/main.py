"""FastAPI application for medical chatbot."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import HealthResponse
from app.config import settings
from app.core.session_store import InMemorySessionStore
from app.db.connection import DatabasePool
from app.retrieval import get_retriever
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.graph.builder import build_medical_chatbot_graph
import logging

# Import routers
from app.api import streaming

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global application state
app_state = {
    "graph": None,
    "session_store": None,
    "retriever": None,
    "db_pool": None,
}


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
    pool = DatabasePool(min_size=5, max_size=20)
    await pool.initialize()
    app_state["db_pool"] = pool

    # 3. Verify database setup
    # Check pgvector extension
    pgvector_exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
    )
    assert pgvector_exists, (
        "pgvector extension not found. Run: python -m app.db.schema"
    )

    # Check vector_chunks table
    # TODO: We might consider setting the "vector_chunks" table name as a constant in config
    table_exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'vector_chunks')"
    )
    assert table_exists, (
        "vector_chunks table not found. Run: python -m app.db.schema"
    )

    # Get document count
    doc_count = await pool.fetchval("SELECT COUNT(*) FROM vector_chunks")
    logger.info(f"📊 Database contains {doc_count} indexed chunks")

    assert doc_count > 0, (
        "No documents indexed. Run: python -m src.embeddings.cli index --input data/chunking_final"
    )

    logger.info("✅ PostgreSQL connection established")

    # 3. Initialize embedding encoder
    logger.info(f"Initializing encoder: {settings.EMBEDDING_MODEL}")
    encoder = Qwen3EmbeddingEncoder(
        model_name=settings.EMBEDDING_MODEL,
        device="mps",
        batch_size=1,
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
            batch_size=1,
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

    # 6. Build graph
    logger.info("Building LangGraph...")
    app_state["graph"] = build_medical_chatbot_graph(
        retriever=retriever,
    )
    logger.info("✅ Medical chatbot graph compiled")

    # 7. Log startup complete
    logger.info("🎉 Application startup complete!")
    logger.info(f"   Mode: Medication Q&A")
    logger.info(f"   Strategy: {settings.RETRIEVAL_STRATEGY}")
    logger.info(f"   Preload: {'Enabled' if settings.PRELOAD_MODELS else 'Lazy loading'}")

    # ========================================================================
    # YIELD TO APP
    # ========================================================================
    yield

    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    logger.info("👋 Shutting down application...")

    if app_state.get("db_pool"):
        await app_state["db_pool"].close()
        logger.info("✅ Database connection pool closed")

    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Medical Chatbot API",
    description="Multi-agent medical chatbot with emotional support and medical information retrieval",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register router
app.include_router(streaming.router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status and version
    """
    return HealthResponse(status="healthy", version="0.1.0")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())
