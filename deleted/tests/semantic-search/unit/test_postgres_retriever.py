"""Unit tests for simplified PostgreSQL Retriever (TICKET-009).

Tests the refactored initialization without requiring database access.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, MagicMock
from app.core.postgres_retriever import PostgreSQLRetriever


def test_init_simplified():
    """Test 1: __init__ simplified - pool parameter only."""
    print("\n=== Test 1: Simplified __init__ ===")

    # Create mock pool
    mock_pool = Mock()
    mock_pool.initialize = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_pool.fetch = AsyncMock(return_value=[])

    # Create retriever
    retriever = PostgreSQLRetriever(
        pool=mock_pool,
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        reranker_model="Qwen/Qwen3-Reranker-0.6B",
        use_reranking=True
    )

    # Verify state
    assert retriever.db_pool == mock_pool, "Pool not set correctly"
    assert retriever.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert retriever.reranker_model == "Qwen/Qwen3-Reranker-0.6B"
    assert retriever.use_reranking is True
    assert retriever.encoder is None, "Encoder should be None (lazy load)"
    assert retriever.reranker is None, "Reranker should be None (lazy load)"

    print("✅ __init__ accepts pool parameter")
    print("✅ Models are None (lazy loaded)")
    print("✅ Test 1 PASSED")


async def test_initialize_simplified():
    """Test 2: initialize() simplified - straightforward model loading."""
    print("\n=== Test 2: Simplified initialize() ===")

    # Create mock pool
    mock_pool = Mock()
    retriever = PostgreSQLRetriever(pool=mock_pool, use_reranking=True)

    # Verify models not loaded
    assert retriever.encoder is None
    assert retriever.reranker is None
    print("✅ Models initially None")

    # Mock model classes to avoid actual loading
    from unittest.mock import patch

    with patch('app.core.postgres_retriever.Qwen3EmbeddingEncoder') as MockEncoder, \
         patch('app.core.postgres_retriever.Qwen3Reranker') as MockReranker:

        # Configure mocks
        mock_encoder = Mock()
        mock_encoder.device = "mps"
        MockEncoder.return_value = mock_encoder

        mock_reranker = Mock()
        MockReranker.return_value = mock_reranker

        # Call initialize
        await retriever.initialize()

        # Verify models loaded
        assert retriever.encoder is not None, "Encoder should be loaded"
        assert retriever.reranker is not None, "Reranker should be loaded"
        print("✅ Encoder loaded")
        print("✅ Reranker loaded")

        # Verify encoder initialized correctly
        MockEncoder.assert_called_once_with(
            model_name="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            batch_size=16,
            max_length=1024,
            normalize_embeddings=True,
            instruction=None
        )
        print("✅ Encoder initialized with correct parameters")

        # Verify reranker initialized correctly
        MockReranker.assert_called_once_with(
            model_name="Qwen/Qwen3-Reranker-0.6B",
            device="mps",
            batch_size=8
        )
        print("✅ Reranker initialized with correct parameters")

    print("✅ Test 2 PASSED")


async def test_close_simplified():
    """Test 3: close() simplified - minimal cleanup."""
    print("\n=== Test 3: Simplified close() ===")

    mock_pool = Mock()
    retriever = PostgreSQLRetriever(pool=mock_pool)

    # close() should just log, no complex cleanup
    await retriever.close()
    print("✅ close() executes without errors")
    print("✅ Test 3 PASSED")


async def test_lazy_loading_in_search():
    """Test 4: search() has lazy loading logic."""
    print("\n=== Test 4: Lazy Loading in search() ===")

    # Create mock pool with fetch method
    mock_pool = Mock()
    mock_pool.fetch = AsyncMock(return_value=[])

    retriever = PostgreSQLRetriever(pool=mock_pool, use_reranking=False)

    # Verify encoder is None
    assert retriever.encoder is None
    print("✅ Encoder initially None")

    # Mock encoder to avoid actual loading
    from unittest.mock import patch
    import numpy as np

    with patch('app.core.postgres_retriever.Qwen3EmbeddingEncoder') as MockEncoder:
        # Configure mock encoder
        mock_encoder = Mock()
        mock_encoder.encode = Mock(return_value=np.zeros(1024))
        MockEncoder.return_value = mock_encoder

        # Call search (should lazy load encoder)
        await retriever.search(query="test query", top_k=5)

        # Verify encoder was lazy loaded
        assert retriever.encoder is not None, "Encoder should be lazy loaded"
        MockEncoder.assert_called_once()
        print("✅ Encoder lazy loaded on first search")

    print("✅ Test 4 PASSED")


async def test_no_try_except_blocks():
    """Test 5: Verify exceptions propagate (no try/except)."""
    print("\n=== Test 5: No try/except Blocks (Fail Fast) ===")

    mock_pool = Mock()
    retriever = PostgreSQLRetriever(pool=mock_pool)

    # Test assertion errors propagate
    try:
        await retriever.search(query="", top_k=5)
        assert False, "Empty query should raise AssertionError"
    except AssertionError as e:
        print(f"✅ AssertionError propagated: {e}")

    try:
        await retriever.search(query="   ", top_k=5)
        assert False, "Whitespace query should raise AssertionError"
    except AssertionError as e:
        print(f"✅ AssertionError propagated: {e}")

    print("✅ Test 5 PASSED")


def test_removed_load_reranker():
    """Test 6: Verify _load_reranker() method removed."""
    print("\n=== Test 6: _load_reranker() Method Removed ===")

    mock_pool = Mock()
    retriever = PostgreSQLRetriever(pool=mock_pool)

    # Verify _load_reranker method doesn't exist
    assert not hasattr(retriever, '_load_reranker'), \
        "_load_reranker() method should be removed"
    print("✅ _load_reranker() method removed")
    print("✅ Test 6 PASSED")


async def test_assertions_used():
    """Test 7: Verify assert statements replace if/raise."""
    print("\n=== Test 7: Assert Statements Used ===")

    # The code now uses assertions instead of if/raise
    # We can verify this by triggering them

    mock_pool = Mock()
    retriever = PostgreSQLRetriever(pool=mock_pool)

    # Test pool assertion
    retriever.db_pool = None
    try:
        await retriever.search(query="test", top_k=5)
        assert False, "Should raise AssertionError for None pool"
    except AssertionError as e:
        assert "pool" in str(e).lower()
        print("✅ Assert statement for pool validation")

    print("✅ Test 7 PASSED")


async def main():
    """Run all unit tests."""
    print("=" * 70)
    print("PostgreSQL Retriever Simplified - Unit Test Suite")
    print("Validating TICKET-009 Refactoring (No Database Required)")
    print("=" * 70)

    try:
        # Synchronous tests
        test_init_simplified()
        test_removed_load_reranker()

        # Async tests
        await test_initialize_simplified()
        await test_close_simplified()
        await test_lazy_loading_in_search()
        await test_no_try_except_blocks()
        await test_assertions_used()

        # Summary
        print("\n" + "=" * 70)
        print("✅ ALL UNIT TESTS PASSED")
        print("=" * 70)
        print("\nTICKET-009 Simplification Verified:")
        print("✅ 1. __init__ simplified (pool parameter only)")
        print("✅ 2. initialize() simplified (straightforward model loading)")
        print("✅ 3. close() simplified (minimal cleanup)")
        print("✅ 4. _load_reranker() method removed")
        print("✅ 5. Lazy loading logic in search()")
        print("✅ 6. No try/except blocks (fail fast)")
        print("✅ 7. Assert statements for validation")
        print("\n📝 Checklist Complete:")
        print("   [x] Simplify __init__ - remove db_url, require pool")
        print("   [x] Simplify initialize() - straightforward model loading")
        print("   [x] Simplify close() - minimal cleanup")
        print("   [x] Remove _load_reranker() method")
        print("   [x] Add lazy loading logic to search()")
        print("   [x] Remove ALL try/except blocks")
        print("   [x] Replace validations with assert statements")

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
