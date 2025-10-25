"""Unit tests for HybridRetriever combining FAISS and BM25 search."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import numpy as np
from typing import List

from app.core.hybrid_retriever import HybridRetriever
from app.core.retriever import Document, DocumentRetriever


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_documents():
    """Create sample documents for testing."""
    return [
        Document(
            id="doc1",
            content="Toddler tantrums are normal developmental behavior at age 2-3",
            metadata={"source": "parenting_guide", "age_range": "2-3"}
        ),
        Document(
            id="doc2",
            content="Sleep training methods for infants include cry it out and gradual extinction",
            metadata={"source": "sleep_guide", "age_range": "0-1"}
        ),
        Document(
            id="doc3",
            content="Positive discipline strategies help toddlers learn emotional regulation",
            metadata={"source": "discipline_guide", "age_range": "2-4"}
        ),
        Document(
            id="doc4",
            content="Child development milestones for two year olds include language growth",
            metadata={"source": "development_guide", "age_range": "2-3"}
        ),
        Document(
            id="doc5",
            content="Parenting techniques for managing behavior in young children",
            metadata={"source": "behavior_guide", "age_range": "1-5"}
        ),
    ]


@pytest.fixture
def child_documents():
    """Create child documents with parent references for testing."""
    return [
        Document(
            id="child1",
            content="Toddler tantrums peak around age 2",
            metadata={"parent_id": "parent1", "source": "guide"}
        ),
        Document(
            id="child2",
            content="Sleep patterns vary by age",
            metadata={"parent_id": "parent1", "source": "guide"}
        ),
        Document(
            id="child3",
            content="Discipline should be age-appropriate",
            metadata={"parent_id": "parent2", "source": "guide"}
        ),
    ]


@pytest.fixture
def parent_documents():
    """Create parent documents for testing."""
    return [
        Document(
            id="parent1",
            content="Comprehensive guide to toddler behavior and sleep",
            metadata={"source": "guide"}
        ),
        Document(
            id="parent2",
            content="Guide to positive discipline strategies",
            metadata={"source": "guide"}
        ),
    ]


@pytest.fixture
def mock_faiss_retriever(sample_documents):
    """Create a mock FAISS retriever."""
    mock_retriever = AsyncMock(spec=DocumentRetriever)

    # Mock search to return documents in order
    async def mock_search(query: str, top_k: int = 3):
        return sample_documents[:top_k]

    mock_retriever.search = mock_search

    # Mock add_documents
    async def mock_add_documents(docs: List[Document]):
        pass

    mock_retriever.add_documents = mock_add_documents

    return mock_retriever


@pytest.fixture
def hybrid_retriever(mock_faiss_retriever, sample_documents):
    """Create HybridRetriever instance with mocked FAISS."""
    return HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.5
    )


# ============================================================================
# Initialization Tests
# ============================================================================

def test_hybrid_retriever_initialization_valid_params(mock_faiss_retriever, sample_documents):
    """Test HybridRetriever initializes with valid parameters."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.5
    )

    assert retriever._alpha == 0.5
    assert len(retriever._documents) == len(sample_documents)
    assert retriever._bm25_index is not None


def test_hybrid_retriever_initialization_invalid_alpha(mock_faiss_retriever, sample_documents):
    """Test HybridRetriever raises ValueError for invalid alpha."""
    with pytest.raises(ValueError, match="alpha must be in"):
        HybridRetriever(
            faiss_retriever=mock_faiss_retriever,
            documents=sample_documents,
            alpha=1.5
        )

    with pytest.raises(ValueError, match="alpha must be in"):
        HybridRetriever(
            faiss_retriever=mock_faiss_retriever,
            documents=sample_documents,
            alpha=-0.5
        )


def test_hybrid_retriever_initialization_empty_documents(mock_faiss_retriever):
    """Test HybridRetriever raises ValueError for empty documents list."""
    with pytest.raises(ValueError, match="documents list cannot be empty"):
        HybridRetriever(
            faiss_retriever=mock_faiss_retriever,
            documents=[],
            alpha=0.5
        )


def test_hybrid_retriever_builds_doc_id_mapping(mock_faiss_retriever, sample_documents):
    """Test that document ID to index mapping is built correctly."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.5
    )

    assert len(retriever._doc_id_to_idx) == len(sample_documents)
    assert "doc1" in retriever._doc_id_to_idx
    assert retriever._doc_id_to_idx["doc1"] == 0


def test_hybrid_retriever_builds_bm25_index(mock_faiss_retriever, sample_documents):
    """Test that BM25 index is built on initialization."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.5
    )

    assert retriever._bm25_index is not None
    assert len(retriever._tokenized_corpus) == len(sample_documents)


# ============================================================================
# Search Tests
# ============================================================================

@pytest.mark.asyncio
async def test_hybrid_search_returns_documents(hybrid_retriever):
    """Test that hybrid search returns documents."""
    results = await hybrid_retriever.search("toddler tantrums", top_k=3)

    assert len(results) <= 3
    assert all(isinstance(doc, Document) for doc in results)


@pytest.mark.asyncio
async def test_hybrid_search_empty_query(hybrid_retriever):
    """Test hybrid search with empty query."""
    results = await hybrid_retriever.search("", top_k=3)

    # Should still return results based on default scoring
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_search_top_k_parameter(hybrid_retriever):
    """Test that top_k parameter limits results correctly."""
    results = await hybrid_retriever.search("parenting", top_k=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_hybrid_search_top_k_exceeds_documents(hybrid_retriever):
    """Test handling when top_k exceeds available documents."""
    results = await hybrid_retriever.search("parenting", top_k=100)

    # Should return all available documents (5 in this case)
    assert len(results) <= len(hybrid_retriever._documents)


@pytest.mark.asyncio
async def test_hybrid_search_combines_vector_and_keyword(hybrid_retriever):
    """Test that hybrid search combines both FAISS and BM25 results."""
    # Query that should match both semantically and via keywords
    results = await hybrid_retriever.search("toddler development", top_k=3)

    assert len(results) > 0
    # Results should include documents matching either vector or keyword search


@pytest.mark.asyncio
async def test_hybrid_search_alpha_zero_pure_bm25(mock_faiss_retriever, sample_documents):
    """Test that alpha=0.0 uses pure BM25 search."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.0  # Pure BM25
    )

    results = await retriever.search("toddler tantrums", top_k=3)

    assert len(results) > 0


@pytest.mark.asyncio
async def test_hybrid_search_alpha_one_pure_faiss(mock_faiss_retriever, sample_documents):
    """Test that alpha=1.0 uses pure FAISS search."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=1.0  # Pure FAISS
    )

    results = await retriever.search("toddler tantrums", top_k=3)

    assert len(results) > 0


# ============================================================================
# Parent-Child Retrieval Tests
# ============================================================================

@pytest.mark.asyncio
async def test_hybrid_search_retrieves_parent_documents(mock_faiss_retriever, child_documents, parent_documents):
    """Test that search returns parent documents when child has parent_id."""
    all_docs = child_documents + parent_documents

    # Configure mock to return child documents
    async def mock_search_returns_children(query: str, top_k: int = 3):
        return child_documents[:top_k]

    mock_faiss_retriever.search = mock_search_returns_children

    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=all_docs,
        alpha=0.5
    )

    results = await retriever.search("toddler", top_k=3)

    # Should return parent documents instead of children
    result_ids = {doc.id for doc in results}
    assert any(doc_id.startswith('parent') for doc_id in result_ids)


@pytest.mark.asyncio
async def test_hybrid_search_deduplicates_parent_documents(mock_faiss_retriever, child_documents, parent_documents):
    """Test that parent documents are not duplicated when multiple children match."""
    all_docs = child_documents + parent_documents

    # Configure mock to return multiple children with same parent
    async def mock_search_returns_siblings(query: str, top_k: int = 3):
        # Return child1 and child2, both have parent1
        return [child_documents[0], child_documents[1]]

    mock_faiss_retriever.search = mock_search_returns_siblings

    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=all_docs,
        alpha=0.5
    )

    results = await retriever.search("toddler", top_k=3)

    # Should only return parent1 once, not twice
    result_ids = [doc.id for doc in results]
    parent1_count = result_ids.count('parent1')
    assert parent1_count <= 1


@pytest.mark.asyncio
async def test_hybrid_search_fallback_to_child_when_parent_missing(mock_faiss_retriever):
    """Test fallback to child document when parent is not found."""
    # Child with parent_id that doesn't exist
    orphan_child = Document(
        id="orphan",
        content="Child without parent",
        metadata={"parent_id": "nonexistent_parent"}
    )

    async def mock_search_returns_orphan(query: str, top_k: int = 3):
        return [orphan_child]

    mock_faiss_retriever.search = mock_search_returns_orphan

    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=[orphan_child],
        alpha=0.5
    )

    results = await retriever.search("test", top_k=1)

    # Should return the child since parent is missing
    assert len(results) == 1
    assert results[0].id == "orphan"


# ============================================================================
# Score Normalization Tests
# ============================================================================

def test_normalize_scores_valid_scores(hybrid_retriever):
    """Test score normalization with valid scores."""
    scores = {1: 10.0, 2: 5.0, 3: 0.0}

    normalized = hybrid_retriever._normalize_scores(scores)

    assert normalized[1] == 1.0  # Max score
    assert normalized[3] == 0.0  # Min score
    assert 0.0 <= normalized[2] <= 1.0  # Middle score


def test_normalize_scores_identical_scores(hybrid_retriever):
    """Test normalization when all scores are identical."""
    scores = {1: 5.0, 2: 5.0, 3: 5.0}

    normalized = hybrid_retriever._normalize_scores(scores)

    # All should be 0.5 when identical
    assert all(score == 0.5 for score in normalized.values())


def test_normalize_scores_empty_dict(hybrid_retriever):
    """Test normalization with empty score dictionary."""
    scores = {}

    normalized = hybrid_retriever._normalize_scores(scores)

    assert normalized == {}


def test_normalize_scores_single_score(hybrid_retriever):
    """Test normalization with single score."""
    scores = {1: 10.0}

    normalized = hybrid_retriever._normalize_scores(scores)

    assert normalized[1] == 0.5


# ============================================================================
# Score Combination Tests
# ============================================================================

def test_combine_scores_equal_weights(hybrid_retriever):
    """Test score combination with equal weights (alpha=0.5)."""
    vector_scores = {1: 1.0, 2: 0.5, 3: 0.0}
    bm25_scores = {1: 0.0, 2: 0.5, 3: 1.0}

    combined = hybrid_retriever._combine_scores(vector_scores, bm25_scores)

    # With alpha=0.5: combined = 0.5*vector + 0.5*bm25
    assert combined[1] == pytest.approx(0.5, rel=1e-5)  # 0.5*1.0 + 0.5*0.0
    assert combined[2] == pytest.approx(0.5, rel=1e-5)  # 0.5*0.5 + 0.5*0.5
    assert combined[3] == pytest.approx(0.5, rel=1e-5)  # 0.5*0.0 + 0.5*1.0


def test_combine_scores_vector_only(mock_faiss_retriever, sample_documents):
    """Test score combination with alpha=1.0 (vector only)."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=1.0  # Vector only
    )

    vector_scores = {1: 1.0, 2: 0.5}
    bm25_scores = {1: 0.0, 2: 0.5}

    combined = retriever._combine_scores(vector_scores, bm25_scores)

    # With alpha=1.0: combined = 1.0*vector + 0.0*bm25
    assert combined[1] == 1.0
    assert combined[2] == 0.5


def test_combine_scores_bm25_only(mock_faiss_retriever, sample_documents):
    """Test score combination with alpha=0.0 (BM25 only)."""
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=sample_documents,
        alpha=0.0  # BM25 only
    )

    vector_scores = {1: 1.0, 2: 0.5}
    bm25_scores = {1: 0.0, 2: 0.5}

    combined = retriever._combine_scores(vector_scores, bm25_scores)

    # With alpha=0.0: combined = 0.0*vector + 1.0*bm25
    assert combined[1] == 0.0
    assert combined[2] == 0.5


def test_combine_scores_partial_overlap(hybrid_retriever):
    """Test score combination when documents appear in only one score set."""
    vector_scores = {1: 1.0, 2: 0.5}
    bm25_scores = {2: 0.5, 3: 1.0}

    combined = hybrid_retriever._combine_scores(vector_scores, bm25_scores)

    # Doc 1: only in vector (gets 0 for BM25)
    assert combined[1] == pytest.approx(0.5, rel=1e-5)  # 0.5*1.0 + 0.5*0.0

    # Doc 2: in both
    assert combined[2] == pytest.approx(0.5, rel=1e-5)  # 0.5*0.5 + 0.5*0.5

    # Doc 3: only in BM25 (gets 0 for vector)
    assert combined[3] == pytest.approx(0.5, rel=1e-5)  # 0.5*0.0 + 0.5*1.0


# ============================================================================
# BM25 Search Tests
# ============================================================================

def test_bm25_search_returns_scores(hybrid_retriever):
    """Test that BM25 search returns score dictionary."""
    scores = hybrid_retriever._bm25_search("toddler development", top_k=3)

    assert isinstance(scores, dict)
    assert len(scores) > 0


def test_bm25_search_keyword_matching(hybrid_retriever):
    """Test that BM25 search matches documents with query keywords."""
    scores = hybrid_retriever._bm25_search("toddler", top_k=5)

    # Documents with "toddler" should have higher scores
    assert len(scores) > 0
    assert all(isinstance(score, float) for score in scores.values())


# ============================================================================
# Add Documents Tests
# ============================================================================

@pytest.mark.asyncio
async def test_add_documents_updates_index(hybrid_retriever):
    """Test that add_documents updates both FAISS and BM25 indices."""
    initial_count = len(hybrid_retriever._documents)

    new_docs = [
        Document(
            id="new1",
            content="New parenting advice about teens",
            metadata={"source": "new_guide"}
        )
    ]

    await hybrid_retriever.add_documents(new_docs)

    assert len(hybrid_retriever._documents) == initial_count + 1
    assert "new1" in hybrid_retriever._doc_id_to_idx


@pytest.mark.asyncio
async def test_add_documents_empty_list(hybrid_retriever):
    """Test that adding empty list is handled gracefully."""
    initial_count = len(hybrid_retriever._documents)

    await hybrid_retriever.add_documents([])

    assert len(hybrid_retriever._documents) == initial_count


@pytest.mark.asyncio
async def test_add_documents_updates_bm25_index(hybrid_retriever):
    """Test that BM25 index is rebuilt after adding documents."""
    initial_corpus_size = len(hybrid_retriever._tokenized_corpus)

    new_docs = [
        Document(
            id="new1",
            content="Additional content",
            metadata={}
        )
    ]

    await hybrid_retriever.add_documents(new_docs)

    # BM25 index should be rebuilt with new documents
    assert len(hybrid_retriever._tokenized_corpus) == initial_corpus_size + 1


# ============================================================================
# Statistics and Configuration Tests
# ============================================================================

def test_get_stats(hybrid_retriever):
    """Test retriever statistics reporting."""
    stats = hybrid_retriever.get_stats()

    assert 'total_documents' in stats
    assert 'alpha' in stats
    assert 'faiss_weight' in stats
    assert 'bm25_weight' in stats
    assert 'indexed_doc_ids' in stats

    assert stats['total_documents'] == len(hybrid_retriever._documents)
    assert stats['alpha'] == 0.5
    assert stats['faiss_weight'] == 0.5
    assert stats['bm25_weight'] == 0.5


def test_set_alpha_valid(hybrid_retriever):
    """Test setting alpha parameter dynamically."""
    hybrid_retriever.set_alpha(0.7)

    assert hybrid_retriever._alpha == 0.7

    stats = hybrid_retriever.get_stats()
    assert stats['alpha'] == 0.7
    assert stats['faiss_weight'] == 0.7
    assert stats['bm25_weight'] == 0.3


def test_set_alpha_invalid(hybrid_retriever):
    """Test that invalid alpha values raise ValueError."""
    with pytest.raises(ValueError, match="alpha must be in"):
        hybrid_retriever.set_alpha(1.5)

    with pytest.raises(ValueError, match="alpha must be in"):
        hybrid_retriever.set_alpha(-0.1)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_search_on_empty_index(mock_faiss_retriever):
    """Test search behavior with empty document index."""
    # Create retriever with minimal documents, then clear them
    initial_docs = [
        Document(id="temp", content="temp", metadata={})
    ]
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=initial_docs,
        alpha=0.5
    )

    # Clear documents to simulate empty index
    retriever._documents = []

    results = await retriever.search("query", top_k=3)

    assert results == []


def test_tokenize_documents(hybrid_retriever, sample_documents):
    """Test document tokenization for BM25."""
    tokenized = hybrid_retriever._tokenize_documents(sample_documents)

    assert len(tokenized) == len(sample_documents)
    assert all(isinstance(tokens, list) for tokens in tokenized)
    assert all(all(isinstance(token, str) for token in tokens) for tokens in tokenized)


def test_get_parent_document_exists(hybrid_retriever):
    """Test retrieving an existing parent document."""
    parent_doc = hybrid_retriever._get_parent_document("doc1")

    assert parent_doc is not None
    assert parent_doc.id == "doc1"


def test_get_parent_document_not_exists(hybrid_retriever):
    """Test retrieving a non-existent parent document."""
    parent_doc = hybrid_retriever._get_parent_document("nonexistent")

    assert parent_doc is None


def test_get_parent_document_without_id(mock_faiss_retriever):
    """Test parent retrieval when document has no ID."""
    docs = [
        Document(id=None, content="No ID document", metadata={})
    ]
    retriever = HybridRetriever(
        faiss_retriever=mock_faiss_retriever,
        documents=docs,
        alpha=0.5
    )

    parent_doc = retriever._get_parent_document("any_id")

    assert parent_doc is None
