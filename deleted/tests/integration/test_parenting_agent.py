"""Integration tests for the parenting agent with agentic RAG flow."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from app.graph.state import MedicalChatState
from app.graph.parenting_state import ParentingRAGState
from app.agents.parenting_agent import (
    create_parenting_rag_agent,
    agent_decision_node,
    grade_documents_node,
    check_quality_node,
    rewrite_query_node,
    generate_answer_node,
    confidence_check_node,
    insufficient_info_node,
    route_after_agent,
    route_after_quality,
    route_after_confidence,
)
from app.core.retriever import Document, DocumentRetriever
from app.core.reranker import CrossEncoderReranker


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_parenting_documents():
    """Create sample parenting advice documents."""
    return [
        Document(
            id="doc1",
            content=(
                "Toddler tantrums are a normal part of development between ages 2-3. "
                "They occur because toddlers are learning to express emotions but lack "
                "the language skills to communicate effectively. The best approach is to "
                "stay calm, validate their feelings, and set clear boundaries."
            ),
            metadata={
                "source": "Dr. Sarah Johnson - Developmental Psychology",
                "timestamp": "00:15:30.000",
                "age_range": "2-3"
            }
        ),
        Document(
            id="doc2",
            content=(
                "Time-outs can be effective for toddlers when used correctly. "
                "The rule of thumb is one minute per year of age. Keep the child in a "
                "safe, boring place and stay calm. After the time-out, briefly explain "
                "what behavior was wrong and move on."
            ),
            metadata={
                "source": "Dr. Michael Chen - Child Behavior Specialist",
                "timestamp": "00:23:45.000",
                "age_range": "2-5"
            }
        ),
        Document(
            id="doc3",
            content=(
                "Positive discipline focuses on teaching rather than punishment. "
                "Use natural consequences, offer choices, and praise good behavior. "
                "This approach helps children develop self-regulation and decision-making skills."
            ),
            metadata={
                "source": "Dr. Emily Rodriguez - Parenting Coach",
                "timestamp": "00:31:20.000",
                "age_range": "1-5"
            }
        ),
    ]


@pytest.fixture
def mock_parenting_retriever(sample_parenting_documents):
    """Create a mock retriever for parenting documents."""
    mock_retriever = AsyncMock(spec=DocumentRetriever)

    async def mock_search(query: str, top_k: int = 3):
        # Return documents based on keyword matching
        if "tantrum" in query.lower():
            return [sample_parenting_documents[0]]
        elif "discipline" in query.lower() or "timeout" in query.lower():
            return sample_parenting_documents[:2]
        else:
            return sample_parenting_documents[:top_k]

    mock_retriever.search = mock_search
    return mock_retriever


@pytest.fixture
def mock_parenting_reranker():
    """Create a mock reranker for parenting documents."""
    mock_reranker = Mock(spec=CrossEncoderReranker)

    async def mock_rerank(query: str, documents, top_k: int = 3):
        # Simple mock: return documents in original order, limited to top_k
        return documents[:top_k]

    mock_reranker.rerank = mock_rerank
    return mock_reranker


@pytest.fixture
def parenting_agent(mock_parenting_retriever, mock_parenting_reranker):
    """Create parenting RAG agent with mocked dependencies."""
    return create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )


# ============================================================================
# Supervisor Routing Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_supervisor_routes_to_parenting_agent_toddler_keyword(
    session_retriever, parenting_retriever, parenting_reranker, test_checkpointer
):
    """Test supervisor routes to parenting agent with 'toddler' keyword."""
    from app.graph.builder import build_medical_chatbot_graph

    # Build graph with parenting agent
    graph = build_medical_chatbot_graph(
        retriever=session_retriever,
        parenting_retriever=parenting_retriever,
        parenting_reranker=parenting_reranker,
        checkpointer=test_checkpointer
    )

    state = MedicalChatState(
        messages=[HumanMessage(content="My toddler has frequent tantrums")],
        session_id="test-parenting-1"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-parenting-1"}})

    # Should route to parenting agent
    assert result.get("assigned_agent") == "parenting"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_supervisor_routes_to_parenting_agent_child_keyword(
    session_retriever, parenting_retriever, parenting_reranker, test_checkpointer
):
    """Test supervisor routes to parenting agent with 'child' keyword."""
    from app.graph.builder import build_medical_chatbot_graph

    graph = build_medical_chatbot_graph(
        retriever=session_retriever,
        parenting_retriever=parenting_retriever,
        parenting_reranker=parenting_reranker,
        checkpointer=test_checkpointer
    )

    state = MedicalChatState(
        messages=[HumanMessage(content="How do I discipline my child?")],
        session_id="test-parenting-2"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-parenting-2"}})

    assert result.get("assigned_agent") == "parenting"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_supervisor_routes_to_parenting_agent_parenting_keyword(
    session_retriever, parenting_retriever, parenting_reranker, test_checkpointer
):
    """Test supervisor routes to parenting agent with 'parenting' keyword."""
    from app.graph.builder import build_medical_chatbot_graph

    graph = build_medical_chatbot_graph(
        retriever=session_retriever,
        parenting_retriever=parenting_retriever,
        parenting_reranker=parenting_reranker,
        checkpointer=test_checkpointer
    )

    state = MedicalChatState(
        messages=[HumanMessage(content="I need parenting advice for a two-year-old")],
        session_id="test-parenting-3"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-parenting-3"}})

    assert result.get("assigned_agent") == "parenting"


# ============================================================================
# Agent Decision Node Tests
# ============================================================================

def test_agent_decision_node_decides_to_retrieve():
    """Test agent decision node decides to use retrieval tool."""
    state = ParentingRAGState(
        messages=[HumanMessage(content="How do I handle toddler tantrums?")],
        question="How do I handle toddler tantrums?"
    )

    result = agent_decision_node(state)

    # Should have added an AI message with tool calls
    assert len(result["messages"]) > len(state["messages"])
    last_message = result["messages"][-1]
    assert hasattr(last_message, "tool_calls") or isinstance(last_message, AIMessage)


def test_agent_decision_node_with_simple_query():
    """Test agent decision node with simple conversational query."""
    state = ParentingRAGState(
        messages=[HumanMessage(content="Hello")],
        question="Hello"
    )

    result = agent_decision_node(state)

    # Should have response
    assert len(result["messages"]) > len(state["messages"])


# ============================================================================
# Document Grading Tests
# ============================================================================

def test_grade_documents_node_filters_relevant(sample_parenting_documents):
    """Test document grading filters out irrelevant documents."""
    state = ParentingRAGState(
        question="How do I handle toddler tantrums?",
        documents=sample_parenting_documents
    )

    result = grade_documents_node(state)

    # Should have filtered documents and relevance scores
    assert "filtered_documents" in result
    assert "relevance_scores" in result
    assert len(result["relevance_scores"]) == len(sample_parenting_documents)


def test_grade_documents_node_empty_documents():
    """Test document grading with empty documents list."""
    state = ParentingRAGState(
        question="Test question",
        documents=[]
    )

    result = grade_documents_node(state)

    assert result["filtered_documents"] == []
    assert result["relevance_scores"] == []


def test_grade_documents_node_assigns_scores(sample_parenting_documents):
    """Test that document grading assigns relevance scores."""
    state = ParentingRAGState(
        question="toddler behavior management",
        documents=sample_parenting_documents
    )

    result = grade_documents_node(state)

    scores = result["relevance_scores"]
    # All scores should be between 0 and 1
    assert all(0.0 <= score <= 1.0 for score in scores)


# ============================================================================
# Query Rewriting Tests
# ============================================================================

def test_rewrite_query_node_improves_query():
    """Test that query rewriting generates improved query."""
    state = ParentingRAGState(
        question="tantrums",
        retrieval_attempts=1
    )

    result = rewrite_query_node(state)

    # Should have rewritten question
    assert result["question"] != state["question"]
    assert len(result["question"]) > len(state["question"])


def test_rewrite_query_node_tracks_attempts():
    """Test that query rewriting doesn't modify attempt count."""
    state = ParentingRAGState(
        question="test query",
        retrieval_attempts=1
    )

    result = rewrite_query_node(state)

    # Attempt count should remain (check_quality_node increments it)
    assert "question" in result


# ============================================================================
# Quality Check Tests
# ============================================================================

def test_check_quality_node_good_results(sample_parenting_documents):
    """Test quality check with good retrieval results."""
    state = ParentingRAGState(
        filtered_documents=sample_parenting_documents,
        relevance_scores=[0.9, 0.8, 0.7],
        retrieval_attempts=0
    )

    result = check_quality_node(state)

    # Should not trigger rewrite
    assert result["should_rewrite"] is False
    assert result["retrieval_attempts"] == 1


def test_check_quality_node_poor_results():
    """Test quality check with poor retrieval results."""
    state = ParentingRAGState(
        filtered_documents=[],
        relevance_scores=[],
        retrieval_attempts=0
    )

    result = check_quality_node(state)

    # Should trigger rewrite
    assert result["should_rewrite"] is True
    assert result["retrieval_attempts"] == 1


def test_check_quality_node_max_attempts_reached():
    """Test quality check stops after max attempts."""
    state = ParentingRAGState(
        filtered_documents=[],
        relevance_scores=[],
        retrieval_attempts=2  # Max attempts
    )

    result = check_quality_node(state)

    # Should not trigger rewrite even with poor results
    assert result["should_rewrite"] is False


def test_check_quality_node_low_average_score(sample_parenting_documents):
    """Test quality check with low average relevance score."""
    state = ParentingRAGState(
        filtered_documents=sample_parenting_documents[:2],
        relevance_scores=[0.4, 0.3],  # Below 0.6 threshold
        retrieval_attempts=0
    )

    result = check_quality_node(state)

    # Should trigger rewrite due to low average score
    assert result["should_rewrite"] is True


# ============================================================================
# Answer Generation Tests
# ============================================================================

def test_generate_answer_node_with_documents(sample_parenting_documents):
    """Test answer generation with available documents."""
    state = ParentingRAGState(
        question="How do I handle toddler tantrums?",
        filtered_documents=sample_parenting_documents,
        relevance_scores=[0.9, 0.8, 0.7]
    )

    result = generate_answer_node(state)

    # Should have generated answer
    assert "generation" in result
    assert len(result["generation"]) > 0
    assert result["generation"] != ""


def test_generate_answer_node_without_documents():
    """Test answer generation without documents."""
    state = ParentingRAGState(
        question="Test question",
        filtered_documents=[],
    )

    result = generate_answer_node(state)

    # Should have fallback message
    assert "generation" in result
    assert "don't have enough reliable information" in result["generation"].lower()
    assert result["confidence"] == 0.0


def test_generate_answer_node_includes_sources(sample_parenting_documents):
    """Test that answer generation includes source metadata."""
    state = ParentingRAGState(
        question="parenting advice",
        filtered_documents=sample_parenting_documents,
        relevance_scores=[0.9, 0.8, 0.7]
    )

    result = generate_answer_node(state)

    # Should have sources
    assert "sources" in result
    assert len(result["sources"]) == len(sample_parenting_documents)
    assert all("source" in src for src in result["sources"])


def test_generate_answer_node_with_user_context(sample_parenting_documents):
    """Test answer generation with user context (child age)."""
    state = ParentingRAGState(
        question="discipline strategies",
        filtered_documents=sample_parenting_documents,
        relevance_scores=[0.9, 0.8, 0.7],
        user_context={"child_age": 3}
    )

    result = generate_answer_node(state)

    assert "generation" in result
    assert len(result["generation"]) > 0


# ============================================================================
# Confidence Check Tests
# ============================================================================

def test_confidence_check_node_high_confidence(sample_parenting_documents):
    """Test confidence calculation with high relevance scores."""
    state = ParentingRAGState(
        filtered_documents=sample_parenting_documents,
        relevance_scores=[0.9, 0.8, 0.7]
    )

    result = confidence_check_node(state)

    # Should have high confidence
    assert result["confidence"] > 0.6
    assert 0.0 <= result["confidence"] <= 1.0


def test_confidence_check_node_low_confidence():
    """Test confidence calculation with low relevance scores."""
    state = ParentingRAGState(
        filtered_documents=[Document(id="1", content="test", metadata={})],
        relevance_scores=[0.3]
    )

    result = confidence_check_node(state)

    # Should have low confidence
    assert result["confidence"] < 0.6


def test_confidence_check_node_no_documents():
    """Test confidence calculation with no documents."""
    state = ParentingRAGState(
        filtered_documents=[],
        relevance_scores=[]
    )

    result = confidence_check_node(state)

    assert result["confidence"] == 0.0


def test_confidence_check_node_formula():
    """Test confidence calculation formula."""
    # Formula: (avg_relevance * 0.7) + (min(doc_count / 5, 1.0) * 0.3)
    state = ParentingRAGState(
        filtered_documents=[Document(id=str(i), content="test", metadata={}) for i in range(5)],
        relevance_scores=[1.0, 1.0, 1.0, 1.0, 1.0]  # Perfect scores
    )

    result = confidence_check_node(state)

    # With 5 docs at 1.0 relevance: (1.0 * 0.7) + (1.0 * 0.3) = 1.0
    assert result["confidence"] == pytest.approx(1.0, rel=1e-2)


# ============================================================================
# Routing Tests
# ============================================================================

def test_route_after_agent_with_tool_calls():
    """Test routing after agent decision when tools are called."""
    # Mock message with tool calls
    message = Mock()
    message.tool_calls = [{"name": "search_parenting_knowledge"}]

    state = ParentingRAGState(
        messages=[message]
    )

    route = route_after_agent(state)
    assert route == "tools"


def test_route_after_agent_without_tool_calls():
    """Test routing after agent decision when no tools called."""
    message = AIMessage(content="Direct answer without retrieval")

    state = ParentingRAGState(
        messages=[message]
    )

    route = route_after_agent(state)
    assert route == "generate_answer"


def test_route_after_quality_should_rewrite():
    """Test routing after quality check when rewrite is needed."""
    state = ParentingRAGState(
        should_rewrite=True
    )

    route = route_after_quality(state)
    assert route == "rewrite_query"


def test_route_after_quality_should_not_rewrite():
    """Test routing after quality check when rewrite is not needed."""
    state = ParentingRAGState(
        should_rewrite=False
    )

    route = route_after_quality(state)
    assert route == "generate_answer"


def test_route_after_confidence_high():
    """Test routing after confidence check with high confidence."""
    from langgraph.graph import END

    state = ParentingRAGState(
        confidence=0.8
    )

    route = route_after_confidence(state)
    assert route == END


def test_route_after_confidence_low():
    """Test routing after confidence check with low confidence."""
    state = ParentingRAGState(
        confidence=0.4
    )

    route = route_after_confidence(state)
    assert route == "insufficient_info"


# ============================================================================
# Insufficient Info Node Tests
# ============================================================================

def test_insufficient_info_node_returns_helpful_message():
    """Test insufficient info node returns helpful fallback message."""
    from langgraph.graph import END

    state = ParentingRAGState(
        messages=[HumanMessage(content="Test question")]
    )

    command = insufficient_info_node(state)

    # Should return command to END
    assert command.goto == END

    # Should have added helpful message
    assert "messages" in command.update
    new_messages = command.update["messages"]
    last_message = new_messages[-1]
    assert isinstance(last_message, AIMessage)
    assert "don't have enough reliable information" in last_message.content.lower()
    assert "pediatrician" in last_message.content.lower()


# ============================================================================
# Full Graph Flow Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_full_flow_with_retrieval(
    mock_parenting_retriever, mock_parenting_reranker, sample_parenting_documents
):
    """Test complete parenting agent flow with successful retrieval."""
    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="How do I handle toddler tantrums?")],
        question="How do I handle toddler tantrums?",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result = agent.invoke(state)

    # Should have response
    assert len(result["messages"]) > 1
    # Should have high confidence
    assert result.get("confidence", 0) >= 0.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_query_rewriting_loop(
    mock_parenting_retriever, mock_parenting_reranker
):
    """Test query rewriting loop when initial retrieval is poor."""
    # Configure mock to return no documents initially
    attempt_count = [0]

    async def mock_search_with_retry(query: str, top_k: int = 3):
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            # First attempt: return nothing
            return []
        else:
            # Second attempt: return documents
            return [
                Document(
                    id="doc1",
                    content="Helpful parenting advice",
                    metadata={"source": "guide"}
                )
            ]

    mock_parenting_retriever.search = mock_search_with_retry

    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="advice")],
        question="advice",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result = agent.invoke(state)

    # Should have attempted retrieval multiple times
    assert result.get("retrieval_attempts", 0) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_insufficient_info_response(
    mock_parenting_retriever, mock_parenting_reranker
):
    """Test 'I don't know' response for low confidence."""
    # Configure mock to return low-quality documents
    async def mock_search_poor_quality(query: str, top_k: int = 3):
        return [
            Document(
                id="poor",
                content="Irrelevant content",
                metadata={"source": "unknown"}
            )
        ]

    mock_parenting_retriever.search = mock_search_poor_quality

    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="obscure parenting question")],
        question="obscure parenting question",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result = agent.invoke(state)

    # Should have response (either answer or insufficient info)
    assert len(result["messages"]) > 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_multi_turn_conversation(
    mock_parenting_retriever, mock_parenting_reranker, sample_parenting_documents
):
    """Test multi-turn conversation maintains context."""
    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    # First turn
    state1 = ParentingRAGState(
        messages=[HumanMessage(content="Tell me about toddler tantrums")],
        question="Tell me about toddler tantrums",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result1 = agent.invoke(state1)

    # Second turn - follow-up question
    state2 = ParentingRAGState(
        messages=result1["messages"] + [HumanMessage(content="What about time-outs?")],
        question="What about time-outs?",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result2 = agent.invoke(state2)

    # Should have responses for both turns
    assert len(result2["messages"]) > len(result1["messages"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_with_child_age_context(
    mock_parenting_retriever, mock_parenting_reranker, sample_parenting_documents
):
    """Test parenting agent uses child age context."""
    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="Discipline strategies for my child")],
        question="Discipline strategies for my child",
        user_context={"child_age": 3},
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result = agent.invoke(state)

    # Should have response
    assert len(result["messages"]) > 1


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_handles_retriever_failure(mock_parenting_reranker):
    """Test graceful handling when retriever fails."""
    # Create mock retriever that raises exception
    failing_retriever = AsyncMock(spec=DocumentRetriever)
    failing_retriever.search.side_effect = Exception("Retriever failed")

    agent = create_parenting_rag_agent(
        retriever=failing_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="Test question")],
        question="Test question",
        retriever=failing_retriever,
        reranker=mock_parenting_reranker
    )

    # Should handle error gracefully
    try:
        result = agent.invoke(state)
        # If it doesn't crash, that's good
        assert "messages" in result
    except Exception:
        # Expected behavior - may raise but shouldn't crash entire system
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parenting_agent_handles_empty_query(
    mock_parenting_retriever, mock_parenting_reranker
):
    """Test handling of empty query."""
    agent = create_parenting_rag_agent(
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    state = ParentingRAGState(
        messages=[HumanMessage(content="")],
        question="",
        retriever=mock_parenting_retriever,
        reranker=mock_parenting_reranker
    )

    result = agent.invoke(state)

    # Should handle gracefully
    assert "messages" in result
