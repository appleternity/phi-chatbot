"""FastAPI application for medical chatbot."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.models import HealthResponse, ChatRequest, ChatResponse, ChatStreamRequest
from app.config import settings
from app.core.session_store import InMemorySessionStore, SessionStore, SessionData
from app.db.connection import DatabasePool
from app.graph.state import MedicalChatState
from app.retrieval.factory import create_retriever
from app.embeddings import create_embedding_provider
from app.core.qwen3_reranker import Qwen3Reranker
from app.graph.builder import build_medical_chatbot_graph
from app.dependencies import get_graph, get_session_store
import logging
import uuid
from typing import Optional

# Import streaming logic
from app.api.streaming import stream_chat_events

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
    app.state.session_store = session_store
    logger.info("✅ Session store initialized")

    # 2. Initialize database connection pool
    logger.info("Connecting to PostgreSQL...")
    pool = DatabasePool(min_size=5, max_size=20)
    await pool.initialize()
    app.state.db_pool = pool

    # 3. Verify database setup
    # Check pgvector extension
    pgvector_exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
    )
    assert pgvector_exists, (
        "pgvector extension not found. Run: python -m app.db.schema"
    )

    # Check vector_chunks table (use settings.table_name)
    # Security: Use parameterized query to prevent SQL injection
    table_exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_name = $1)",
        settings.table_name
    )
    assert table_exists, (
        f"{settings.table_name} table not found. Run: python -m src.embeddings.ingest_embeddings"
    )

    # Get document count
    # Security: table_name quoted to support special characters (e.g., hyphens)
    # PostgreSQL doesn't support parameterized identifiers, so quoted f-string is safe
    doc_count = await pool.fetchval(f'SELECT COUNT(*) FROM "{settings.table_name}"')
    logger.info(f"📊 Database contains {doc_count} indexed chunks")

    assert doc_count > 0, (
        "No documents indexed. Run: python -m src.embeddings.generate_embeddings && python -m src.embeddings.ingest_embeddings"
    )

    logger.info("✅ PostgreSQL connection established")

    # 3. Initialize embedding provider with explicit parameters
    logger.info(f"Initializing embedding provider: {settings.embedding_provider}")
    encoder = create_embedding_provider(
        provider_type=settings.embedding_provider,
        embedding_model=settings.EMBEDDING_MODEL,
        device=settings.device,
        batch_size=settings.batch_size,
        openai_api_key=settings.openai_api_key,
        aliyun_api_key=settings.aliyun_api_key
    )

    # NOTE: Dimension validation removed for simplicity.
    # If we need validation in the future, we could:
    # 1. Generate a test embedding: test_embedding = encoder.encode("test")
    # 2. Try inserting into database and check for dimension mismatch error
    # 3. Or query schema_metadata and compare dimensions
    # However, dimension mismatches should rarely happen in practice.
    # The database will fail fast on first insert if dimensions don't match.

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

    # 5. Create retriever with explicit strategy parameter
    logger.info(f"Creating retriever (strategy: {settings.RETRIEVAL_STRATEGY}, table: {settings.table_name})...")
    retriever = create_retriever(
        strategy=settings.RETRIEVAL_STRATEGY,
        pool=pool,
        encoder=encoder,
        reranker=reranker,
        table_name=settings.table_name
    )
    app.state.retriever = retriever
    logger.info("✅ Retriever initialized")

    # 6. Build graph
    logger.info("Building LangGraph...")
    app.state.graph = build_medical_chatbot_graph(
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

    if hasattr(app.state, "db_pool") and app.state.db_pool:
        await app.state.db_pool.close()
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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status and version
    """
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/chat", response_model=None)
async def chat(
    request: ChatRequest,
    fastapi_request: Request,
    graph = Depends(get_graph),
    session_store: SessionStore = Depends(get_session_store)
):
    """Unified chat endpoint with streaming and non-streaming modes.

    This endpoint supports both traditional request/response and SSE streaming
    based on the `streaming` parameter in the request.

    **Non-Streaming Mode (streaming=False, default):**
    1. Creates new session with UUID if session_id is None
    2. Loads existing session and validates user ownership
    3. Constructs graph state with session data
    4. Invokes the graph (routes to appropriate agent)
    5. Updates session with results
    6. Returns the complete agent response with session_id

    **Streaming Mode (streaming=True):**
    1. Creates new session with UUID if session_id is None
    2. Returns SSE stream with:
       - Processing stage indicators (retrieval, reranking, generation)
       - Token-by-token response streaming
       - Error handling and cancellation support
    3. Session updates handled within streaming logic

    Args:
        request: Chat request with user_id, optional session_id, message, and streaming flag
        fastapi_request: FastAPI Request object for disconnect detection
        session_store: Session store dependency

    Returns:
        - ChatResponse (JSON) if streaming=False
        - StreamingResponse (SSE) if streaming=True

    Raises:
        HTTPException 404: Session not found or expired
        HTTPException 403: Session belongs to different user
        HTTPException 500: Internal server error
    """
    try:
        # Import shared session utilities
        from app.utils.session_helpers import (
            create_or_load_session,
            build_graph_state,
            build_graph_config,
            persist_session_updates
        )

        # Create or load session with ownership validation (shared logic)
        session_id, session = await create_or_load_session(
            request.session_id, request.user_id, session_store
        )
        logger.info(f"Session {session_id} ready (streaming={request.streaming})")

        # Route to streaming or non-streaming based on request parameter
        if request.streaming:
            # Streaming mode: Return SSE response
            logger.info(f"Streaming mode enabled for session {session_id}")

            # Create ChatStreamRequest for streaming logic
            stream_request = ChatStreamRequest(
                message=request.message,
                session_id=session_id
            )

            return StreamingResponse(
                stream_chat_events(
                    stream_request,
                    graph,
                    fastapi_request,
                    session_store,  # Pass session_store for persistence
                    request.user_id  # Pass user_id for session creation
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )
        else:
            # Non-streaming mode: Traditional request/response
            logger.info(f"📄 Non-streaming mode for session {session_id}")

            # Build graph state using shared utility
            state = build_graph_state(request.message, session_id, session)

            # Build graph config using shared utility
            config = build_graph_config(session_id)
            logger.debug(f"🤖 Invoking graph for session: {session_id}")

            # Invoke graph with state and config
            result = await graph.ainvoke(state, config)

            # Extract response from last message
            last_message = result["messages"][-1]
            response_text = last_message.content
            assigned_agent = result.get("assigned_agent", session.assigned_agent)

            logger.info(f"✅ Response by {assigned_agent} for session: {session_id}")

            # Persist session updates using shared utility
            await persist_session_updates(
                session_id,
                session,
                assigned_agent=assigned_agent,
                metadata=result.get("metadata"),
                session_store=session_store
            )

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
