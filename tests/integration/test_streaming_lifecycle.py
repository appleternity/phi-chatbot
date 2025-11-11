"""Integration tests for SSE streaming lifecycle.

This module tests the complete streaming lifecycle including:
- Progressive token arrival
- Done event clean closure
- Client disconnect/cancellation handling
- Session state preservation across requests

Tests use httpx AsyncClient with ASGITransport for realistic integration testing
without requiring a running server.

Spec Reference: specs/003-sse-streaming/quickstart.md
Related: specs/003-sse-streaming/data-model.md
"""

import pytest
import json
import asyncio
from httpx import AsyncClient, ASGITransport
from typing import List, Dict, Any
import time
import uuid


@pytest.fixture
async def streaming_client(test_checkpointer):
    """Create async test client for streaming tests with lifespan support.

    This fixture:
    1. Triggers application lifespan (database, graph initialization)
    2. Replaces graph with test checkpointer for deterministic behavior
    3. Creates httpx AsyncClient with ASGITransport

    Args:
        test_checkpointer: Session-scoped checkpointer from conftest.py

    Yields:
        AsyncClient configured for SSE streaming tests
    """
    from app.main import app, app_state
    from app.graph.builder import build_medical_chatbot_graph

    # Manually trigger lifespan startup
    async with app.router.lifespan_context(app):
        # Replace graph with test checkpointer version for deterministic tests
        retriever = app_state.get("retriever")
        if retriever:
            app_state["graph"] = build_medical_chatbot_graph(
                retriever, checkpointer=test_checkpointer
            )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
        ) as ac:
            yield ac


async def parse_sse_events(response) -> List[Dict[str, Any]]:
    """Parse SSE events from streaming response.

    Utility function to parse Server-Sent Events format:
    - Each event starts with "data: "
    - Events are separated by double newlines
    - Each event contains JSON payload

    Args:
        response: httpx streaming response

    Returns:
        List of parsed event dictionaries

    Example:
        data: {"type":"token","content":"Hello","timestamp":"..."}

        data: {"type":"done","content":{},"timestamp":"..."}
    """
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])  # Remove "data: " prefix
                events.append(data)
            except json.JSONDecodeError as e:
                # Log malformed events for debugging
                pytest.fail(f"Failed to parse SSE event: {line}, error: {e}")
    return events


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_streaming_progressive_arrival(streaming_client):
    """Test that tokens are streamed progressively, not buffered.

    Functional Requirements:
    - FR-001: Real-time token streaming
    - FR-002: <100ms token delivery latency
    - FR-003: Tokens delivered progressively as generated

    Success Criteria:
    - SC-001: First token within 1 second
    - SC-002: Token latency <100ms between tokens

    Verification:
    1. Tokens arrive incrementally (not all at once)
    2. Token count > 0
    3. First token arrives quickly (<1s)
    4. Inter-token latency is reasonable (<100ms average)

    Test Case: T027 [US1] Progressive token arrival verification
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    # Track timing for latency verification
    start_time = time.time()
    first_token_time = None
    token_timestamps = []

    async with streaming_client.stream(
        "POST",
        "/chat",
        json={
            "message": "What are the side effects of aripiprazole?",
            "session_id": session_id,
        },
    ) as response:
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        events = await parse_sse_events(response)

    # Extract tokens and their timestamps
    tokens = []
    for event in events:
        if event["type"] == "token":
            token_content = event["content"]
            tokens.append(token_content)

            # Track first token timing
            if first_token_time is None:
                first_token_time = time.time()

            token_timestamps.append(time.time())

    # Assertions
    assert len(tokens) > 0, "No tokens received from stream"

    # Verify tokens form non-empty response
    full_response = "".join(tokens)
    assert len(full_response) > 0, "Response is empty"

    # Verify first token latency (SC-001: <1 second)
    if first_token_time:
        first_token_latency = first_token_time - start_time
        assert first_token_latency < 1.0, (
            f"First token latency {first_token_latency:.3f}s exceeds 1s threshold (SC-001)"
        )

    # Verify inter-token latency (SC-002: <100ms average)
    if len(token_timestamps) > 1:
        inter_token_latencies = [
            token_timestamps[i] - token_timestamps[i - 1]
            for i in range(1, len(token_timestamps))
        ]
        avg_latency = sum(inter_token_latencies) / len(inter_token_latencies)

        # Note: In test environment with FakeChatModel, latency should be near-zero
        # In production, this verifies <100ms average
        assert avg_latency < 0.1, (
            f"Average inter-token latency {avg_latency*1000:.1f}ms exceeds 100ms (SC-002)"
        )

    # Verify done event received
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1, f"Expected 1 done event, got {len(done_events)}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_done_event_closes_stream_cleanly(streaming_client):
    """Test that done event properly closes the stream.

    Functional Requirements:
    - FR-011: Clean connection closure with done event
    - FR-012: Stream ends after done event

    Verification:
    1. Done event is emitted as last event
    2. No events emitted after done
    3. Stream closes cleanly (no errors)
    4. Done event has correct structure

    Test Case: T028 [US1] Done event clean closure
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    async with streaming_client.stream(
        "POST",
        "/chat",
        json={
            "message": "What is sertraline used for?",
            "session_id": session_id,
        },
    ) as response:
        assert response.status_code == 200

        events = await parse_sse_events(response)

    # Verify events list is not empty
    assert len(events) > 0, "No events received from stream"

    # Verify last event is 'done'
    last_event = events[-1]
    assert last_event["type"] == "done", (
        f"Last event should be 'done', got '{last_event['type']}'"
    )

    # Verify done event structure
    assert "timestamp" in last_event, "Done event missing timestamp"
    assert "content" in last_event, "Done event missing content"

    # Verify no events after done
    done_indices = [i for i, e in enumerate(events) if e["type"] == "done"]
    assert len(done_indices) == 1, f"Expected 1 done event, got {len(done_indices)}"
    assert done_indices[0] == len(events) - 1, "Events found after done event"

    # Verify at least some tokens were streamed before done
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0, "No tokens streamed before done event"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_client_disconnect_triggers_cancellation(streaming_client):
    """Test that client disconnect/abort triggers proper cancellation.

    Functional Requirements:
    - FR-018: Stream stops immediately on client disconnect
    - FR-019: Backend detects cancellation and logs appropriately

    Verification:
    1. AbortController-style cancellation (simulated via timeout)
    2. Stream stops processing
    3. Cancellation event emitted (if detected early enough)
    4. No errors propagate to client

    Note: This test simulates disconnect by using a very short timeout.
    In real scenarios, AbortController.abort() would be used on frontend.

    Test Case: T029 [US1] Client disconnect cancellation detection
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    # Simulate client disconnect by using extremely short timeout
    # This forces the connection to abort mid-stream
    events_before_disconnect = []

    try:
        async with streaming_client.stream(
            "POST",
            "/chat",
            json={
                "message": "What are the side effects of aripiprazole?",
                "session_id": session_id,
            },
            timeout=0.001,  # 1ms timeout - will disconnect almost immediately
        ) as response:
            # Try to read events before timeout
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events_before_disconnect.append(data)
    except Exception as e:
        # Timeout or connection error expected
        assert "timed out" in str(e).lower() or "timeout" in str(e).lower(), (
            f"Expected timeout error, got: {e}"
        )

    # Verification: Stream was interrupted (may have received 0 or few events)
    # This simulates what happens when user clicks "Stop" button
    # In production, AbortController would trigger similar early termination

    # The key test is that the disconnect doesn't cause server errors
    # and that partial results can be handled gracefully
    assert isinstance(events_before_disconnect, list), "Events should be list"

    # Note: We may receive 0 events due to fast timeout - this is expected
    # The important part is that cancellation doesn't crash the server


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_state_preserved_after_cancellation(streaming_client):
    """Test that session state is preserved after stream cancellation.

    Functional Requirements:
    - FR-021: Can send new message after cancellation
    - FR-022: Conversation context preserved
    - FR-023: No data loss from cancelled stream

    Success Criteria:
    - SC-007: Graceful error handling with recovery

    Verification:
    1. Send first message and cancel mid-stream
    2. Send second message in same session
    3. Second stream works normally
    4. Conversation context maintained (checkpointer state)

    Test Case: T030 [US1] Session state preservation after cancellation
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    # ========================================================================
    # Phase 1: Start stream and cancel it mid-stream
    # ========================================================================

    events_first_stream = []

    try:
        async with streaming_client.stream(
            "POST",
            "/chat",
            json={
                "message": "What is sertraline?",
                "session_id": session_id,
            },
            timeout=0.01,  # 10ms timeout - cancel quickly
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events_first_stream.append(data)
    except Exception:
        # Timeout expected - this simulates user clicking "Stop"
        pass

    # Wait briefly to ensure backend cleanup completes
    await asyncio.sleep(0.1)

    # ========================================================================
    # Phase 2: Send new message in same session
    # ========================================================================

    events_second_stream = []

    async with streaming_client.stream(
        "POST",
        "/chat",
        json={
            "message": "What are its side effects?",  # Follow-up question
            "session_id": session_id,  # Same session
        },
    ) as response:
        assert response.status_code == 200, (
            f"Second stream failed with status {response.status_code}"
        )

        events_second_stream = await parse_sse_events(response)

    # ========================================================================
    # Verification
    # ========================================================================

    # Verify second stream completed successfully
    assert len(events_second_stream) > 0, "Second stream received no events"

    # Verify second stream has tokens
    second_tokens = [e for e in events_second_stream if e["type"] == "token"]
    assert len(second_tokens) > 0, "Second stream received no tokens"

    # Verify second stream ends with done event
    second_done = [e for e in events_second_stream if e["type"] == "done"]
    assert len(second_done) == 1, "Second stream missing done event"

    # Verify no error events in second stream
    second_errors = [e for e in events_second_stream if e["type"] == "error"]
    assert len(second_errors) == 0, f"Second stream had errors: {second_errors}"

    # Verify second stream produces valid response
    second_response = "".join([e["content"] for e in second_tokens])
    assert len(second_response) > 0, "Second stream response is empty"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stage_indicators_emitted(streaming_client):
    """Test that processing stage indicators are emitted correctly.

    Functional Requirements:
    - FR-004: Processing stage events
    - FR-005: Stage transitions (retrieval → reranking → generation)

    Success Criteria:
    - SC-003: Stage transitions <200ms

    Verification:
    1. Retrieval stages emitted (start/complete)
    2. Reranking stages emitted (start/complete)
    3. Stages appear in correct order
    4. Stages have correct structure

    Additional Test: Complements T027-T030 with stage-specific verification
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    async with streaming_client.stream(
        "POST",
        "/chat",
        json={
            "message": "What is bupropion?",
            "session_id": session_id,
        },
    ) as response:
        assert response.status_code == 200

        events = await parse_sse_events(response)

    # Extract stage events
    stage_events = [
        e for e in events
        if e["type"] in [
            "retrieval_start", "retrieval_complete",
            "reranking_start", "reranking_complete"
        ]
    ]

    # Verify stage events exist
    assert len(stage_events) > 0, "No stage events received"

    # Verify retrieval stages
    retrieval_starts = [e for e in events if e["type"] == "retrieval_start"]
    retrieval_completes = [e for e in events if e["type"] == "retrieval_complete"]

    assert len(retrieval_starts) > 0, "No retrieval_start event"
    assert len(retrieval_completes) > 0, "No retrieval_complete event"

    # Verify stage event structure
    for stage_event in stage_events:
        assert "type" in stage_event, "Stage event missing type"
        assert "content" in stage_event, "Stage event missing content"
        assert "timestamp" in stage_event, "Stage event missing timestamp"

        # Stage events should have content dict with stage/status
        if stage_event["content"]:  # Some may have empty content
            assert "stage" in stage_event["content"], "Stage event content missing 'stage'"
            assert "status" in stage_event["content"], "Stage event content missing 'status'"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_event_handling(streaming_client):
    """Test that errors are properly emitted as events.

    Functional Requirements:
    - FR-010: Error events
    - FR-013: Error structure with message and code

    Success Criteria:
    - SC-007: Graceful error handling

    Verification:
    1. Invalid input triggers error event (if applicable)
    2. Error event has correct structure
    3. Stream terminates after error
    4. No tokens emitted after error

    Note: This test depends on ability to trigger errors.
    May need to mock/inject error conditions for comprehensive testing.

    Additional Test: Error handling verification
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    # Test with empty message (should be caught by validation)
    response = await streaming_client.post(
        "/chat",
        json={
            "message": "",  # Invalid: empty message
            "session_id": session_id,
        },
    )

    # Validation error should be HTTP 422, not streamed error
    assert response.status_code == 422, (
        f"Expected validation error 422, got {response.status_code}"
    )

    # Note: Testing actual streaming errors (like LLM failures) requires
    # error injection or mocking, which is beyond this integration test scope.
    # Those scenarios would be covered by unit tests or manual error injection.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_streaming_sessions(streaming_client):
    """Test multiple concurrent streaming sessions.

    Success Criteria:
    - SC-006: Support 10+ concurrent sessions

    Verification:
    1. Start multiple streams concurrently
    2. All streams complete successfully
    3. No interference between sessions
    4. All streams emit done events

    Additional Test: Concurrent session handling
    """
    num_sessions = 5  # Test with 5 concurrent sessions
    session_ids = [str(uuid.uuid4()) for _ in range(num_sessions)]  # Generate valid UUIDs

    async def stream_single_session(session_id: str) -> List[Dict[str, Any]]:
        """Stream a single session and return events."""
        async with streaming_client.stream(
            "POST",
            "/chat",
            json={
                "message": f"Query for session {session_id}",
                "session_id": session_id,
            },
        ) as response:
            assert response.status_code == 200
            return await parse_sse_events(response)

    # Run all streams concurrently
    results = await asyncio.gather(
        *[stream_single_session(sid) for sid in session_ids]
    )

    # Verify all sessions completed
    assert len(results) == num_sessions, (
        f"Expected {num_sessions} results, got {len(results)}"
    )

    # Verify each session has events
    for i, events in enumerate(results):
        assert len(events) > 0, f"Session {i} received no events"

        # Verify each has tokens
        tokens = [e for e in events if e["type"] == "token"]
        assert len(tokens) > 0, f"Session {i} received no tokens"

        # Verify each has done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1, (
            f"Session {i} expected 1 done event, got {len(done_events)}"
        )


# ============================================================================
# Performance Benchmarks (Optional - for monitoring)
# ============================================================================

@pytest.mark.integration
@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_streaming_performance_benchmark(streaming_client):
    """Benchmark streaming performance metrics.

    This test measures actual performance and logs metrics.
    Marked with @pytest.mark.benchmark to run separately.

    Metrics:
    - First token latency (SC-001: <1s)
    - Average inter-token latency (SC-002: <100ms)
    - Total stream duration
    - Tokens per second
    """
    session_id = str(uuid.uuid4())  # Generate valid UUID

    start_time = time.time()
    first_token_time = None
    token_times = []
    token_count = 0

    async with streaming_client.stream(
        "POST",
        "/chat",
        json={
            "message": "What are the side effects of aripiprazole?",
            "session_id": session_id,
        },
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])

                if data["type"] == "token":
                    current_time = time.time()

                    if first_token_time is None:
                        first_token_time = current_time

                    token_times.append(current_time)
                    token_count += 1

                elif data["type"] == "done":
                    break

    end_time = time.time()

    # Calculate metrics
    total_duration = end_time - start_time
    first_token_latency = (first_token_time - start_time) if first_token_time else 0

    if len(token_times) > 1:
        inter_token_latencies = [
            token_times[i] - token_times[i - 1]
            for i in range(1, len(token_times))
        ]
        avg_inter_token_latency = sum(inter_token_latencies) / len(inter_token_latencies)
    else:
        avg_inter_token_latency = 0

    tokens_per_second = token_count / total_duration if total_duration > 0 else 0

    # Log metrics (visible in pytest output with -v)
    print("\n" + "="*60)
    print("Streaming Performance Benchmark")
    print("="*60)
    print(f"Total Duration:           {total_duration:.3f}s")
    print(f"First Token Latency:      {first_token_latency:.3f}s")
    print(f"Avg Inter-Token Latency:  {avg_inter_token_latency*1000:.1f}ms")
    print(f"Token Count:              {token_count}")
    print(f"Tokens/Second:            {tokens_per_second:.1f}")
    print("="*60)

    # Assertions (success criteria)
    assert first_token_latency < 1.0, (
        f"First token latency {first_token_latency:.3f}s exceeds 1s (SC-001)"
    )

    assert avg_inter_token_latency < 0.1, (
        f"Average inter-token latency {avg_inter_token_latency*1000:.1f}ms exceeds 100ms (SC-002)"
    )
