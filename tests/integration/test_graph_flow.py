"""Integration tests for graph execution flow."""

import pytest
from app.graph.builder import build_medical_chatbot_graph
from app.graph.state import MedicalChatState
from app.core.retriever import FAISSRetriever, Document


@pytest.fixture
def graph_with_mock_data(session_retriever, parenting_retriever, parenting_reranker, test_checkpointer):
    """Create graph with session retriever and checkpointer.

    Reuses session_retriever to avoid re-loading the SentenceTransformer model
    (saves ~2.8s per test). The session_retriever already has sample documents.
    """
    graph = build_medical_chatbot_graph(
        session_retriever,
        parenting_retriever,
        parenting_reranker,
        checkpointer=test_checkpointer
    )
    return graph


@pytest.mark.asyncio
@pytest.mark.integration
async def test_supervisor_classification_flow(graph_with_mock_data):
    """Test that supervisor correctly classifies and routes."""
    graph = graph_with_mock_data

    # Test medical information query
    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}], session_id="test-med-1"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-med-1"}})

    assert result["assigned_agent"] == "rag_agent"
    assert len(result["messages"]) > 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_emotional_support_flow(graph_with_mock_data):
    """Test emotional support agent flow."""
    graph = graph_with_mock_data

    state = MedicalChatState(
        messages=[{"role": "user", "content": "I'm feeling really anxious today"}],
        session_id="test-emotional-1",
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-emotional-1"}})

    assert result["assigned_agent"] == "emotional_support"
    assert len(result["messages"]) > 1
    # Response should be empathetic
    response_text = result["messages"][-1].content.lower()
    assert any(word in response_text for word in ["understand", "feel", "hear", "support"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_session_persistence_flow(graph_with_mock_data):
    """Test that session assignment persists across messages."""
    graph = graph_with_mock_data

    # First message - should classify
    state1 = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}], session_id="test-persist-1"
    )

    result1 = await graph.ainvoke(state1, {"configurable": {"thread_id": "test-persist-1"}})
    assigned_agent = result1["assigned_agent"]
    assert assigned_agent == "rag_agent"

    # Second message - should use assigned agent
    state2 = MedicalChatState(
        messages=[{"role": "user", "content": "What about side effects?"}],
        session_id="test-persist-1",
        assigned_agent=assigned_agent,
    )

    result2 = await graph.ainvoke(state2, {"configurable": {"thread_id": "test-persist-1"}})

    # Should maintain same agent assignment
    assert result2["assigned_agent"] == assigned_agent
