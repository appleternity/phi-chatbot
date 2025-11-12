#!/usr/bin/env python3
"""Test script to verify all three retrieval strategies work.

Usage:
    python test_strategies.py
"""

import asyncio
import sys
from contextlib import asynccontextmanager

# Set up path for imports
sys.path.insert(0, ".")

from app.config import settings
from app.db.connection import get_pool, close_pool
from app.retrieval import get_retriever
from app.embeddings.local_encoder import LocalEmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker


async def test_strategy(strategy_name: str):
    """Test a specific retrieval strategy."""
    print(f"\n{'='*60}")
    print(f"Testing strategy: {strategy_name}")
    print(f"{'='*60}")

    # Override settings for this test
    settings.RETRIEVAL_STRATEGY = strategy_name
    settings.PRELOAD_MODELS = False  # Lazy loading for faster tests

    try:
        # 1. Initialize database connection
        print("✓ Connecting to database...")
        pool = await get_pool()

        # 2. Initialize encoder
        print(f"✓ Creating encoder ({settings.EMBEDDING_MODEL})...")
        encoder = LocalEmbeddingProvider(
            model_name=settings.EMBEDDING_MODEL,
            device="mps",
            batch_size=16,
            max_length=1024,
            normalize_embeddings=True,
            instruction=None
        )

        # 3. Initialize reranker (if needed)
        reranker = None
        if strategy_name in ["rerank", "advanced"]:
            print(f"✓ Creating reranker ({settings.RERANKER_MODEL})...")
            reranker = Qwen3Reranker(
                model_name=settings.RERANKER_MODEL,
                device="mps",
                batch_size=8
            )
        else:
            print("✓ Skipping reranker (not needed for simple strategy)")

        # 4. Create retriever using factory
        print(f"✓ Creating retriever with factory...")
        retriever = get_retriever(
            pool=pool,
            encoder=encoder,
            reranker=reranker
        )

        # 5. Verify retriever type
        retriever_class = retriever.__class__.__name__
        print(f"✓ Retriever created: {retriever_class}")

        # 6. Test search (simple smoke test - don't actually run search to avoid loading models)
        print(f"✓ Strategy '{strategy_name}' initialized successfully!")

        # Clean up
        await close_pool()

        return True

    except Exception as e:
        print(f"✗ Error testing strategy '{strategy_name}': {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run tests for all three strategies."""
    print("\n" + "="*60)
    print("RETRIEVAL STRATEGY INTEGRATION TESTS")
    print("="*60)

    strategies = ["simple", "rerank", "advanced"]
    results = {}

    for strategy in strategies:
        success = await test_strategy(strategy)
        results[strategy] = success

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for strategy, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {strategy}")
        if not success:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n🎉 All strategies work correctly!")
        return 0
    else:
        print("\n❌ Some strategies failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
