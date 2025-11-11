"""Event handler system for SSE streaming.

This module provides event handlers for processing LangGraph streaming events
and converting them to SSE events for the frontend.

Architecture:
- CustomEventHandler: Handles custom events from get_stream_writer()
- ModelStreamHandler: Handles LLM token streaming from stream_mode="messages"

Simplified Handler Architecture (using stream_mode + get_stream_writer):
- stream_mode=["messages", "custom"] provides direct access to tokens and stage events
- Nodes emit custom events via get_stream_writer() for stage transitions
- Direct handler invocation (no dispatcher pattern)
- Error handling via natural exception propagation to streaming.py try/catch

Handler Usage:
- CustomEventHandler processes stage events from stream_mode="custom"
- ModelStreamHandler processes token streaming from stream_mode="messages"

Usage:
    from app.api.event_handlers import CustomEventHandler, ModelStreamHandler

    custom_handler = CustomEventHandler()
    model_handler = ModelStreamHandler()

    # For stream_mode="custom"
    async for sse_event in custom_handler.handle_custom(chunk, session):
        yield sse_event.to_sse_format()

    # For stream_mode="messages"
    async for sse_event in model_handler.handle_message(message, metadata, session):
        yield sse_event.to_sse_format()

Removed handlers (no longer needed):
- ChainStartHandler - Replaced by get_stream_writer() in nodes
- RerankStartHandler - Replaced by get_stream_writer() in nodes
- ModelEndHandler - No longer needed with direct emission
- ChainErrorHandler - Errors propagate to streaming.py try/catch
"""

from .custom_handler import CustomEventHandler
from .model_stream_handler import ModelStreamHandler

__all__ = [
    "CustomEventHandler",
    "ModelStreamHandler",
]
