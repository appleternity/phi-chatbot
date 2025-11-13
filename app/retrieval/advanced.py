"""Advanced retrieval strategy: query expansion + search + rerank.

Most sophisticated retrieval approach using LLM query expansion.
"""

import asyncio
import logging
import numpy as np
import re
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from app.db.connection import DatabasePool
from app.retrieval.utils import extract_retrieval_query, format_conversation_context
from app.embeddings import EmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker
from app.agents.base import create_llm

from app.config import settings

logger = logging.getLogger(__name__)


class AdvancedRetriever:
    """Advanced retrieval: query expansion + multi-query search + reranking.

    Process:
        1. LLM expands query into 3 variations
        2. Search all variations in parallel
        3. Merge and deduplicate results
        4. Rerank with Qwen3-Reranker
        5. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding provider (local/cloud)
        reranker: Qwen3-Reranker for scoring
        llm: LLM for query expansion
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: EmbeddingProvider,
        reranker: Qwen3Reranker,
        table_name: str = "vector_chunks",
        max_queries: int = 10,
    ):
        """Initialize advanced retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
            table_name: Table name (default: "vector_chunks")
            max_queries: Maximum number of query variations to generate (default: 10)
                        - Simple queries: 1-2 variations
                        - Comparative queries: 5-10 variations
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker
        self.table_name = table_name
        self.max_queries = max_queries
        self.llm = create_llm(temperature=1.0, disable_streaming=True, tags=["internal-llm"])

        logger.info(
            f"AdvancedRetriever initialized "
            f"(table={table_name}, max_queries={max_queries}, query expansion + reranking)"
        )

    async def expand_query(
        self,
        query: str,
        conversation_context: Optional[str] = None
    ) -> List[str]:
        """Expand query into 1-10 diverse variations using LLM.

        Generates query variations optimized for semantic search:
        - Simple queries: 1-2 variations
        - Comparative queries: 5-10 variations
        - Complex queries: 2-10 variations based on complexity

        Strategies:
        - Entity decomposition (Drug A, Drug B separately)
        - Aspect coverage (mechanism, side effects, efficacy)
        - Perspective variation (patient, clinician, pharmacist)

        IMPORTANT: All variations are generated in English, even if the input
        query is in Chinese, to match the English medical knowledge base.

        Args:
            query: User query (may be in Chinese or English)
            conversation_context: Optional conversation history for better context

        Returns:
            List of 1-10 query variation strings (all in English)
        """
        # Build expansion prompt with optional conversation context
        context_section = ""
        if conversation_context:
            context_section = f"""
Conversation History (for context only):
{conversation_context}

"""

        expansion_prompt = f"""You are a medical search query assistant. Generate up to {self.max_queries} diverse English queries.

{context_section}User Query: {query}

Requirements:
1. Output ONLY queries, one per line (no numbering, no prefixes)
2. All queries MUST be in English (translate if needed)
   - For Chinese queries: Translate medical terms accurately (阿立哌唑 → aripiprazole, 利培酮 → risperidone)
   - For mixed Chinese+Latin: Preserve Latin/English terms exactly (5-HT2A, D2, NMDA) while translating Chinese
   - Preserve drug names, receptor names, and scientific terminology
3. Generate 2-{self.max_queries} queries depending on complexity:
   - Simple questions: 2-3 queries
   - Comparisons: 5-{self.max_queries} queries (cover both entities)
   - Complex topics: Adjust based on number of distinct aspects
4. Diversity strategies:
   - Entity decomposition (Drug A, Drug B separately)
   - Aspect coverage (mechanism, side effects, efficacy)
   - Perspective variation (patient, clinician, pharmacist)

Example input: "Compare aripiprazole and risperidone"
Example output:
aripiprazole mechanism of action
risperidone mechanism of action
aripiprazole side effects
risperidone side effects
aripiprazole vs risperidone efficacy
atypical antipsychotics comparison

Example input (Chinese): "阿立哌唑的作用机制"
Example output:
aripiprazole mechanism of action
aripiprazole pharmacology
how aripiprazole works

Example input (Mixed Chinese+Latin): "5-HT2A受体"
Example output:
5-HT2A receptor
serotonin 5-HT2A receptor
5-HT2A receptor function

Generate queries:"""

        # Generate variations with LLM
        response = self.llm.invoke([{"role": "user", "content": expansion_prompt}])
        response_text = response.content

        # Parse response - simple newline split
        raw_queries = []
        for line in response_text.split('\n'):
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # Remove any numbering (e.g., "1. query" -> "query", "10. query" -> "query", "1) query" -> "query")
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            # Add non-empty queries
            if line:
                raw_queries.append(line)

        # Validation Step 1: Filter malformed queries
        valid_queries = self._validate_queries(raw_queries)

        # Validation Step 2: Limit to max_queries
        queries = valid_queries[:self.max_queries]

        # Fallback if no valid queries generated
        if not queries:
            logger.warning(
                f"Query expansion produced 0 valid queries after validation. "
                f"Using original query as fallback."
            )
            queries = [query]

        # Structured logging with metrics
        filtered_count = len(raw_queries) - len(valid_queries)

        logger.info(
            f"Query expansion completed: raw_count={len(raw_queries)}, "
            f"filtered={filtered_count}, final_count={len(queries)}"
        )
        for i, q in enumerate(queries, 1):
            logger.debug(f"  Query {i}: {q}")

        return queries

    async def search(
        self,
        query: List[BaseMessage],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with query expansion and reranking.

        Args:
            query: List of conversation messages.
                   For AdvancedRetriever, uses last 5 messages to provide rich context
                   for LLM-based query expansion. This enables better understanding of
                   follow-up questions and conversational context.
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score
        """
        # Extract query string from last human message
        query_str = extract_retrieval_query(query, max_history=1)

        # Format last 5 messages for query expansion context (richer understanding)
        # Exclude the last message to avoid duplication with query_str
        if len(query) > 1:
            conversation_context = format_conversation_context(
                query,
                max_messages=5,
                exclude_last_n=1  # EXPLICIT: Don't duplicate the query message!
            )
        else:
            conversation_context = None

        # Validate
        assert query_str and query_str.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Advanced search: query='{query_str[:50]}...', top_k={top_k}")
        if conversation_context:
            logger.debug(f"Using conversation context with {len(conversation_context)} chars")

        # Stage 1: Expand query with conversation context
        queries = await self.expand_query(query_str, conversation_context)
        logger.info(f"Expanded to {len(queries)} query variations for search. They are:{"\n".join(queries)}")


        # Stage 1.5: Batch encode all queries at once (PERFORMANCE OPTIMIZATION)
        # Instead of encoding queries one-by-one in _vector_search (10 calls with batch_size=1),
        # we encode all queries together (1 call with batch_size=10)
        # This is 5-10x faster for both local GPU and cloud API providers
        embeddings_raw = self.encoder.encode(queries)  # Batch encoding!

        # Convert to list of lists (handle both single ndarray and list of ndarrays)
        if isinstance(embeddings_raw, np.ndarray):
            # Single query case (shouldn't happen here, but defensive)
            embeddings = [embeddings_raw.tolist()]
        else:
            # Multiple queries (expected)
            embeddings = [emb.tolist() for emb in embeddings_raw]

        logger.info(f"Batch encoded {len(queries)} queries")

        # Stage 2: Search all query variations in parallel (vector + optional keyword)
        # Vector search with pre-computed embeddings
        vector_tasks = [
            self._vector_search(queries[i], top_k, embeddings[i], filters)
            for i in range(len(queries))
        ]

        # Keyword search (if enabled)
        if settings.enable_keyword_search:
            logger.info(f"Keyword search enabled: will search {len(queries)} queries with top_k_per_query={top_k}")
            keyword_tasks = [self._keyword_search(queries, top_k_per_query=top_k)]
        else:
            logger.debug("Keyword search disabled (enable_keyword_search=False)")
            keyword_tasks = []

        # Execute all searches in parallel
        all_tasks = vector_tasks + keyword_tasks
        search_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Separate vector and keyword results
        vector_results = search_results[:len(vector_tasks)]
        keyword_results = search_results[len(vector_tasks):] if keyword_tasks else []

        # Merge vector results
        vector_candidates = []
        for i, result in enumerate(vector_results, 1):
            if isinstance(result, Exception):
                logger.error(f"Vector query {i} failed with error: {result}")
                continue
            vector_candidates.extend(result)

        # Merge keyword results (if any)
        keyword_candidates = []
        if keyword_results:
            for result in keyword_results:
                if isinstance(result, Exception):
                    logger.error(f"Keyword search failed with error: {result}")
                    continue
                keyword_candidates.extend(result)

        # Combine vector and keyword results
        all_candidates = vector_candidates + keyword_candidates

        # Deduplicate using _merge_results
        unique_candidates = self._merge_results(all_candidates)

        if not unique_candidates:
            logger.warning("No candidates found from any query variation")
            return []

        logger.info(
            f"Search completed: vector={len(vector_candidates)}, keyword={len(keyword_candidates)}, "
            f"unique={len(unique_candidates)}"
        )

        # Stage 3: Rerank all candidates with ORIGINAL query
        candidate_texts = [row["chunk_text"] for row in unique_candidates]
        rerank_scores = self.reranker.rerank(query_str, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(unique_candidates, rerank_scores):
            result = {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
                "rerank_score": float(score),
            }
            results_with_scores.append(result)

        # Sort by rerank_score (descending)
        results_with_scores.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Take top_k
        final_results = results_with_scores[:top_k]

        logger.info(
            f"Reranking completed: {len(unique_candidates)} candidates → {len(final_results)} results "
            f"(top score: {final_results[0]['rerank_score']:.3f}, "
            f"bottom score: {final_results[-1]['rerank_score']:.3f})"
        )

        return final_results

    def _validate_queries(self, queries: List[str]) -> List[str]:
        """Filter out malformed queries (empty, punctuation-only).

        Args:
            queries: List of raw query strings

        Returns:
            List of valid queries with malformed ones removed
        """
        valid = []
        for q in queries:
            # Check if empty or whitespace-only
            if not q or not q.strip():
                continue

            # Check if query contains at least one alphanumeric character
            if not any(c.isalnum() for c in q):
                logger.debug(f"Filtered malformed query (no alphanumeric): '{q}'")
                continue

            valid.append(q)

        return valid

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute vector similarity search for a single query with pre-computed embedding.

        Args:
            query: Query string (used for logging only)
            top_k: Number of results per query
            query_embedding: Pre-computed query embedding (from batch encoding)
            filters: Optional metadata filters

        Returns:
            List of result dictionaries with similarity scores
        """
        try:
            # Use pre-computed embedding (batch encoded in search() method)

            # Build SQL query
            sql, params = self._build_query(query_embedding, top_k, filters)

            # Execute search
            results = await self.pool.fetch(sql, *params)

            # Convert to list of dicts
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Vector search failed for query '{query[:50]}...': {e}")
            raise

    async def _keyword_search(
        self,
        queries: List[str],
        top_k_per_query: int = 5
    ) -> List[Dict[str, Any]]:
        """Execute pg_trgm keyword search for all queries in parallel.

        Uses PostgreSQL pg_trgm extension for trigram-based similarity matching.
        This is particularly effective for drug names and medical terminology.

        Note: Uses custom similarity threshold from settings (default: 0.1) instead of
        the default pg_trgm threshold (0.3) which is too high for short queries against
        long medical documents.

        With multiple queries, this returns up to (top_k_per_query × len(queries)) results
        before deduplication. For example, with 10 queries and top_k=5, you may get up to
        50 results. The _merge_results() method deduplicates by chunk_id to prevent exact
        duplicates in the final candidate set.

        Args:
            queries: List of query strings
            top_k_per_query: Number of results to retrieve per query (default: 5)

        Returns:
            Combined list of result dictionaries with similarity_score
        """
        try:
            threshold = settings.keyword_similarity_threshold
            logger.info(
                f"Starting keyword search for {len(queries)} queries "
                f"(top_k_per_query={top_k_per_query}, threshold={threshold})"
            )

            # Debug: Log all queries being searched
            for i, q in enumerate(queries, 1):
                logger.debug(f"  Keyword query {i}: '{q}'")

            # Build keyword search tasks for all queries
            # Use similarity() function with custom threshold instead of % operator
            # to avoid pg_trgm's default 0.3 threshold which is too high
            keyword_tasks = []
            for q in queries:
                sql = f"""
                SELECT
                    chunk_id,
                    chunk_text,
                    source_document,
                    chapter_title,
                    section_title,
                    subsection_title,
                    summary,
                    token_count,
                    similarity(chunk_text, $1) AS similarity_score
                FROM "{self.table_name}"
                WHERE similarity(chunk_text, $1) > $2
                ORDER BY similarity_score DESC
                LIMIT $3
                """
                params = [q, threshold, top_k_per_query]
                task = self.pool.fetch(sql, *params)
                keyword_tasks.append(task)

            # Execute all keyword searches in parallel
            keyword_results = await asyncio.gather(*keyword_tasks, return_exceptions=True)

            # Merge results with detailed logging
            all_results = []
            for i, result in enumerate(keyword_results, 1):
                if isinstance(result, Exception):
                    logger.error(f"Keyword query {i} ('{queries[i-1]}') failed: {result}")
                    continue

                result_list = [dict(row) for row in result]
                logger.debug(
                    f"  Keyword query {i} ('{queries[i-1][:50]}...'): {len(result_list)} results"
                )

                # Log top result score if available
                if result_list:
                    top_score = result_list[0].get('similarity_score', 0)
                    logger.debug(f"    Top score: {top_score:.4f}")

                all_results.extend(result_list)

            logger.info(
                f"Keyword search completed: {len(all_results)} total results from {len(queries)} queries "
                f"(avg {len(all_results)/len(queries):.1f} results/query)"
            )

            return all_results

        except Exception as e:
            # Graceful degradation: log error and return empty results
            logger.warning(
                f"Keyword search failed (pg_trgm extension may be missing): {e}. "
                f"Falling back to vector-only search."
            )
            return []

    def _merge_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge and deduplicate results by chunk_id.

        Keeps first occurrence of each chunk_id (highest similarity from any query).

        Args:
            results: List of result dictionaries from multiple queries

        Returns:
            Deduplicated list of results
        """
        seen = {}
        for result in results:
            chunk_id = result["chunk_id"]
            if chunk_id not in seen:
                seen[chunk_id] = result

        deduplicated = list(seen.values())

        logger.debug(
            f"Deduplication: {len(results)} total results → "
            f"{len(deduplicated)} unique chunks "
            f"({len(results) - len(deduplicated)} duplicates removed)"
        )

        return deduplicated

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query (same as other retrievers)."""
        sql = f"""
        SELECT
            chunk_id,
            chunk_text,
            source_document,
            chapter_title,
            section_title,
            subsection_title,
            summary,
            token_count,
            1 - (embedding <=> $1) AS similarity_score
        FROM "{self.table_name}"
        """

        params = [embedding]
        param_index = 2

        # NOTE: what is filters here?
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
