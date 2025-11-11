"""Unit tests for CustomEventHandler.

Tests the custom event handler that processes events emitted via
get_stream_writer() from nodes.
"""

import pytest

from app.api.event_handlers.custom_handler import CustomEventHandler
from app.models import StreamingSession, create_stage_event


class TestCustomEventHandler:
    """Test suite for CustomEventHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return CustomEventHandler()

    @pytest.fixture
    def session(self):
        """Create streaming session."""
        return StreamingSession(session_id="test-session", status="active")

    @pytest.mark.asyncio
    async def test_can_handle_custom_stage_event(self, handler, session):
        """Test handler recognizes custom stage events."""
        event = {
            "event": "on_custom",
            "data": {
                "type": "stage",
                "stage": "retrieval",
                "status": "started"
            }
        }
        assert await handler.can_handle(event, session) is True

    @pytest.mark.asyncio
    async def test_can_handle_rejects_non_custom_events(self, handler, session):
        """Test handler rejects non-custom events."""
        event = {
            "event": "on_chain_start",
            "data": {}
        }
        assert await handler.can_handle(event, session) is False

    @pytest.mark.asyncio
    async def test_can_handle_rejects_custom_without_type(self, handler, session):
        """Test handler rejects custom events without type field."""
        event = {
            "event": "on_custom",
            "data": {"some_field": "value"}
        }
        assert await handler.can_handle(event, session) is False

    @pytest.mark.asyncio
    async def test_handle_stage_started_event(self, handler, session):
        """Test handler processes stage started events."""
        event = {
            "event": "on_custom",
            "data": {
                "type": "stage",
                "stage": "retrieval",
                "status": "started"
            }
        }

        events = []
        async for sse_event in handler.handle(event, session):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].event == "stage"
        assert events[0].data["stage"] == "retrieval"
        assert events[0].data["status"] == "started"
        assert session.current_stage == "retrieval"

    @pytest.mark.asyncio
    async def test_handle_stage_complete_event_with_metadata(self, handler, session):
        """Test handler processes stage complete events with metadata."""
        event = {
            "event": "on_custom",
            "data": {
                "type": "stage",
                "stage": "routing",
                "status": "complete",
                "metadata": {"assigned_agent": "rag_agent"}
            }
        }

        events = []
        async for sse_event in handler.handle(event, session):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].event == "stage"
        assert events[0].data["stage"] == "routing"
        assert events[0].data["status"] == "complete"
        assert events[0].data["metadata"]["assigned_agent"] == "rag_agent"

    @pytest.mark.asyncio
    async def test_handle_unknown_event_type(self, handler, session):
        """Test handler gracefully handles unknown event types."""
        event = {
            "event": "on_custom",
            "data": {
                "type": "unknown_type",
                "some_data": "value"
            }
        }

        events = []
        async for sse_event in handler.handle(event, session):
            events.append(sse_event)

        # Should yield nothing for unknown types
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_all_stage_types(self, handler, session):
        """Test handler processes all stage types correctly."""
        stages = [
            ("routing", "started"),
            ("routing", "complete"),
            ("retrieval", "started"),
            ("retrieval", "complete"),
            ("reranking", "started"),
            ("reranking", "complete"),
            ("generation", "started"),
        ]

        for stage, status in stages:
            event = {
                "event": "on_custom",
                "data": {
                    "type": "stage",
                    "stage": stage,
                    "status": status
                }
            }

            events = []
            async for sse_event in handler.handle(event, session):
                events.append(sse_event)

            assert len(events) == 1
            assert events[0].event == "stage"
            assert events[0].data["stage"] == stage
            assert events[0].data["status"] == status

            # Verify session state updated for "started" events
            if status == "started":
                assert session.current_stage == stage
