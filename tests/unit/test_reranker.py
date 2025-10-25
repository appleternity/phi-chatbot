"""Unit tests for CrossEncoderReranker."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from typing import List

from app.core.reranker import CrossEncoderReranker
from app.core.retriever import Document


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_documents():
    """Create sample documents for reranking tests."""
    return [
        Document(
            id="doc1",
            content="Toddler tantrums are normal at age 2-3 and part of emotional development",
            metadata={"source": "parenting_guide", "relevance": "high"}
        ),
        Document(
            id="doc2",
            content="Sleep training can help infants develop healthy sleep patterns",
            metadata={"source": "sleep_guide", "relevance": "medium"}
        ),
        Document(
            id="doc3",
            content="Positive discipline focuses on teaching rather than punishment",
            metadata={"source": "discipline_guide", "relevance": "high"}
        ),
        Document(
            id="doc4",
            content="Child development milestones vary by individual but follow general patterns",
            metadata={"source": "development_guide", "relevance": "low"}
        ),
        Document(
            id="doc5",
            content="Emotional regulation skills develop gradually during early childhood",
            metadata={"source": "emotional_guide", "relevance": "medium"}
        ),
    ]


@pytest.fixture
def mock_cross_encoder():
    """Create a mock CrossEncoder model."""
    with patch('app.core.reranker.CrossEncoder') as mock_ce:
        # Mock the model instance
        mock_model = Mock()

        # Mock predict to return scores based on content similarity
        def mock_predict(pairs, show_progress_bar=False):
            # Return descending scores for deterministic testing
            scores = np.array([0.9, 0.7, 0.5, 0.3, 0.1][:len(pairs)])
            return scores

        mock_model.predict = mock_predict
        mock_ce.return_value = mock_model

        yield mock_ce


@pytest.fixture
def reranker(mock_cross_encoder):
    """Create CrossEncoderReranker instance with mocked model."""
    reranker = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length=512
    )
    return reranker


# ============================================================================
# Initialization Tests
# ============================================================================

def test_reranker_initialization_default_params(mock_cross_encoder):
    """Test CrossEncoderReranker initializes with default parameters."""
    reranker = CrossEncoderReranker()

    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert reranker.max_length == 512


def test_reranker_initialization_custom_params(mock_cross_encoder):
    """Test CrossEncoderReranker initializes with custom parameters."""
    reranker = CrossEncoderReranker(
        model_name="custom-model",
        max_length=256
    )

    assert reranker.model_name == "custom-model"
    assert reranker.max_length == 256


def test_reranker_device_detection_mps(mock_cross_encoder):
    """Test device detection prefers MPS when available."""
    with patch('torch.backends.mps.is_available', return_value=True):
        reranker = CrossEncoderReranker()
        assert reranker.device == "mps"


def test_reranker_device_detection_cpu_fallback(mock_cross_encoder):
    """Test device detection falls back to CPU when MPS unavailable."""
    with patch('torch.backends.mps.is_available', return_value=False):
        reranker = CrossEncoderReranker()
        assert reranker.device == "cpu"


def test_reranker_initialization_model_loading_failure():
    """Test that model loading failure raises RuntimeError."""
    with patch('app.core.reranker.CrossEncoder', side_effect=Exception("Model not found")):
        with pytest.raises(RuntimeError, match="Failed to initialize CrossEncoderReranker"):
            CrossEncoderReranker()


# ============================================================================
# Reranking Tests
# ============================================================================

def test_rerank_returns_documents(reranker, sample_documents):
    """Test that rerank returns documents in order."""
    query = "toddler emotional development"
    results = reranker.rerank(query, sample_documents, top_k=3)

    assert len(results) == 3
    assert all(isinstance(doc, Document) for doc in results)


def test_rerank_respects_top_k(reranker, sample_documents):
    """Test that rerank returns exactly top_k documents."""
    query = "parenting advice"

    # Test different top_k values
    for top_k in [1, 2, 3, 5]:
        results = reranker.rerank(query, sample_documents, top_k=top_k)
        expected_count = min(top_k, len(sample_documents))
        assert len(results) == expected_count


def test_rerank_orders_by_relevance(reranker, sample_documents):
    """Test that rerank orders documents by relevance score."""
    query = "toddler tantrums"
    results = reranker.rerank(query, sample_documents, top_k=5)

    # With mocked scores [0.9, 0.7, 0.5, 0.3, 0.1], documents should be in that order
    assert results[0].id == "doc1"  # Highest score
    assert results[1].id == "doc2"
    assert results[2].id == "doc3"
    assert results[3].id == "doc4"
    assert results[4].id == "doc5"  # Lowest score


def test_rerank_with_query_document_pairs(reranker, sample_documents):
    """Test that rerank creates proper query-document pairs."""
    query = "child development"

    # Mock to capture the pairs passed to predict
    captured_pairs = []

    def capture_predict(pairs, show_progress_bar=False):
        captured_pairs.extend(pairs)
        return np.array([0.5] * len(pairs))

    reranker._model.predict = capture_predict

    reranker.rerank(query, sample_documents, top_k=3)

    # Verify pairs were created correctly
    assert len(captured_pairs) == len(sample_documents)
    assert all(pair[0] == query for pair in captured_pairs)
    assert all(pair[1] == doc.content for pair, doc in zip(captured_pairs, sample_documents))


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_rerank_empty_documents_list(reranker):
    """Test rerank with empty documents list."""
    query = "test query"
    results = reranker.rerank(query, [], top_k=3)

    assert results == []


def test_rerank_single_document(reranker, sample_documents):
    """Test rerank with single document."""
    query = "test query"
    single_doc = [sample_documents[0]]

    results = reranker.rerank(query, single_doc, top_k=3)

    assert len(results) == 1
    assert results[0].id == "doc1"


def test_rerank_top_k_zero(reranker, sample_documents):
    """Test that top_k=0 raises ValueError."""
    query = "test query"

    with pytest.raises(ValueError, match="top_k must be positive"):
        reranker.rerank(query, sample_documents, top_k=0)


def test_rerank_top_k_negative(reranker, sample_documents):
    """Test that negative top_k raises ValueError."""
    query = "test query"

    with pytest.raises(ValueError, match="top_k must be positive"):
        reranker.rerank(query, sample_documents, top_k=-1)


def test_rerank_top_k_exceeds_documents(reranker, sample_documents):
    """Test rerank when top_k exceeds number of documents."""
    query = "test query"

    results = reranker.rerank(query, sample_documents, top_k=100)

    # Should return all available documents
    assert len(results) == len(sample_documents)


def test_rerank_empty_query(reranker, sample_documents):
    """Test rerank with empty query string."""
    results = reranker.rerank("", sample_documents, top_k=3)

    # Should still return results (model handles empty queries)
    assert len(results) <= 3


# ============================================================================
# Score Handling Tests
# ============================================================================

def test_rerank_score_ordering(reranker, sample_documents):
    """Test that documents are ordered by descending score."""
    # Mock predict to return specific scores
    def mock_predict_specific(pairs, show_progress_bar=False):
        return np.array([0.1, 0.9, 0.3, 0.7, 0.5])

    reranker._model.predict = mock_predict_specific

    query = "test query"
    results = reranker.rerank(query, sample_documents, top_k=5)

    # Should be ordered: doc2 (0.9), doc4 (0.7), doc5 (0.5), doc3 (0.3), doc1 (0.1)
    assert results[0].id == "doc2"
    assert results[1].id == "doc4"
    assert results[2].id == "doc5"
    assert results[3].id == "doc3"
    assert results[4].id == "doc1"


def test_rerank_identical_scores(reranker, sample_documents):
    """Test rerank behavior when all scores are identical."""
    # Mock predict to return identical scores
    def mock_predict_identical(pairs, show_progress_bar=False):
        return np.array([0.5] * len(pairs))

    reranker._model.predict = mock_predict_identical

    query = "test query"
    results = reranker.rerank(query, sample_documents, top_k=3)

    # Should return top_k documents (order may be arbitrary)
    assert len(results) == 3


def test_rerank_negative_scores(reranker, sample_documents):
    """Test rerank handles negative scores correctly."""
    # Mock predict to return negative scores
    def mock_predict_negative(pairs, show_progress_bar=False):
        return np.array([-0.1, -0.9, -0.3, -0.7, -0.5])

    reranker._model.predict = mock_predict_negative

    query = "test query"
    results = reranker.rerank(query, sample_documents, top_k=3)

    # Should still order correctly (highest = least negative)
    assert len(results) == 3
    assert results[0].id == "doc1"  # -0.1 is highest


# ============================================================================
# Error Handling and Graceful Degradation Tests
# ============================================================================

def test_rerank_model_prediction_failure(reranker, sample_documents):
    """Test graceful degradation when model prediction fails."""
    # Mock predict to raise exception
    def mock_predict_failure(pairs, show_progress_bar=False):
        raise RuntimeError("Model prediction failed")

    reranker._model.predict = mock_predict_failure

    query = "test query"
    results = reranker.rerank(query, sample_documents, top_k=3)

    # Should return original documents in original order (graceful degradation)
    assert len(results) == 3
    assert results == sample_documents[:3]


def test_rerank_handles_long_content(reranker):
    """Test rerank handles documents with content exceeding max_length."""
    long_content = "word " * 1000  # Create very long content
    long_docs = [
        Document(
            id="long1",
            content=long_content,
            metadata={}
        )
    ]

    query = "test query"
    results = reranker.rerank(query, long_docs, top_k=1)

    # Should handle long content without error
    assert len(results) == 1


def test_rerank_handles_special_characters(reranker, sample_documents):
    """Test rerank handles documents with special characters."""
    special_docs = [
        Document(
            id="special1",
            content="Content with special chars: @#$%^&*()!",
            metadata={}
        ),
        Document(
            id="special2",
            content="Unicode content: こんにちは 你好 مرحبا",
            metadata={}
        ),
    ]

    query = "special characters"
    results = reranker.rerank(query, special_docs, top_k=2)

    assert len(results) == 2


# ============================================================================
# Property Tests
# ============================================================================

def test_reranker_model_name_property(reranker):
    """Test that model_name property returns correct value."""
    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"


def test_reranker_device_property(reranker):
    """Test that device property returns correct value."""
    assert reranker.device in ["cpu", "mps", "cuda"]


def test_reranker_max_length_property(reranker):
    """Test that max_length property returns correct value."""
    assert reranker.max_length == 512


# ============================================================================
# Integration Tests
# ============================================================================

def test_rerank_typical_use_case(reranker, sample_documents):
    """Test typical reranking workflow."""
    # Simulate retrieval results that need reranking
    query = "managing toddler behavior"

    # Initial retrieval (mocked - would come from vector search)
    candidates = sample_documents[:5]

    # Rerank to get top 3 most relevant
    reranked = reranker.rerank(query, candidates, top_k=3)

    assert len(reranked) == 3
    assert all(isinstance(doc, Document) for doc in reranked)
    # Most relevant documents should be at the top
    assert reranked[0] in candidates


def test_rerank_with_diverse_queries(reranker, sample_documents):
    """Test reranking with different types of queries."""
    queries = [
        "toddler tantrums",
        "sleep training methods",
        "positive discipline",
        "child development",
        "emotional regulation"
    ]

    for query in queries:
        results = reranker.rerank(query, sample_documents, top_k=3)
        assert len(results) == 3
        assert all(isinstance(doc, Document) for doc in results)


def test_rerank_preserves_document_metadata(reranker, sample_documents):
    """Test that reranking preserves document metadata."""
    query = "parenting advice"
    results = reranker.rerank(query, sample_documents, top_k=3)

    # Verify metadata is preserved
    for doc in results:
        assert 'source' in doc.metadata
        assert 'relevance' in doc.metadata


def test_rerank_with_duplicate_documents(reranker):
    """Test reranking with duplicate documents."""
    duplicate_docs = [
        Document(id="dup1", content="Same content", metadata={}),
        Document(id="dup2", content="Same content", metadata={}),
        Document(id="dup3", content="Different content", metadata={}),
    ]

    query = "content"
    results = reranker.rerank(query, duplicate_docs, top_k=3)

    # Should return all 3 documents even if content is duplicated
    assert len(results) == 3


# ============================================================================
# Performance and Logging Tests
# ============================================================================

def test_rerank_logs_statistics(reranker, sample_documents, caplog):
    """Test that rerank logs useful statistics."""
    import logging
    caplog.set_level(logging.INFO)

    query = "test query"
    reranker.rerank(query, sample_documents, top_k=3)

    # Check that INFO log was generated with statistics
    assert any("Reranked" in record.message for record in caplog.records)


def test_rerank_logs_warning_for_empty_documents(reranker, caplog):
    """Test that warning is logged for empty documents."""
    import logging
    caplog.set_level(logging.WARNING)

    query = "test query"
    reranker.rerank(query, [], top_k=3)

    # Check that WARNING log was generated
    assert any("empty documents" in record.message.lower() for record in caplog.records)


def test_rerank_logs_debug_for_single_document(reranker, sample_documents, caplog):
    """Test that debug log is generated for single document."""
    import logging
    caplog.set_level(logging.DEBUG)

    query = "test query"
    reranker.rerank(query, [sample_documents[0]], top_k=3)

    # Check that DEBUG log was generated
    assert any("Single document" in record.message for record in caplog.records)


# ============================================================================
# Comparative Tests
# ============================================================================

def test_rerank_changes_order_from_retrieval(reranker, sample_documents):
    """Test that reranking produces different order than retrieval."""
    # Mock predict to return reverse order scores
    def mock_predict_reverse(pairs, show_progress_bar=False):
        return np.array([0.1, 0.3, 0.5, 0.7, 0.9])

    reranker._model.predict = mock_predict_reverse

    query = "test query"
    results = reranker.rerank(query, sample_documents, top_k=5)

    # Order should be reversed from input
    assert results[0].id == "doc5"
    assert results[-1].id == "doc1"


def test_rerank_improves_precision_at_k(reranker):
    """Test that reranking improves precision for top results."""
    # Create documents where high relevance is scattered
    mixed_docs = [
        Document(id="low1", content="Irrelevant content", metadata={"true_relevance": "low"}),
        Document(id="high1", content="Highly relevant content", metadata={"true_relevance": "high"}),
        Document(id="low2", content="Another irrelevant", metadata={"true_relevance": "low"}),
        Document(id="high2", content="Very relevant content", metadata={"true_relevance": "high"}),
        Document(id="low3", content="Not relevant", metadata={"true_relevance": "low"}),
    ]

    # Mock predict to give high scores to high relevance docs
    def mock_predict_relevance(pairs, show_progress_bar=False):
        scores = []
        for pair in pairs:
            content = pair[1]
            if "relevant content" in content.lower():
                scores.append(0.9)
            else:
                scores.append(0.1)
        return np.array(scores)

    reranker._model.predict = mock_predict_relevance

    query = "relevant information"
    results = reranker.rerank(query, mixed_docs, top_k=2)

    # Top 2 should be high relevance documents
    assert all(doc.metadata["true_relevance"] == "high" for doc in results)
