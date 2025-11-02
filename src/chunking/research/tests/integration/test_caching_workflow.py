"""
Integration tests for caching workflow (T059-T062).

Tests verify:
- Cache hit/miss scenarios (T060, T061)
- Token reduction with reprocessing (T062)
- TTL expiration and cleanup
- Cache warming strategy
"""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.chunking.research.cache_store import FileCacheStore
from src.chunking.chunking_pipeline import ChunkingPipeline
from src.chunking.llm_provider import MockLLMProvider
from src.chunking.models import Document


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary cache directory for tests"""
    return tmp_path / "test_cache"


@pytest.fixture
def cache_store(temp_cache_dir):
    """FileCacheStore with short TTL for testing"""
    return FileCacheStore(
        cache_dir=temp_cache_dir,
        default_ttl=2  # 2 seconds for fast testing
    )


@pytest.fixture
def mock_llm():
    """Mock LLM provider with structure analysis response"""
    responses = {
        "openai/gpt-4o": {
            "id": "test-response",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Introduction\t1\t0\t1000\tROOT"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 50,
                "total_tokens": 550
            }
        }
    }
    return MockLLMProvider(responses=responses)


@pytest.fixture
def sample_document():
    """Sample document for testing"""
    content = "# Introduction\n\nThis is a test document with some content."
    return Document(
        file_path=Path("test.txt"),
        content=content,
        document_id="test_doc",
        file_hash="abc123"
    )


@pytest.fixture
def pipeline(mock_llm, cache_store):
    """ChunkingPipeline with mocked dependencies"""
    return ChunkingPipeline(
        llm_provider=mock_llm,
        cache_store=cache_store,
        structure_model="openai/gpt-4o",
        boundary_model="openai/gpt-4o",
        segmentation_model="google/gemini-2.0-flash-exp"
    )


# ============================================================================
# T060: Cache Hit Scenario
# ============================================================================


def test_cache_hit_on_second_analysis(pipeline, sample_document, cache_store):
    """
    T060: Verify cache hit when analyzing same document twice.

    Expected behavior:
    - First analysis: cache miss, consumes tokens
    - Second analysis: cache hit, zero tokens consumed
    """
    # First analysis - should be cache miss
    result1 = pipeline._get_structure_analyzer().analyze(sample_document)

    assert result1["cache_hit"] is False
    assert result1["tokens_consumed"] > 0
    first_tokens = result1["tokens_consumed"]

    # Verify cache was populated
    cache_key = pipeline._get_structure_analyzer().generate_cache_key(
        sample_document.content,
        prefix="structure"
    )
    assert cache_store.get(cache_key) is not None

    # Second analysis - should be cache hit
    result2 = pipeline._get_structure_analyzer().analyze(sample_document)

    assert result2["cache_hit"] is True
    assert result2["tokens_consumed"] == 0

    # Structures should be equivalent
    assert result2["structure"].chapter_title == result1["structure"].chapter_title
    assert len(result2["structure"].sections) == len(result1["structure"].sections)


# ============================================================================
# T061: Cache Miss Scenario
# ============================================================================


def test_cache_miss_with_different_content(pipeline, sample_document, cache_store):
    """
    T061: Verify cache miss when content changes.

    Expected behavior:
    - Analyze document A: cache miss
    - Analyze document B (different content): cache miss
    - Different cache keys should be used
    """
    # Analyze first document
    result1 = pipeline._get_structure_analyzer().analyze(sample_document)

    assert result1["cache_hit"] is False
    assert result1["tokens_consumed"] > 0

    # Create document with different content
    modified_document = Document(
        file_path=sample_document.file_path,
        content=sample_document.content + "\n\nAdditional content",
        document_id=sample_document.document_id,
        file_hash="different_hash"
    )

    # Analyze modified document - should be cache miss
    result2 = pipeline._get_structure_analyzer().analyze(modified_document)

    assert result2["cache_hit"] is False
    assert result2["tokens_consumed"] > 0

    # Verify different cache keys were used
    cache_key1 = pipeline._get_structure_analyzer().generate_cache_key(
        sample_document.content,
        prefix="structure"
    )
    cache_key2 = pipeline._get_structure_analyzer().generate_cache_key(
        modified_document.content,
        prefix="structure"
    )

    assert cache_key1 != cache_key2


# ============================================================================
# T062: Token Reduction Verification
# ============================================================================


def test_token_reduction_with_reprocessing(pipeline, cache_store):
    """
    T062: Verify token consumption reduction with cache.

    Expected behavior:
    - Process 3 identical documents
    - First: consumes tokens
    - Second and third: zero tokens (cache hits)
    - Total tokens << 3x first document tokens
    """
    # Create 3 identical documents
    documents = []
    for i in range(3):
        content = "# Test Document\n\nSome test content for caching."
        doc = Document(
            file_path=Path(f"test_{i}.txt"),
            content=content,
            document_id=f"test_doc_{i}",
            file_hash=f"hash_{i}"
        )
        documents.append(doc)

    # Analyze all documents
    results = []
    total_tokens = 0

    for doc in documents:
        result = pipeline._get_structure_analyzer().analyze(doc)
        results.append(result)
        total_tokens += result["tokens_consumed"]

    # Verify first document consumed tokens
    assert results[0]["cache_hit"] is False
    assert results[0]["tokens_consumed"] > 0
    first_tokens = results[0]["tokens_consumed"]

    # Verify subsequent documents used cache
    assert results[1]["cache_hit"] is True
    assert results[1]["tokens_consumed"] == 0

    assert results[2]["cache_hit"] is True
    assert results[2]["tokens_consumed"] == 0

    # Verify total tokens is just from first document
    assert total_tokens == first_tokens

    # Calculate token savings percentage
    tokens_without_cache = first_tokens * 3
    token_savings = (tokens_without_cache - total_tokens) / tokens_without_cache

    assert token_savings >= 0.66  # At least 66% savings (2 out of 3 cached)


# ============================================================================
# TTL Expiration Tests
# ============================================================================


def test_cache_expiration_after_ttl(pipeline, sample_document, cache_store):
    """
    Verify cache entries expire after TTL.

    Expected behavior:
    - Analyze document: cache populated
    - Wait for TTL to expire
    - Re-analyze: cache miss (expired)
    """
    # First analysis - cache populated
    result1 = pipeline._get_structure_analyzer().analyze(sample_document)
    assert result1["cache_hit"] is False

    # Wait for TTL to expire (2 seconds + buffer)
    time.sleep(2.5)

    # Second analysis - cache should be expired
    result2 = pipeline._get_structure_analyzer().analyze(sample_document)
    assert result2["cache_hit"] is False
    assert result2["tokens_consumed"] > 0


def test_cache_cleanup_removes_expired_entries(cache_store, sample_document):
    """
    Verify cleanup_expired removes expired entries.

    Expected behavior:
    - Store entry with short TTL
    - Wait for expiration
    - Call cleanup_expired()
    - Verify entry removed
    """
    # Store a cache entry
    cache_key = "test_structure_abc123"
    cache_data = {
        "document_id": sample_document.document_id,
        "chapter_title": "Test",
        "sections": []
    }

    cache_store.set(cache_key, cache_data, ttl=1)  # 1 second TTL

    # Verify entry exists
    assert cache_store.get(cache_key) is not None

    # Wait for expiration
    time.sleep(1.5)

    # Cleanup expired entries
    removed_count = cache_store.cleanup_expired()

    assert removed_count == 1
    assert cache_store.get(cache_key) is None


# ============================================================================
# Cache Warming Tests
# ============================================================================


def test_cache_warming_strategy(pipeline):
    """
    Verify cache warming pre-populates cache.

    Expected behavior:
    - Call warm_cache() with documents
    - Verify cache populated
    - Subsequent analysis uses cache
    """
    # Create documents to warm cache
    documents = []
    for i in range(3):
        content = f"# Document {i}\n\nTest content for document {i}."
        doc = Document(
            file_path=Path(f"doc_{i}.txt"),
            content=content,
            document_id=f"doc_{i}",
            file_hash=f"hash_{i}"
        )
        documents.append(doc)

    # Warm cache
    cached_count = pipeline.warm_cache(documents)

    assert cached_count == 3

    # Verify subsequent analysis uses cache
    for doc in documents:
        result = pipeline._get_structure_analyzer().analyze(doc)
        assert result["cache_hit"] is True
        assert result["tokens_consumed"] == 0


# ============================================================================
# Cache Statistics Tests
# ============================================================================


def test_cache_statistics_tracking(cache_store):
    """
    Verify cache statistics are accurate.

    Expected behavior:
    - Get initial stats
    - Add entries
    - Get updated stats
    - Verify counts are correct
    """
    # Initial stats
    stats = cache_store.get_stats()
    initial_count = stats["file_count"]

    # Add cache entries
    for i in range(5):
        cache_store.set(
            f"test_key_{i}",
            {"data": f"value_{i}"},
            ttl=10
        )

    # Get updated stats
    stats = cache_store.get_stats()

    assert stats["file_count"] == initial_count + 5
    assert stats["total_size_bytes"] > 0
    assert "cache_dir" in stats
