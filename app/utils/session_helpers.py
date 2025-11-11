"""Shared session management utilities for streaming and non-streaming modes.

This module extracts common session logic to avoid duplication between
streaming and non-streaming endpoints. Both modes should use these utilities
to ensure consistent session handling.
"""

import uuid
import logging
from typing import Optional, Tuple

from fastapi import HTTPException

from app.core.session_store import SessionData, SessionStore
from app.graph.state import MedicalChatState

logger = logging.getLogger(__name__)


async def create_or_load_session(
    session_id: Optional[str],
    user_id: str,
    session_store: SessionStore,
) -> Tuple[str, SessionData]:
    """Create new session or load existing one with ownership validation.

    This function handles the complete session lifecycle:
    1. If session_id is None, creates a new session with UUID
    2. If session_id provided, loads from store and validates ownership
    3. Returns tuple of (session_id, session_data) for use by caller

    Args:
        session_id: Optional session ID from request. None creates new session.
        user_id: User ID from request for session creation and ownership validation
        session_store: Session store instance for persistence operations

    Returns:
        Tuple[str, SessionData]: (session_id, session_data)
            - session_id: Either newly created or validated existing session ID
            - session_data: SessionData object with user_id, assigned_agent, metadata

    Raises:
        HTTPException 404: Session not found or expired
        HTTPException 403: Session belongs to different user

    Example:
        >>> session_id, session = await create_or_load_session(
        ...     request.session_id, request.user_id, session_store
        ... )
        >>> # Use session_id and session for graph invocation
    """
    if session_id is None:
        # Create new session with UUID
        new_session_id = str(uuid.uuid4())
        session = SessionData(session_id=new_session_id, user_id=user_id)
        logger.info(f"🆕 New session {new_session_id} for user {user_id}")
        return new_session_id, session
    else:
        # Load existing session
        session = await session_store.get_session(session_id)
        if session is None:
            # Session not found or expired - create new session instead of failing
            # This handles cases where:
            # 1. Backend restarted (in-memory store lost)
            # 2. Session TTL expired
            # 3. Frontend has stale session_id in localStorage
            logger.warning(
                f"⚠️ Session {session_id} not found or expired, creating new session for user {user_id}"
            )
            new_session_id = str(uuid.uuid4())
            session = SessionData(session_id=new_session_id, user_id=user_id)
            logger.info(f"🆕 New session {new_session_id} for user {user_id} (replacing expired {session_id})")
            return new_session_id, session

        # Validate user ownership
        if session.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail=f"Session {session_id} does not belong to user {user_id}"
            )

        logger.info(
            f"📂 Loaded session {session_id} for user {user_id}, "
            f"agent: {session.assigned_agent}"
        )
        return session_id, session


def build_graph_state(
    message: str,
    session_id: str,
    session_data: SessionData,
) -> MedicalChatState:
    """Build LangGraph state from message and session data.

    Constructs MedicalChatState with consistent structure for both
    streaming and non-streaming modes.

    Args:
        message: User message content
        session_id: Session identifier for the conversation
        session_data: Session data with assigned_agent and metadata

    Returns:
        MedicalChatState: Initialized state for graph invocation

    Example:
        >>> state = build_graph_state(
        ...     "What is aripiprazole?",
        ...     session_id,
        ...     session_data
        ... )
        >>> result = await graph.ainvoke(state, config)
    """
    return MedicalChatState(
        messages=[{"role": "user", "content": message}],
        session_id=session_id,
        assigned_agent=session_data.assigned_agent,
        metadata=session_data.metadata,
    )


def build_graph_config(session_id: str) -> dict:
    """Build LangGraph configuration with thread_id for conversation memory.

    Creates configuration dict that enables LangGraph's checkpointing system
    to maintain conversation history across invocations.

    Args:
        session_id: Session identifier to use as thread_id

    Returns:
        dict: Configuration dict with thread_id for LangGraph

    Example:
        >>> config = build_graph_config(session_id)
        >>> result = await graph.ainvoke(state, config)
    """
    return {"configurable": {"thread_id": session_id}}


async def persist_session_updates(
    session_id: str,
    session_data: SessionData,
    assigned_agent: Optional[str],
    metadata: Optional[dict],
    session_store: SessionStore,
) -> None:
    """Persist session updates after graph execution.

    Updates session with assigned_agent and metadata from graph result,
    then saves to session store. This ensures session state is preserved
    across multiple invocations.

    Args:
        session_id: Session identifier
        session_data: Session data object to update
        assigned_agent: Agent assigned by graph (from result["assigned_agent"])
        metadata: Metadata from graph result (from result["metadata"])
        session_store: Session store instance for persistence

    Example:
        >>> result = await graph.ainvoke(state, config)
        >>> await persist_session_updates(
        ...     session_id, session,
        ...     assigned_agent=result.get("assigned_agent"),
        ...     metadata=result.get("metadata"),
        ...     session_store=session_store
        ... )
    """
    # Update assigned_agent if provided by graph
    if assigned_agent is not None:
        session_data.assigned_agent = assigned_agent

    # Update metadata if provided by graph
    if metadata is not None:
        session_data.metadata = metadata

    # Persist to store
    await session_store.save_session(session_id, session_data)
    logger.debug(f"💾 Session {session_id} persisted with agent: {assigned_agent}")
