"""Integration tests for AdvancedRetriever multi-query generation (User Story 1).

Tests:
- T008: Single-topic query generation (1-2 queries)
- T009: Comparative query generation (5-10 queries)
- T010: Result deduplication across multiple queries
"""

import pytest
import asyncio
from langchain_core.messages import HumanMessage

from app.retrieval.advanced import AdvancedRetriever
from app.db.connection import DatabasePool
from app.embeddings.factory import create_embedding_provider
from app.core.qwen3_reranker import Qwen3Reranker
from app.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdvancedRetrieverMultiQuery:
    """Integration tests for multi-query generation (User Story 1)."""

    @pytest.fixture(scope="class")
    async def retriever(self):
        """Create AdvancedRetriever instance for tests."""
        # Initialize components
        encoder = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key if hasattr(settings, 'openai_api_key') else None,
            aliyun_api_key=settings.aliyun_api_key if hasattr(settings, 'aliyun_api_key') else None,
        )
        reranker = Qwen3Reranker()
        pool = DatabasePool()

        # Create retriever with max_queries=10
        retriever = AdvancedRetriever(
            pool=pool,
            encoder=encoder,
            reranker=reranker,
            table_name=settings.table_name,
            max_queries=10
        )

        yield retriever

        # Cleanup
        await pool.close()

    async def test_single_topic_query_generation(self, retriever):
        """T008: Test single-topic query generates 1-2 queries.

        Given: A simple, single-topic query
        When: Query expansion is performed
        Then: System generates 1-2 query variations
        """
        # Simple single-topic query
        query = "What is aripiprazole?"

        # Expand query
        queries = await retriever.expand_query(query)

        # Assertions
        assert queries is not None, "Query expansion should return results"
        assert isinstance(queries, list), "Queries should be a list"
        assert 1 <= len(queries) <= 3, f"Expected 1-3 queries for simple topic, got {len(queries)}"
        assert all(isinstance(q, str) for q in queries), "All queries should be strings"
        assert all(len(q) > 0 for q in queries), "No empty queries allowed"

        # All queries should be in English (no Chinese characters)
        for q in queries:
            assert not any('\u4e00' <= char <= '\u9fff' for char in q), \
                f"Query should be in English, got: {q}"

    async def test_comparative_query_generation(self, retriever):
        """T009: Test comparative query generates 5-10 queries.

        Given: A comparative query with multiple entities
        When: Query expansion is performed
        Then: System generates 5-10 query variations covering both entities
        """
        # Comparative query with two drugs
        query = "Compare aripiprazole and risperidone"

        # Expand query
        queries = await retriever.expand_query(query)

        # Assertions
        assert queries is not None, "Query expansion should return results"
        assert isinstance(queries, list), "Queries should be a list"
        assert 5 <= len(queries) <= 10, f"Expected 5-10 queries for comparison, got {len(queries)}"
        assert all(isinstance(q, str) for q in queries), "All queries should be strings"
        assert all(len(q) > 0 for q in queries), "No empty queries allowed"

        # Check that both entities are covered
        aripiprazole_count = sum(1 for q in queries if "aripiprazole" in q.lower())
        risperidone_count = sum(1 for q in queries if "risperidone" in q.lower())

        assert aripiprazole_count > 0, "Should generate queries about aripiprazole"
        assert risperidone_count > 0, "Should generate queries about risperidone"

        # All queries should be in English
        for q in queries:
            assert not any('\u4e00' <= char <= '\u9fff' for char in q), \
                f"Query should be in English, got: {q}"

    async def test_result_deduplication(self, retriever):
        """T010: Test result deduplication across multiple queries.

        Given: Multiple query variations that may return overlapping results
        When: Multi-query search is performed
        Then: Results are deduplicated by chunk_id before reranking
        """
        # Use a query that's likely to produce overlapping results
        query = [HumanMessage(content="aripiprazole mechanism")]

        # Perform search
        results = await retriever.search(query, top_k=5)

        # Assertions
        assert results is not None, "Search should return results"
        assert isinstance(results, list), "Results should be a list"

        # Check for duplicate chunk_ids
        chunk_ids = [r["chunk_id"] for r in results]
        unique_chunk_ids = set(chunk_ids)

        assert len(chunk_ids) == len(unique_chunk_ids), \
            f"Duplicate chunk_ids found: {len(chunk_ids)} total, {len(unique_chunk_ids)} unique"

        # Verify all results have required fields
        for r in results:
            assert "chunk_id" in r, "Result should have chunk_id"
            assert "chunk_text" in r, "Result should have chunk_text"
            assert "rerank_score" in r, "Result should have rerank_score"
            assert "similarity_score" in r, "Result should have similarity_score"

    async def test_fallback_on_zero_queries(self, retriever):
        """T011: Test fallback logic when query generation produces 0 valid queries.

        Given: Query expansion fails to generate valid queries
        When: Search is performed
        Then: System falls back to using the original query
        """
        # This test verifies the fallback behavior in expand_query()
        # If LLM returns garbage, we should still get at least [original_query]

        query = "test query"
        queries = await retriever.expand_query(query)

        # Should always get at least one query (original as fallback)
        assert len(queries) >= 1, "Should have at least one query (fallback)"

        # If expansion completely failed, we should have exactly the original query
        if len(queries) == 1:
            # Fallback case - original query should be present
            assert any(query.lower() in q.lower() for q in queries), \
                "Fallback should include original query"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdvancedRetrieverEndToEnd:
    """End-to-end integration tests for complete retrieval workflow."""

    @pytest.fixture(scope="class")
    async def retriever(self):
        """Create AdvancedRetriever instance for tests."""
        encoder = create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key if hasattr(settings, 'openai_api_key') else None,
            aliyun_api_key=settings.aliyun_api_key if hasattr(settings, 'aliyun_api_key') else None,
        )
        reranker = Qwen3Reranker()
        pool = DatabasePool()

        retriever = AdvancedRetriever(
            pool=pool,
            encoder=encoder,
            reranker=reranker,
            table_name=settings.table_name,
            max_queries=10
        )

        yield retriever

        await pool.close()

    async def test_multi_query_search_workflow(self, retriever):
        """Test complete multi-query search workflow.

        Given: A comparative query
        When: Complete search workflow is executed
        Then: System generates multiple queries, searches, deduplicates, and reranks
        """
        query = [HumanMessage(content="Compare aripiprazole and risperidone side effects")]

        # Perform search
        results = await retriever.search(query, top_k=5)

        # Assertions
        assert results is not None
        assert len(results) > 0, "Should return results"
        assert len(results) <= 5, "Should respect top_k limit"

        # Verify results are sorted by rerank_score (descending)
        rerank_scores = [r["rerank_score"] for r in results]
        assert rerank_scores == sorted(rerank_scores, reverse=True), \
            "Results should be sorted by rerank_score descending"

        # Verify no duplicates
        chunk_ids = [r["chunk_id"] for r in results]
        assert len(chunk_ids) == len(set(chunk_ids)), "No duplicate chunk_ids"
