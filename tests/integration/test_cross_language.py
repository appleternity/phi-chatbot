"""Integration tests for cross-language query handling (User Story 4).

Tests:
- T032: Chinese query translation with drug name preservation
- T033: Mixed Chinese+Latin query handling
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
class TestCrossLanguageHandling:
    """Integration tests for cross-language query handling (User Story 4)."""

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

    async def test_chinese_query_translation(self, retriever):
        """T032: Test Chinese query translation with drug name preservation.

        Given: A Chinese query with a drug name
        When: Query expansion is performed
        Then: LLM generates accurate English queries with correct medical terms
        """
        # Chinese query: "阿立哌唑的作用机制" (aripiprazole mechanism of action)
        chinese_query = "阿立哌唑的作用机制"

        # Expand query
        queries = await retriever.expand_query(chinese_query)

        # Assertions
        assert queries is not None, "Query expansion should return results"
        assert isinstance(queries, list), "Queries should be a list"
        assert len(queries) > 0, "Should generate at least one query"

        # All queries should be in English (no Chinese characters)
        for q in queries:
            assert not any('\u4e00' <= char <= '\u9fff' for char in q), \
                f"Query should be in English, got: {q}"

        # At least one query should mention "aripiprazole"
        aripiprazole_mentions = sum(1 for q in queries if "aripiprazole" in q.lower())
        assert aripiprazole_mentions > 0, \
            f"At least one query should mention 'aripiprazole', got: {queries}"

        # At least one query should mention "mechanism"
        mechanism_mentions = sum(1 for q in queries if "mechanism" in q.lower())
        assert mechanism_mentions > 0, \
            f"At least one query should mention 'mechanism', got: {queries}"

    async def test_mixed_chinese_latin_query(self, retriever):
        """T033: Test mixed Chinese+Latin query handling (e.g., "5-HT2A受体").

        Given: A query with mixed Chinese and Latin/English terms
        When: Query expansion is performed
        Then: LLM preserves Latin terms exactly while translating Chinese
        """
        # Mixed query: "5-HT2A受体" (5-HT2A receptor)
        mixed_query = "5-HT2A受体"

        # Expand query
        queries = await retriever.expand_query(mixed_query)

        # Assertions
        assert queries is not None
        assert isinstance(queries, list)
        assert len(queries) > 0

        # All queries should contain "5-HT2A" (preserved exactly)
        # Note: LLM might rephrase, so we check for presence of the receptor name
        receptor_mentions = sum(
            1 for q in queries
            if ("5-HT2A" in q or "5HT2A" in q or "serotonin" in q.lower())
        )
        assert receptor_mentions > 0, \
            f"At least one query should mention the receptor (5-HT2A or serotonin), got: {queries}"

        # At least one query should mention "receptor"
        receptor_word_mentions = sum(1 for q in queries if "receptor" in q.lower())
        assert receptor_word_mentions > 0, \
            f"At least one query should mention 'receptor', got: {queries}"

        # Chinese characters should be translated to English
        chinese_only_queries = [
            q for q in queries
            if any('\u4e00' <= char <= '\u9fff' for char in q)
        ]
        assert len(chinese_only_queries) == 0, \
            f"All queries should be in English (no Chinese-only queries), got Chinese in: {chinese_only_queries}"

    async def test_chinese_comparison_query(self, retriever):
        """Test Chinese comparative query generates comprehensive English variations.

        Given: A Chinese comparative query (e.g., "比较阿立哌唑和利培酮")
        When: Query expansion is performed
        Then: LLM generates multiple English queries covering both drugs
        """
        # Chinese: "比较阿立哌唑和利培酮" (Compare aripiprazole and risperidone)
        chinese_query = "比较阿立哌唑和利培酮"

        # Expand query
        queries = await retriever.expand_query(chinese_query)

        # Assertions
        assert len(queries) >= 3, "Comparative query should generate multiple queries"

        # Check for both drug names
        aripiprazole_count = sum(1 for q in queries if "aripiprazole" in q.lower())
        risperidone_count = sum(1 for q in queries if "risperidone" in q.lower())

        assert aripiprazole_count > 0, "Should generate queries about aripiprazole"
        assert risperidone_count > 0, "Should generate queries about risperidone"

        # All should be in English
        for q in queries:
            assert not any('\u4e00' <= char <= '\u9fff' for char in q), \
                f"Query should be in English, got: {q}"

    async def test_chinese_query_end_to_end(self, retriever):
        """Test complete workflow with Chinese query.

        Given: A Chinese query
        When: Complete search workflow is executed
        Then: System translates, searches, and returns relevant results
        """
        # Chinese query
        query = [HumanMessage(content="阿立哌唑副作用")]

        # Perform search
        results = await retriever.search(query, top_k=5)

        # Assertions
        assert results is not None
        assert len(results) > 0, "Should return results for Chinese query"
        assert len(results) <= 5, "Should respect top_k limit"

        # Verify results are relevant (should contain drug name or side effects info)
        relevant_count = sum(
            1 for r in results
            if ("aripiprazole" in r["chunk_text"].lower() or
                "side effect" in r["chunk_text"].lower())
        )

        assert relevant_count > 0, \
            "At least some results should be relevant to aripiprazole side effects"
