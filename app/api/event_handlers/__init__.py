"""Event handler system for SSE streaming.

This module provides a clean event dispatcher pattern for handling LangGraph events
and converting them to SSE events for the frontend.

Architecture:
- EventDispatcher: Routes events to appropriate handlers
- EventHandler: Protocol for all handler implementations
- Handler Classes: Specialized handlers for different event types

Handler Registration Order Matters:
1. RerankStartHandler (most specific: "rerank" in node name)
2. ChainStartHandler (specific: supervisor, rag_agent, emotional_support)
3. ModelStreamHandler (token streaming)
4. ModelEndHandler (LLM completion)
5. ChainErrorHandler (error handling)

Usage:
    from app.api.event_handlers import create_event_dispatcher

    dispatcher = create_event_dispatcher()
    async for sse_event in dispatcher.dispatch(langgraph_event, session):
        yield sse_event.to_sse_format()
"""

from .dispatcher import EventDispatcher
from .base import EventHandler
from .chain_start_handler import ChainStartHandler
from .rerank_start_handler import RerankStartHandler
from .model_stream_handler import ModelStreamHandler
from .model_end_handler import ModelEndHandler
from .chain_error_handler import ChainErrorHandler

__all__ = [
    "EventDispatcher",
    "EventHandler",
    "ChainStartHandler",
    "RerankStartHandler",
    "ModelStreamHandler",
    "ModelEndHandler",
    "ChainErrorHandler",
    "create_event_dispatcher",
]


def create_event_dispatcher() -> EventDispatcher:
    """Create and configure event dispatcher with all handlers.

    Handlers are registered in priority order:
    1. RerankStartHandler - Most specific (rerank in node name)
    2. ChainStartHandler - Specific nodes (supervisor, agents)
    3. ModelStreamHandler - Token streaming
    4. ModelEndHandler - LLM completion
    5. ChainErrorHandler - Error handling

    Returns:
        Configured EventDispatcher ready for use
    """
    dispatcher = EventDispatcher()

    # Register handlers in priority order (first match wins)
    dispatcher.register(RerankStartHandler())
    dispatcher.register(ChainStartHandler())
    dispatcher.register(ModelStreamHandler())
    dispatcher.register(ModelEndHandler())
    dispatcher.register(ChainErrorHandler())

    return dispatcher
