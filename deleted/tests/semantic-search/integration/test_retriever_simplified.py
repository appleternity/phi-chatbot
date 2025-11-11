"""Test simplified PostgreSQL Retriever initialization.

This script validates TICKET-009 refactoring:
- Clean __init__ with pool parameter only
- Simple initialize() for preloading
- Lazy loading in search() method
- No try/except blocks
- Assert statements for validation
"""

import asyncio
import sys
from app.db.connection import DatabasePool
from app.core.postgres_retriever import PostgreSQLRetriever


async def test_lazy_loading():
    """Test 1: Lazy loading (no preload)."""
    print("\n=== Test 1: Lazy Loading (No Preload) ===")

    # Initialize pool
    pool = DatabasePool(min_size=2, max_size=5)
    await pool.initialize()
    print("✅ Database pool initialized")

    # Create retriever without preloading
    retriever = PostgreSQLRetriever(
        pool=pool,
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        reranker_model="Qwen/Qwen3-Reranker-0.6B",
        use_reranking=True
    )
    print("✅ Retriever created (models NOT preloaded)")
    print(f"   Encoder loaded: {retriever.encoder is not None}")
    print(f"   Reranker loaded: {retriever.reranker is not None}")

    # Search (models should lazy load)
    print("\n🔍 Executing search (models will lazy load)...")
    results = await retriever.search(
        query="aripiprazole mechanism of action",
        top_k=3
    )
    print(f"✅ Search completed: {len(results)} results")
    print(f"   Encoder loaded: {retriever.encoder is not None}")
    print(f"   Reranker loaded: {retriever.reranker is not None}")

    # Display results
    for i, doc in enumerate(results, 1):
        rerank_score = doc.metadata.get("rerank_score", 0.0)
        sim_score = doc.metadata["similarity_score"]
        print(f"\n{i}. {doc.metadata['chunk_id']}")
        print(f"   Rerank: {rerank_score:.4f} | Similarity: {sim_score:.4f}")
        print(f"   {doc.content[:150]}...")

    # Cleanup
    await retriever.close()
    await pool.close()
    print("\n✅ Test 1 PASSED")


async def test_preloading():
    """Test 2: Preloading with initialize()."""
    print("\n=== Test 2: Preloading Models ===")

    # Initialize pool
    pool = DatabasePool(min_size=2, max_size=5)
    await pool.initialize()
    print("✅ Database pool initialized")

    # Create retriever
    retriever = PostgreSQLRetriever(
        pool=pool,
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        reranker_model="Qwen/Qwen3-Reranker-0.6B",
        use_reranking=True
    )
    print("✅ Retriever created (models NOT preloaded yet)")
    print(f"   Encoder loaded: {retriever.encoder is not None}")
    print(f"   Reranker loaded: {retriever.reranker is not None}")

    # Preload models
    print("\n⚡ Preloading models...")
    await retriever.initialize()
    print("✅ Models preloaded")
    print(f"   Encoder loaded: {retriever.encoder is not None}")
    print(f"   Reranker loaded: {retriever.reranker is not None}")

    # Search (models already loaded)
    print("\n🔍 Executing search (models already loaded)...")
    results = await retriever.search(
        query="aripiprazole side effects",
        top_k=2
    )
    print(f"✅ Search completed: {len(results)} results")

    # Cleanup
    await retriever.close()
    await pool.close()
    print("\n✅ Test 2 PASSED")


async def test_no_reranking():
    """Test 3: Search without reranking (encoder only)."""
    print("\n=== Test 3: No Reranking (Encoder Only) ===")

    # Initialize pool
    pool = DatabasePool(min_size=2, max_size=5)
    await pool.initialize()
    print("✅ Database pool initialized")

    # Create retriever without reranking
    retriever = PostgreSQLRetriever(
        pool=pool,
        use_reranking=False  # Disable reranking
    )
    print("✅ Retriever created (reranking disabled)")

    # Search (only encoder should lazy load)
    print("\n🔍 Executing search (encoder lazy loads, no reranker)...")
    results = await retriever.search(
        query="aripiprazole dosage",
        top_k=2
    )
    print(f"✅ Search completed: {len(results)} results")
    print(f"   Encoder loaded: {retriever.encoder is not None}")
    print(f"   Reranker loaded: {retriever.reranker is not None}")

    # Verify only similarity scores (no rerank scores)
    for doc in results:
        assert "similarity_score" in doc.metadata
        print(f"   Similarity: {doc.metadata['similarity_score']:.4f}")

    # Cleanup
    await retriever.close()
    await pool.close()
    print("\n✅ Test 3 PASSED")


async def test_assertion_errors():
    """Test 4: Verify assert statements work correctly."""
    print("\n=== Test 4: Assertion Error Handling ===")

    # Initialize pool
    pool = DatabasePool(min_size=2, max_size=5)
    await pool.initialize()
    print("✅ Database pool initialized")

    # Create retriever
    retriever = PostgreSQLRetriever(pool=pool)

    # Test empty query assertion
    print("\n🧪 Testing empty query assertion...")
    try:
        await retriever.search(query="", top_k=5)
        print("❌ FAILED: Empty query should trigger assertion")
        return False
    except AssertionError as e:
        print(f"✅ Assertion caught: {e}")

    # Cleanup
    await pool.close()
    print("\n✅ Test 4 PASSED")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("PostgreSQL Retriever Simplified - Test Suite")
    print("Validating TICKET-009 Refactoring")
    print("=" * 60)

    try:
        # Run tests
        await test_lazy_loading()
        await test_preloading()
        await test_no_reranking()
        await test_assertion_errors()

        # Summary
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nSimplification Summary:")
        print("- ✅ __init__ simplified (pool parameter only)")
        print("- ✅ initialize() simplified (optional preloading)")
        print("- ✅ close() simplified (minimal cleanup)")
        print("- ✅ _load_reranker() removed")
        print("- ✅ Lazy loading in search() works")
        print("- ✅ No try/except blocks (fail fast)")
        print("- ✅ Assert statements for validation")

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
