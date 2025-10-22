"""Unit tests for session store."""

import pytest
import asyncio
from app.core.session_store import InMemorySessionStore, SessionData


@pytest.mark.asyncio
async def test_session_create_and_retrieve():
    """Test creating and retrieving sessions."""
    store = InMemorySessionStore()
    session = SessionData(session_id="test-123", assigned_agent="rag_agent")

    await store.save_session("test-123", session)
    retrieved = await store.get_session("test-123")

    assert retrieved is not None
    assert retrieved.session_id == "test-123"
    assert retrieved.assigned_agent == "rag_agent"


@pytest.mark.asyncio
async def test_session_update():
    """Test updating existing session."""
    store = InMemorySessionStore()
    session = SessionData(session_id="test-update", assigned_agent="emotional_support")

    await store.save_session("test-update", session)

    # Update session
    session.assigned_agent = "rag_agent"
    session.metadata = {"updated": True}
    await store.save_session("test-update", session)

    # Retrieve and verify
    retrieved = await store.get_session("test-update")
    assert retrieved.assigned_agent == "rag_agent"
    assert retrieved.metadata["updated"] is True


@pytest.mark.asyncio
async def test_session_expiration():
    """Test session TTL expiration."""
    store = InMemorySessionStore(ttl_seconds=1)
    session = SessionData(session_id="test-expire")

    await store.save_session("test-expire", session)

    # Wait for expiration
    await asyncio.sleep(2)

    # Should be None after expiration
    retrieved = await store.get_session("test-expire")
    assert retrieved is None


@pytest.mark.asyncio
async def test_session_delete():
    """Test deleting sessions."""
    store = InMemorySessionStore()
    session = SessionData(session_id="test-delete")

    await store.save_session("test-delete", session)
    await store.delete_session("test-delete")

    retrieved = await store.get_session("test-delete")
    assert retrieved is None


@pytest.mark.asyncio
async def test_multiple_sessions():
    """Test managing multiple sessions concurrently."""
    store = InMemorySessionStore()

    # Create multiple sessions
    for i in range(5):
        session = SessionData(session_id=f"test-{i}", assigned_agent=f"agent-{i}")
        await store.save_session(f"test-{i}", session)

    # Verify all exist
    for i in range(5):
        retrieved = await store.get_session(f"test-{i}")
        assert retrieved is not None
        assert retrieved.assigned_agent == f"agent-{i}"


def test_clear_expired_sessions():
    """Test clearing expired sessions."""
    store = InMemorySessionStore(ttl_seconds=1)

    # Create sessions
    import time

    for i in range(3):
        session = SessionData(session_id=f"expire-{i}")
        import asyncio

        asyncio.run(store.save_session(f"expire-{i}", session))

    # Wait for expiration
    time.sleep(2)

    # Clear expired
    cleared_count = store.clear_expired_sessions()
    assert cleared_count == 3
