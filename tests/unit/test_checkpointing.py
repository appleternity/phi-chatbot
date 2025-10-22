"""Unit tests for checkpointing and state serialization.

These tests specifically verify that the two-layer serialization fix works:
1. Closure pattern prevents outer graph from checkpointing non-serializable objects
2. checkpointer=False prevents inner agent from checkpointing retriever

This test suite was added to catch the FAISSRetriever serialization bug that
wasn't caught by existing integration tests.
"""

import pytest
from app.graph.builder import build_medical_chatbot_graph
from app.graph.state import MedicalChatState
from app.agents.rag_agent import create_rag_agent
from app.core.retriever import FAISSRetriever, Document


def test_rag_agent_checkpointer_disabled(session_retriever):
    """Verify RAG agent has checkpointing explicitly disabled.

    This is critical to prevent the inner agent from attempting to
    serialize the temporary state_with_retriever dict that contains
    the non-serializable FAISSRetriever object.
    """
    rag_agent = create_rag_agent(session_retriever)

    # Critical: checkpointer must be False to prevent serialization
    assert rag_agent.checkpointer is False, (
        "RAG agent must have checkpointer=False to prevent "
        "serialization of retriever in temporary state"
    )


@pytest.mark.asyncio
async def test_graph_checkpoint_excludes_non_serializable(session_retriever, test_checkpointer):
    """Verify checkpointed state excludes retriever and rag_agent.

    The closure pattern should ensure these objects are captured in
    closure scope rather than being added to the checkpointed state.
    """
    graph = build_medical_chatbot_graph(session_retriever, checkpointer=test_checkpointer)
    config = {"configurable": {"thread_id": "test-checkpoint-exclusion"}}

    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is TestMed?"}],
        session_id="test-1"
    )

    result = await graph.ainvoke(state, config)

    # Get checkpoint to inspect what's actually saved
    checkpoint = await graph.aget_state(config)

    # CRITICAL: These objects must NOT be in checkpoint
    # If they are, msgpack serialization will fail
    assert "retriever" not in checkpoint.values, (
        "Retriever should not be in checkpointed state - "
        "it's non-serializable and should be in closure scope"
    )
    assert "_rag_agent" not in checkpoint.values, (
        "RAG agent should not be in checkpointed state - "
        "it's non-serializable and should be in closure scope"
    )

    # These SHOULD be in checkpoint for conversation persistence
    assert "messages" in checkpoint.values
    assert "session_id" in checkpoint.values
    assert "assigned_agent" in checkpoint.values


@pytest.mark.asyncio
async def test_checkpoint_state_is_serializable(session_retriever, test_checkpointer):
    """Verify that checkpointed state can actually be serialized with msgpack.

    This is the test that would have caught the original FAISSRetriever
    serialization bug if it had existed before the fix.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    graph = build_medical_chatbot_graph(session_retriever, checkpointer=test_checkpointer)

    config = {"configurable": {"thread_id": "test-serialize-check"}}
    state = MedicalChatState(
        messages=[{"role": "user", "content": "Tell me about DrugA"}],
        session_id="test-serialize"
    )

    # This invocation will trigger RAG agent with retriever in temp state
    await graph.ainvoke(state, config)

    # Get the actual checkpoint
    checkpoint = await graph.aget_state(config)

    # Try to serialize - this is what the MemorySaver does internally
    # Should NOT raise TypeError about FAISSRetriever or CompiledStateGraph
    serde = JsonPlusSerializer()
    try:
        # Use dumps_typed method (correct API for LangGraph serializer)
        for key, value in checkpoint.values.items():
            type_str, serialized = serde.dumps_typed(value)
            assert type_str is not None
            assert serialized is not None
    except TypeError as e:
        error_msg = str(e)
        if "FAISSRetriever" in error_msg:
            pytest.fail(
                "Checkpoint contains FAISSRetriever - closure pattern failed! "
                f"Error: {error_msg}"
            )
        elif "CompiledStateGraph" in error_msg:
            pytest.fail(
                "Checkpoint contains CompiledStateGraph - closure pattern failed! "
                f"Error: {error_msg}"
            )
        else:
            # Some other serialization error
            raise


@pytest.mark.asyncio
async def test_multi_turn_with_checkpoint_reload(session_retriever, test_checkpointer):
    """Test conversation persists across turns by actually reloading checkpoint.

    This verifies that:
    1. First turn creates checkpoint successfully
    2. Second turn can reload checkpoint without serialization errors
    3. Agent assignment persists via checkpoint (not passed in state)
    4. Message history accumulates correctly
    """
    graph = build_medical_chatbot_graph(session_retriever, checkpointer=test_checkpointer)
    thread_id = "test-multi-turn-reload"
    config = {"configurable": {"thread_id": thread_id}}

    # First turn - initial classification
    state1 = MedicalChatState(
        messages=[{"role": "user", "content": "Tell me about TestDrug"}],
        session_id="session-multi"
    )
    result1 = await graph.ainvoke(state1, config)
    assigned = result1["assigned_agent"]
    assert assigned == "rag_agent"  # Should be assigned to RAG agent

    # Get checkpoint state after first turn
    checkpoint1 = await graph.aget_state(config)
    assert checkpoint1.values["assigned_agent"] == assigned
    msg_count_1 = len(checkpoint1.values["messages"])

    # Second turn - should reload from checkpoint
    # Deliberately don't pass assigned_agent to force checkpoint loading
    state2 = MedicalChatState(
        messages=[{"role": "user", "content": "What are the side effects?"}],
        session_id="session-multi"
        # Note: NOT passing assigned_agent - should load from checkpoint
    )
    result2 = await graph.ainvoke(state2, config)

    # Verify assignment was preserved via checkpoint, not state parameter
    assert result2["assigned_agent"] == assigned, (
        "Agent assignment should persist via checkpoint loading"
    )

    # Verify message history accumulated
    checkpoint2 = await graph.aget_state(config)
    msg_count_2 = len(checkpoint2.values["messages"])
    assert msg_count_2 > msg_count_1, (
        "Message history should accumulate across turns"
    )


@pytest.mark.asyncio
async def test_simulated_api_flow_with_checkpointing(session_retriever, test_checkpointer):
    """Simulate the actual API flow that triggered the serialization error.

    This test mimics what happens when the real API endpoint is called:
    1. Build graph with real FAISSRetriever
    2. Invoke with thread_id (triggers checkpointing)
    3. RAG agent receives retriever in temporary state
    4. Checkpoint should save successfully (no serialization error)
    5. Second call should load checkpoint successfully

    This is the test that would have caught the bug reported in the issue.
    """
    graph = build_medical_chatbot_graph(session_retriever, checkpointer=test_checkpointer)

    # Simulate first API call with medical query
    config1 = {"configurable": {"thread_id": "api-session-123"}}
    state1 = MedicalChatState(
        messages=[{"role": "user", "content": "What is MedicationX?"}],
        session_id="api-session-123"
    )

    # This should trigger RAG agent which receives retriever in temp state
    # The bug would cause: TypeError: Type is not msgpack serializable: FAISSRetriever
    result1 = await graph.ainvoke(state1, config1)
    assert result1["assigned_agent"] == "rag_agent"

    # Checkpoint should have been saved successfully (no serialization error)
    checkpoint = await graph.aget_state(config1)
    assert checkpoint is not None
    assert "retriever" not in checkpoint.values  # Should NOT be checkpointed

    # Simulate second API call with same thread (continuation)
    config2 = {"configurable": {"thread_id": "api-session-123"}}
    state2 = MedicalChatState(
        messages=[{"role": "user", "content": "Tell me more about dosage"}],
        session_id="api-session-123"
    )

    # Should load checkpoint and continue without error
    result2 = await graph.ainvoke(state2, config2)
    assert result2["assigned_agent"] == "rag_agent"

    # Verify checkpoint reloading worked
    checkpoint2 = await graph.aget_state(config2)
    assert len(checkpoint2.values["messages"]) > len(checkpoint.values["messages"])


@pytest.mark.asyncio
async def test_rag_agent_with_different_thread_ids(session_retriever, test_checkpointer):
    """Test that different thread_ids maintain separate checkpoint states.

    Verifies that:
    1. Each thread has independent checkpoint
    2. No cross-contamination between threads
    3. Serialization works for all threads
    """
    graph = build_medical_chatbot_graph(session_retriever, checkpointer=test_checkpointer)

    # Thread 1
    config1 = {"configurable": {"thread_id": "thread-001"}}
    state1 = MedicalChatState(
        messages=[{"role": "user", "content": "Query 1"}],
        session_id="session-1"
    )
    result1 = await graph.ainvoke(state1, config1)

    # Thread 2
    config2 = {"configurable": {"thread_id": "thread-002"}}
    state2 = MedicalChatState(
        messages=[{"role": "user", "content": "I'm feeling sad"}],
        session_id="session-2"
    )
    result2 = await graph.ainvoke(state2, config2)

    # Should have different agent assignments
    assert result1["assigned_agent"] == "rag_agent"
    assert result2["assigned_agent"] == "emotional_support"

    # Each checkpoint should be independent and serializable
    checkpoint1 = await graph.aget_state(config1)
    checkpoint2 = await graph.aget_state(config2)

    assert checkpoint1.values["assigned_agent"] != checkpoint2.values["assigned_agent"]
    assert checkpoint1.values["session_id"] != checkpoint2.values["session_id"]
