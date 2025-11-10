"""FastAPI application for medical chatbot."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import HealthResponse, ChatRequest, ChatResponse
from app.config import settings
from app.core.session_store import InMemorySessionStore, SessionStore, SessionData
from app.db.connection import DatabasePool
from app.graph.state import MedicalChatState
from app.retrieval import get_retriever
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.graph.builder import build_medical_chatbot_graph
import logging
import uuid
from typing import Optional

# Import routers
from app.api import streaming_router

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
        max_length=8192,
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
app.include_router(streaming_router)


# Dependency to get session store
def get_session_store() -> SessionStore:
    """Get session store from app state."""
    return app_state["session_store"]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status and version
    """
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store)
):
    """Main chat endpoint with user-aware session management.

    This endpoint:
    1. Creates new session with UUID if session_id is None
    2. Loads existing session and validates user ownership
    3. Constructs graph state with session data
    4. Invokes the graph (routes to appropriate agent)
    5. Updates session with results
    6. Returns the agent's response with session_id

    Args:
        request: Chat request with user_id, optional session_id, and message
        session_store: Session store dependency

    Returns:
        Chat response with session_id (new or existing), message, agent, metadata

    Raises:
        HTTPException 404: Session not found or expired
        HTTPException 403: Session belongs to different user
        HTTPException 500: Internal server error
    """
    try:
        # Handle session creation or loading
        if request.session_id is None:
            # Create new session with UUID
            session_id = str(uuid.uuid4())
            session = SessionData(session_id=session_id, user_id=request.user_id)
            logger.info(f"🆕 New session {session_id} for user {request.user_id}")
        else:
            # Load existing session
            session = await session_store.get_session(request.session_id)
            if session is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {request.session_id} not found or expired"
                )

            # Validate user ownership
            if session.user_id != request.user_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"Session {request.session_id} does not belong to user {request.user_id}"
                )

            session_id = request.session_id
            logger.info(
                f"📂 Loaded session {session_id} for user {request.user_id}, "
                f"agent: {session.assigned_agent}"
            )

        # Construct graph state
        state = MedicalChatState(
            messages=[{"role": "user", "content": request.message}],
            session_id=session_id,
            assigned_agent=session.assigned_agent,
            metadata=session.metadata,
        )

        # Invoke graph with thread_id for conversation memory
        config = {"configurable": {"thread_id": session_id}}
        logger.debug(f"🤖 Invoking graph for session: {session_id}")

        result = await app_state["graph"].ainvoke(state, config)

        # Extract response from last message
        last_message = result["messages"][-1]
        response_text = last_message.content
        assigned_agent = result.get("assigned_agent", session.assigned_agent)

        logger.info(f"✅ Response by {assigned_agent} for session: {session_id}")

        # Update session
        session.assigned_agent = assigned_agent
        session.metadata = result.get("metadata", session.metadata)
        await session_store.save_session(session_id, session)

        # Always return session_id (whether new or existing)
        return ChatResponse(
            session_id=session_id,
            message=response_text,
            agent=assigned_agent or "supervisor",
            metadata=result.get("metadata"),
        )

    except HTTPException:
        # Re-raise HTTP exceptions (404, 403)
        raise
    except Exception as e:
        logger.error(f"❌ Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
        timeout_keep_alive=120,  # 120 seconds keep-alive for long RAG operations
    )
