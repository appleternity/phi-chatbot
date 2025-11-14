"""Integration tests for hybrid keyword+vector search (User Story 3).

Tests:
- T023: Keyword-only search using pg_trgm
- T024: Hybrid search (vector + keyword) result merging
- T025: Keyword search with specific drug names
"""

import pytest
from langchain_core.messages import HumanMessage

from app.retrieval.advanced import AdvancedRetriever
from app.db.connection import DatabasePool
from app.embeddings.factory import create_embedding_provider
from app.core.qwen3_reranker import Qwen3Reranker
from app.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.enable_keyword_search,
    reason="Keyword search disabled (ENABLE_KEYWORD_SEARCH=false)"
)
class TestKeywordSearch:
    """Integration tests for pg_trgm keyword search (User Story 3)."""

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

    async def test_keyword_only_search(self, retriever):
        """T023: Test keyword-only search using pg_trgm.

        Given: A query with a specific drug name
        When: Keyword search is performed
        Then: Documents containing the drug name are retrieved via trigram matching
        """
        query = "aripiprazole"

        # Execute keyword search directly
        keyword_results = await retriever._keyword_search([query], top_k_per_query=10)

        # Assertions
        assert keyword_results is not None, "Keyword search should return results"
        assert isinstance(keyword_results, list), "Results should be a list"
        assert len(keyword_results) > 0, "Should find results for 'aripiprazole'"

        # Verify all results have similarity_score field
        for r in keyword_results:
            assert "similarity_score" in r, "Result should have similarity_score"
            assert r["similarity_score"] > 0, "Similarity score should be positive"
            assert "chunk_text" in r, "Result should have chunk_text"

            # Verify the drug name appears in the chunk text (case-insensitive)
            chunk_text_lower = r["chunk_text"].lower()
            assert "aripiprazole" in chunk_text_lower, \
                "Result should contain the drug name 'aripiprazole'"

    async def test_hybrid_search_result_merging(self, retriever):
        """T024: Test hybrid search (vector + keyword) result merging.

        Given: A query that triggers both vector and keyword search
        When: Hybrid search is performed
        Then: Results from both searches are merged and deduplicated correctly
        """
        query = [HumanMessage(content="aripiprazole mechanism of action")]

        # Perform complete hybrid search
        results = await retriever.search(query, top_k=5)

        # Assertions
        assert results is not None
        assert isinstance(results, list)
        assert len(results) > 0, "Hybrid search should return results"
        assert len(results) <= 5, "Should respect top_k limit"

        # Verify no duplicate chunk_ids
        chunk_ids = [r["chunk_id"] for r in results]
        unique_chunk_ids = set(chunk_ids)
        assert len(chunk_ids) == len(unique_chunk_ids), \
            f"Duplicate chunk_ids found in hybrid results: {len(chunk_ids)} total, {len(unique_chunk_ids)} unique"

        # All results should have rerank_score (final ranking after merge)
        for r in results:
            assert "rerank_score" in r, "Result should have rerank_score"
            assert r["rerank_score"] > 0, "Rerank score should be positive"

        # Results should be sorted by rerank_score (descending)
        rerank_scores = [r["rerank_score"] for r in results]
        assert rerank_scores == sorted(rerank_scores, reverse=True), \
            "Results should be sorted by rerank_score descending"

    async def test_keyword_search_with_drug_names(self, retriever):
        """T025: Test keyword search with specific drug names.

        Given: Queries with different drug names
        When: Keyword search is performed
        Then: Each drug name retrieves its specific documents
        """
        drug_queries = [
            "aripiprazole",
            "risperidone",
            "olanzapine",
        ]

        for drug_name in drug_queries:
            # Execute keyword search
            keyword_results = await retriever._keyword_search([drug_name], top_k_per_query=5)

            # Assertions
            assert len(keyword_results) > 0, f"Should find results for '{drug_name}'"

            # Verify drug name appears in ALL results
            for r in keyword_results:
                chunk_text_lower = r["chunk_text"].lower()
                assert drug_name.lower() in chunk_text_lower, \
                    f"Result should contain '{drug_name}'"

                # Verify similarity_score exists and is positive
                assert "similarity_score" in r
                assert r["similarity_score"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestHybridSearchGracefulDegradation:
    """Test graceful degradation when pg_trgm extension is missing."""

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

    @pytest.mark.skipif(
        settings.enable_keyword_search,
        reason="Keyword search enabled, cannot test degradation"
    )
    async def test_vector_only_fallback(self, retriever):
        """Test that system works with vector-only search when keyword search is disabled.

        Given: Keyword search is disabled (enable_keyword_search=false)
        When: Search is performed
        Then: System falls back to vector-only search without errors
        """
        query = [HumanMessage(content="aripiprazole mechanism")]

        # Perform search (should work with vector-only)
        results = await retriever.search(query, top_k=5)

        # Assertions
        assert results is not None
        assert len(results) > 0, "Vector-only search should work"
        assert len(results) <= 5, "Should respect top_k limit"

        # Vector-only mode: similarity_score from vector search
        for r in results:
            assert "similarity_score" in r, "Should have similarity_score from vector search"
            assert "rerank_score" in r, "Should have rerank_score from reranker"
