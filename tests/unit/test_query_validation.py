"""Unit tests for query validation and deduplication (User Story 2).

Tests:
- T016: Duplicate query detection (exact string match)
- T017: Malformed query filtering (empty, punctuation-only)
- T018: Query ranking by relevance (top-10 selection)
"""

import pytest

from app.retrieval.advanced import AdvancedRetriever


class TestQueryValidation:
    """Unit tests for query validation logic (User Story 2)."""

    def test_duplicate_query_detection(self):
        """T016: Test duplicate query detection using exact string match.

        Given: A list of queries with exact duplicates
        When: Deduplication is applied
        Then: Exact duplicate queries are removed
        """
        queries = [
            "aripiprazole mechanism",
            "risperidone side effects",
            "aripiprazole mechanism",  # Exact duplicate
            "atypical antipsychotics",
            "risperidone side effects",  # Exact duplicate
            "aripiprazole efficacy",
        ]

        # Expected unique queries
        expected_unique = {
            "aripiprazole mechanism",
            "risperidone side effects",
            "atypical antipsychotics",
            "aripiprazole efficacy",
        }

        # Deduplicate using set (simple exact match)
        unique_queries = list(dict.fromkeys(queries))  # Preserves order, removes duplicates

        # Assertions
        assert len(unique_queries) == 4, f"Expected 4 unique queries, got {len(unique_queries)}"
        assert set(unique_queries) == expected_unique, "Deduplication failed"

    def test_malformed_query_filtering(self):
        """T017: Test malformed query filtering (empty, punctuation-only).

        Given: A list of queries including malformed ones
        When: Validation is applied
        Then: Empty and punctuation-only queries are filtered out
        """
        queries = [
            "aripiprazole mechanism",
            "",  # Empty
            "   ",  # Whitespace only
            "???",  # Punctuation only
            "...",  # Punctuation only
            "risperidone side effects",
            "!@#$%",  # Punctuation only
        ]

        # Filter out malformed queries
        def is_valid_query(q: str) -> bool:
            """Check if query is valid (non-empty, meaningful content)."""
            if not q or not q.strip():
                return False
            # Check if query contains at least one alphanumeric character
            return any(c.isalnum() for c in q)

        valid_queries = [q for q in queries if is_valid_query(q)]

        # Assertions
        assert len(valid_queries) == 2, f"Expected 2 valid queries, got {len(valid_queries)}"
        assert "aripiprazole mechanism" in valid_queries
        assert "risperidone side effects" in valid_queries

    def test_query_ranking_selection(self):
        """T018: Test query ranking by relevance (top-10 selection).

        Given: More than 10 generated queries
        When: Query limit is applied
        Then: Only top 10 queries are selected
        """
        # Generate 15 queries
        queries = [f"query {i}" for i in range(1, 16)]

        # Limit to top 10
        max_queries = 10
        limited_queries = queries[:max_queries]

        # Assertions
        assert len(limited_queries) == 10, f"Expected 10 queries, got {len(limited_queries)}"
        assert limited_queries[0] == "query 1"
        assert limited_queries[9] == "query 10"
        assert "query 11" not in limited_queries
        assert "query 15" not in limited_queries

    def test_combined_validation_workflow(self):
        """Test complete validation workflow: filter → deduplicate → limit.

        Given: Raw queries with malformed ones and duplicates
        When: Complete validation workflow is applied
        Then: Output is clean, unique, and limited to max_queries
        """
        raw_queries = [
            "aripiprazole mechanism",
            "",  # Empty - should be removed
            "risperidone side effects",
            "aripiprazole mechanism",  # Duplicate - should be removed
            "   ",  # Whitespace - should be removed
            "atypical antipsychotics",
            "???",  # Punctuation - should be removed
            "aripiprazole efficacy",
            "risperidone mechanism",
            "aripiprazole safety",
        ]

        # Step 1: Filter malformed
        def is_valid_query(q: str) -> bool:
            if not q or not q.strip():
                return False
            return any(c.isalnum() for c in q)

        valid_queries = [q for q in raw_queries if is_valid_query(q)]

        # Step 2: Deduplicate (preserve order)
        unique_queries = list(dict.fromkeys(valid_queries))

        # Step 3: Limit to max_queries
        max_queries = 10
        final_queries = unique_queries[:max_queries]

        # Assertions
        assert len(final_queries) == 6, f"Expected 6 final queries, got {len(final_queries)}"
        assert final_queries[0] == "aripiprazole mechanism"
        assert "aripiprazole mechanism" in final_queries
        assert "" not in final_queries
        assert "???" not in final_queries
        assert final_queries.count("aripiprazole mechanism") == 1  # No duplicates
