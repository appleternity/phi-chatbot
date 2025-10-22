"""Integration tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from contextlib import asynccontextmanager


@pytest.fixture
async def client(test_checkpointer):
    """Create async test client with lifespan support and persistent checkpointer."""
    from app.main import app, app_state
    from app.graph.builder import build_medical_chatbot_graph

    # Manually trigger lifespan startup
    async with app.router.lifespan_context(app):
        # After lifespan startup, replace graph with test checkpointer version
        # This ensures API tests use persistent checkpoints like unit tests
        retriever = app_state.get("retriever")
        if retriever:
            app_state["graph"] = build_medical_chatbot_graph(retriever, checkpointer=test_checkpointer)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac


@pytest.mark.integration
async def test_health_endpoint(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.integration
async def test_chat_endpoint_new_session(client):
    """Test chat endpoint with new session."""
    response = await client.post(
        "/chat", json={"session_id": "test-api-new-1", "message": "I'm feeling anxious"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-api-new-1"
    assert data["agent"] in ["emotional_support", "supervisor"]
    assert len(data["message"]) > 0


@pytest.mark.integration
async def test_chat_endpoint_medical_query(client):
    """Test chat endpoint with medical query."""
    response = await client.post(
        "/chat",
        json={"session_id": "test-api-medical-1", "message": "What is Sertraline used for?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["agent"] in ["rag_agent", "supervisor"]
    assert "message" in data


@pytest.mark.integration
async def test_chat_endpoint_multi_turn(client):
    """Test multi-turn conversation."""
    session_id = "test-api-multiturn-1"

    # First message
    response1 = await client.post(
        "/chat", json={"session_id": session_id, "message": "Tell me about antidepressants"}
    )
    assert response1.status_code == 200
    agent1 = response1.json()["agent"]

    # Second message in same session
    response2 = await client.post(
        "/chat", json={"session_id": session_id, "message": "What about side effects?"}
    )
    assert response2.status_code == 200
    agent2 = response2.json()["agent"]

    # Should maintain same agent
    assert agent2 == agent1


@pytest.mark.integration
async def test_chat_endpoint_invalid_request(client):
    """Test chat endpoint with invalid request."""
    response = await client.post("/chat", json={"session_id": "test-invalid", "message": ""})

    # Should fail validation (empty message)
    assert response.status_code == 422


@pytest.mark.integration
async def test_concurrent_sessions(client):
    """Test handling multiple concurrent sessions."""
    sessions = [f"test-concurrent-{i}" for i in range(5)]

    # Send messages to different sessions
    responses = []
    for session_id in sessions:
        response = await client.post(
            "/chat", json={"session_id": session_id, "message": "I need help"}
        )
        responses.append(response)

    # All should succeed
    for response in responses:
        assert response.status_code == 200

    # Each should have different session_id
    session_ids = [r.json()["session_id"] for r in responses]
    assert len(set(session_ids)) == 5
