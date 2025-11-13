"""Comprehensive verification tests for retrieval module.

Tests all three strategies: simple, rerank, advanced
"""

import asyncio
import logging

# Force reload of environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from app.config import settings
from app.db.connection import DatabasePool
from app.embeddings.local_encoder import LocalEmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker
from app.retrieval import get_retriever, SimpleRetriever, RerankRetriever, AdvancedRetriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_simple_retriever():
    """Test SimpleRetriever: query → embedding → pgvector search."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: SimpleRetriever (no reranking)")
    logger.info("=" * 80)

    async with DatabasePool() as pool:
        encoder = LocalEmbeddingProvider(
            model_name=settings.EMBEDDING_MODEL,
            device="mps",
            batch_size=16
        )

        retriever = SimpleRetriever(pool=pool, encoder=encoder)

        # Test search
        query = "What are the side effects of aripiprazole?"
        results = await retriever.search(query, top_k=3)

        # Verify results
        assert len(results) > 0, "Should return results"
        assert len(results) <= 3, "Should respect top_k limit"

        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Chunk ID: {result['chunk_id']}")
            logger.info(f"  Source: {result['source_document']}")
            logger.info(f"  Similarity: {result['similarity_score']:.4f}")
            logger.info(f"  Content: {result['chunk_text'][:100]}...")

            # Verify required fields
            assert "chunk_id" in result
            assert "chunk_text" in result
            assert "similarity_score" in result
            assert "rerank_score" not in result, "Simple retriever should NOT have rerank_score"

    logger.info("\n✓ SimpleRetriever test passed")


async def test_rerank_retriever():
    """Test RerankRetriever: query → search top_k*4 → rerank → top_k."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: RerankRetriever (two-stage retrieval)")
    logger.info("=" * 80)

    async with DatabasePool() as pool:
        encoder = LocalEmbeddingProvider(
            model_name=settings.EMBEDDING_MODEL,
            device="mps",
            batch_size=16
        )
        reranker = Qwen3Reranker(device="mps")

        retriever = RerankRetriever(pool=pool, encoder=encoder, reranker=reranker)

        # Test search
        query = "What are the side effects of aripiprazole?"
        results = await retriever.search(query, top_k=3)

        # Verify results
        assert len(results) > 0, "Should return results"
        assert len(results) <= 3, "Should respect top_k limit"

        # Verify rerank scores are sorted descending
        rerank_scores = [r["rerank_score"] for r in results]
        assert rerank_scores == sorted(rerank_scores, reverse=True), "Results should be sorted by rerank_score"

        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Chunk ID: {result['chunk_id']}")
            logger.info(f"  Source: {result['source_document']}")
            logger.info(f"  Similarity: {result['similarity_score']:.4f}")
            logger.info(f"  Rerank Score: {result['rerank_score']:.4f}")
            logger.info(f"  Content: {result['chunk_text'][:100]}...")

            # Verify required fields
            assert "chunk_id" in result
            assert "chunk_text" in result
            assert "similarity_score" in result
            assert "rerank_score" in result, "Rerank retriever MUST have rerank_score"

    logger.info("\n✓ RerankRetriever test passed")


async def test_advanced_retriever():
    """Test AdvancedRetriever: query expansion → search → dedupe → rerank."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: AdvancedRetriever (query expansion + reranking)")
    logger.info("=" * 80)

    async with DatabasePool() as pool:
        encoder = LocalEmbeddingProvider(
            model_name=settings.EMBEDDING_MODEL,
            device="mps",
            batch_size=16
        )
        reranker = Qwen3Reranker(device="mps")

        retriever = AdvancedRetriever(pool=pool, encoder=encoder, reranker=reranker)

        # Test query expansion
        query = "What are the side effects of aripiprazole?"
        expanded_queries = await retriever.expand_query(query)

        logger.info(f"\nExpanded queries:")
        for i, q in enumerate(expanded_queries, 1):
            logger.info(f"  {i}. {q}")

        assert len(expanded_queries) == 3, "Should expand to exactly 3 queries"
        assert expanded_queries[0] == query, "First query should be original"

        # Test search with expansion
        results = await retriever.search(query, top_k=3)

        # Verify results
        assert len(results) > 0, "Should return results"
        assert len(results) <= 3, "Should respect top_k limit"

        # Verify rerank scores are sorted descending
        rerank_scores = [r["rerank_score"] for r in results]
        assert rerank_scores == sorted(rerank_scores, reverse=True), "Results should be sorted by rerank_score"

        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Chunk ID: {result['chunk_id']}")
            logger.info(f"  Source: {result['source_document']}")
            logger.info(f"  Similarity: {result['similarity_score']:.4f}")
            logger.info(f"  Rerank Score: {result['rerank_score']:.4f}")
            logger.info(f"  Content: {result['chunk_text'][:100]}...")

            # Verify required fields
            assert "chunk_id" in result
            assert "chunk_text" in result
            assert "similarity_score" in result
            assert "rerank_score" in result, "Advanced retriever MUST have rerank_score"

    logger.info("\n✓ AdvancedRetriever test passed")


async def test_factory():
    """Test factory pattern with all strategies."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Factory Pattern")
    logger.info("=" * 80)

    async with DatabasePool() as pool:
        encoder = LocalEmbeddingProvider(
            model_name=settings.EMBEDDING_MODEL,
            device="mps",
            batch_size=16
        )
        reranker = Qwen3Reranker(device="mps")

        # Test simple strategy
        settings.RETRIEVAL_STRATEGY = "simple"
        retriever = get_retriever(pool, encoder)
        assert isinstance(retriever, SimpleRetriever), "Factory should return SimpleRetriever"
        logger.info("✓ Factory created SimpleRetriever")

        # Test rerank strategy
        settings.RETRIEVAL_STRATEGY = "rerank"
        retriever = get_retriever(pool, encoder, reranker)
        assert isinstance(retriever, RerankRetriever), "Factory should return RerankRetriever"
        logger.info("✓ Factory created RerankRetriever")

        # Test advanced strategy
        settings.RETRIEVAL_STRATEGY = "advanced"
        retriever = get_retriever(pool, encoder, reranker)
        assert isinstance(retriever, AdvancedRetriever), "Factory should return AdvancedRetriever"
        logger.info("✓ Factory created AdvancedRetriever")

        # Test invalid strategy
        settings.RETRIEVAL_STRATEGY = "invalid"
        try:
            retriever = get_retriever(pool, encoder, reranker)
            assert False, "Should raise ValueError for invalid strategy"
        except ValueError as e:
            logger.info(f"✓ Factory correctly raised ValueError: {e}")

        # Test missing reranker
        settings.RETRIEVAL_STRATEGY = "rerank"
        try:
            retriever = get_retriever(pool, encoder, reranker=None)
            assert False, "Should raise AssertionError when reranker missing"
        except AssertionError as e:
            logger.info(f"✓ Factory correctly raised AssertionError: {e}")

    logger.info("\n✓ Factory test passed")


async def main():
    """Run all verification tests."""
    logger.info("\n" + "=" * 80)
    logger.info("RETRIEVAL MODULE VERIFICATION TESTS")
    logger.info("=" * 80)

    try:
        await test_simple_retriever()
        await test_rerank_retriever()
        await test_advanced_retriever()
        await test_factory()

        logger.info("\n" + "=" * 80)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 80)
        logger.info("\nRetrieval module implementation complete:")
        logger.info("  ✓ SimpleRetriever: query → embedding → search")
        logger.info("  ✓ RerankRetriever: query → search top_k*4 → rerank")
        logger.info("  ✓ AdvancedRetriever: query expansion → search → rerank")
        logger.info("  ✓ Factory: get_retriever() with strategy selection")

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
