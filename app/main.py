"""FastAPI application for medical chatbot."""

from contextlib import asynccontextmanager
from pathlib import Path
import pickle
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.config import settings
from app.core.session_store import SessionStore, InMemorySessionStore, SessionData
from app.core.retriever import DocumentRetriever, FAISSRetriever, Document
from app.core.hybrid_retriever import HybridRetriever
from app.core.reranker import CrossEncoderReranker
from app.graph.builder import build_medical_chatbot_graph
from app.graph.state import MedicalChatState
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global application state
app_state = {"graph": None, "session_store": None, "retriever": None}


def _initialize_session_store() -> SessionStore:
    """Initialize session store.

    Returns:
        InMemorySessionStore instance
    """
    session_store = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
    logger.info("✅ Session store initialized")
    return session_store


async def _load_medical_retriever() -> DocumentRetriever:
    """Load pre-computed medical document embeddings from disk.

    This function ALWAYS loads from disk. Embeddings must be pre-computed
    using: python -m src.precompute_embeddings

    Returns:
        FAISSRetriever with loaded embeddings

    Raises:
        FileNotFoundError: If embeddings not found at settings.index_path
        ValueError: If embeddings are corrupted or invalid
    """
    logger.info("📚 Loading pre-computed medical document embeddings...")

    try:
        retriever = await FAISSRetriever.load_index(
            path=settings.index_path,
            embedding_model=settings.embedding_model
        )
        logger.info("✅ Loaded pre-computed medical embeddings from disk")
        logger.info(f"📊 Index contains {len(retriever._documents)} documents")
        return retriever

    except FileNotFoundError as e:
        logger.error(f"❌ Medical embeddings not found at: {settings.index_path}")
        logger.error("💡 Please run: python -m src.precompute_embeddings")
        raise
    except ValueError as e:
        logger.error(f"❌ Medical embeddings corrupted: {e}")
        logger.error("💡 Please re-run: python -m src.precompute_embeddings")
        raise


async def _load_parenting_system() -> tuple[HybridRetriever, CrossEncoderReranker]:
    """Load pre-computed parenting video embeddings and reranker from disk.

    Linus: "Fail early, fail loudly, fail with useful error messages"

    The parenting agent is REQUIRED for production. This function fails-fast
    if embeddings are not available, preventing startup with incomplete system.

    To pre-compute embeddings, run:
        python -m src.precompute_parenting_embeddings --force

    Returns:
        Tuple of (HybridRetriever, CrossEncoderReranker)

    Raises:
        FileNotFoundError: If parenting index not found
        RuntimeError: If parenting index is corrupted or incomplete
    """
    logger.info("📚 Loading pre-computed parenting knowledge base...")
    parenting_index_path = settings.parenting_index_path

    # Fail-fast validation
    if not Path(parenting_index_path).exists():
        raise FileNotFoundError(
            f"Parenting index required but not found at: {parenting_index_path}\n"
            f"Run: python -m src.precompute_parenting_embeddings --force"
        )

    try:
        # Load embeddings
        import numpy as np
        from scipy.sparse import load_npz

        dense_embeddings = np.load(f"{parenting_index_path}/dense_embeddings.npy")
        sparse_embeddings = load_npz(f"{parenting_index_path}/sparse_embeddings.npz")

        # Load documents
        with open(f"{parenting_index_path}/child_documents.pkl", "rb") as f:
            child_documents = pickle.load(f)

        # Create hybrid retriever
        parenting_retriever = HybridRetriever(
            documents=child_documents,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
            dense_weight=settings.dense_weight,
            sparse_weight=settings.sparse_weight,
        )

        # Initialize reranker
        parenting_reranker = CrossEncoderReranker(
            model_name=settings.reranker_model,
            top_k=settings.reranker_top_k,
        )

        logger.info(f"✅ Loaded parenting knowledge base: {len(child_documents)} chunks")
        return parenting_retriever, parenting_reranker

    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Parenting index files incomplete: {e}\n"
            f"Run: python -m src.precompute_parenting_embeddings --force"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to load parenting system: {e}\n"
            f"Try regenerating: python -m src.precompute_parenting_embeddings --force"
        ) from e


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown.

    Linus: "Fail early, fail loudly, fail with useful error messages"

    All embeddings MUST be pre-computed before starting the service.
    This function loads pre-computed indices from disk for fast startup
    and fails-fast if any required dependencies are missing.

    Required precompute commands:
        python -m src.precompute_embeddings
        python -m src.precompute_parenting_embeddings --force

    Raises:
        FileNotFoundError: If required embeddings not found
        RuntimeError: If embeddings are corrupted
    """
    # Startup
    logger.info("🚀 Initializing Medical Chatbot application...")

    try:
        # Initialize session store
        app_state["session_store"] = _initialize_session_store()

        # Load pre-computed medical embeddings (fail-fast if not found)
        retriever = await _load_medical_retriever()
        app_state["retriever"] = retriever

        # Load pre-computed parenting embeddings (fail-fast if not found)
        parenting_retriever, parenting_reranker = await _load_parenting_system()
        app_state["parenting_retriever"] = parenting_retriever
        app_state["parenting_reranker"] = parenting_reranker

        # Build graph with all required dependencies
        app_state["graph"] = build_medical_chatbot_graph(
            retriever=retriever,
            parenting_retriever=parenting_retriever,
            parenting_reranker=parenting_reranker,
        )
        logger.info("✅ Medical chatbot graph compiled with all agents")
        logger.info("🎉 Application startup complete!")

        yield

    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise

    # Shutdown
    logger.info("👋 Shutting down application...")


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
async def chat(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store)
):
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
