"""FastAPI application for medical chatbot."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.config import settings
from app.core.session_store import SessionStore, InMemorySessionStore, SessionData
from app.core.retriever import DocumentRetriever, FAISSRetriever
from app.graph.builder import build_medical_chatbot_graph
from app.graph.state import MedicalChatState
from app.utils.data_loader import load_medical_documents
import logging

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global application state
app_state = {"graph": None, "session_store": None, "retriever": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("🚀 Initializing Medical Chatbot application...")

    # Initialize session store
    app_state["session_store"] = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
    logger.info("✅ Session store initialized")

    # Initialize retriever and load documents
    logger.info("📚 Initializing document retriever...")

    retriever = FAISSRetriever(embedding_model=settings.embedding_model)

    # Load from persistent index or compute from source (fail-fast, no fallback)
    if settings.use_persistent_index and not settings.force_recompute:
        # Load from disk - will raise exception if not found or corrupted
        retriever = await FAISSRetriever.load_index(
            path=settings.index_path,
            embedding_model=settings.embedding_model
        )
        logger.info("✅ Loaded pre-computed embeddings from disk")
        logger.info(f"📊 Index contains {len(retriever._documents)} documents")
    else:
        # Compute embeddings from source
        if settings.force_recompute:
            logger.info("🔄 Force recompute enabled - computing embeddings from source...")
        else:
            logger.info("💾 Persistent index disabled - computing embeddings from source...")

        docs = await load_medical_documents()
        await retriever.add_documents(docs)
        logger.info(f"✅ Loaded {len(docs)} medical documents into retriever")

    app_state["retriever"] = retriever

    # Build graph
    app_state["graph"] = build_medical_chatbot_graph(retriever)
    logger.info("✅ Medical chatbot graph compiled")

    logger.info("🎉 Application startup complete!")

    yield

    # Shutdown
    logger.info("👋 Shutting down application...")
    # Cleanup if needed


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


# Dependency injection
def get_session_store() -> SessionStore:
    """Get session store instance."""
    return app_state["session_store"]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status and version
    """
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session_store: SessionStore = Depends(get_session_store)):
    """Main chat endpoint with session-aware routing.

    This endpoint:
    1. Loads or creates a session
    2. Constructs graph state with session data
    3. Invokes the graph (routes to appropriate agent)
    4. Updates session with results
    5. Returns the agent's response

    Args:
        request: Chat request with session_id and message
        session_store: Session store dependency

    Returns:
        Chat response with agent message

    Raises:
        HTTPException: If processing fails
    """
    try:
        logger.info(f"📨 Received message from session: {request.session_id}")

        # Load or create session
        session = await session_store.get_session(request.session_id)
        if session is None:
            session = SessionData(session_id=request.session_id)
            logger.info(f"🆕 Created new session: {request.session_id}")
        else:
            logger.info(
                f"📂 Loaded existing session: {request.session_id}, "
                f"assigned_agent: {session.assigned_agent}"
            )

        # Construct graph state
        state = MedicalChatState(
            messages=[{"role": "user", "content": request.message}],
            session_id=request.session_id,
            assigned_agent=session.assigned_agent,
            metadata=session.metadata,
        )

        # Invoke graph with thread_id for conversation memory
        config = {"configurable": {"thread_id": request.session_id}}
        logger.debug(f"🤖 Invoking graph for session: {request.session_id}")

        result = await app_state["graph"].ainvoke(state, config)

        # Extract response from last message
        last_message = result["messages"][-1]
        response_text = last_message.content
        assigned_agent = result.get("assigned_agent", session.assigned_agent)

        logger.info(
            f"✅ Response generated by {assigned_agent} for session: {request.session_id}"
        )

        # Update session
        session.assigned_agent = assigned_agent
        session.metadata = result.get("metadata", session.metadata)
        await session_store.save_session(request.session_id, session)

        return ChatResponse(
            session_id=request.session_id,
            message=response_text,
            agent=assigned_agent or "supervisor",
            metadata=result.get("metadata"),
        )

    except Exception as e:
        logger.error(f"❌ Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())
