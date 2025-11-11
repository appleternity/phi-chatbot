"""FastAPI dependency injection for application components.

This module provides dependency functions that can be used with FastAPI's
Depends() mechanism to access application state in a clean, testable way.

Usage:
    from fastapi import Depends
    from app.dependencies import get_graph, get_session_store

    @app.post("/endpoint")
    async def endpoint(
        graph = Depends(get_graph),
        session_store = Depends(get_session_store)
    ):
        # Use graph and session_store
        pass
"""

from fastapi import Request
from langgraph.graph import StateGraph
from app.core.session_store import SessionStore


def get_graph(request: Request) -> StateGraph:
    """Get the LangGraph instance from application state.

    Args:
        request: FastAPI Request object with app.state access

    Returns:
        Compiled LangGraph medical chatbot graph

    Raises:
        RuntimeError: If graph not initialized (app startup failed)
    """
    if not hasattr(request.app.state, "graph") or request.app.state.graph is None:
        raise RuntimeError(
            "Graph not initialized. Application startup may have failed."
        )
    return request.app.state.graph


def get_session_store(request: Request) -> SessionStore:
    """Get the session store from application state.

    Args:
        request: FastAPI Request object with app.state access

    Returns:
        SessionStore instance (InMemorySessionStore or Redis-backed)

    Raises:
        RuntimeError: If session store not initialized (app startup failed)
    """
    if not hasattr(request.app.state, "session_store") or request.app.state.session_store is None:
        raise RuntimeError(
            "Session store not initialized. Application startup may have failed."
        )
    return request.app.state.session_store
