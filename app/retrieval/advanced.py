"""Advanced retrieval strategy: query expansion + search + rerank.

Most sophisticated retrieval approach using LLM query expansion.
"""

import logging
from typing import List, Dict, Any, Optional

from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.agents.base import create_llm

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
        encoder: Embedding encoder
        reranker: Qwen3-Reranker for scoring
        llm: LLM for query expansion
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: Qwen3EmbeddingEncoder,
        reranker: Qwen3Reranker,
    ):
        """Initialize advanced retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker
        self.llm = create_llm(temperature=0.7)  # For creative query variations

        logger.info("AdvancedRetriever initialized (query expansion + reranking)")

    async def expand_query(self, query: str) -> List[str]:
        """Expand query into multiple variations using LLM.

        Generates 3 query variations:
        1. Original query (unchanged)
        2. More specific technical variation
        3. Broader contextual variation

        Args:
            query: Original user query

        Returns:
            List of 3 query strings
        """
        expansion_prompt = f"""You are a medical information search assistant.

Given the user's query, generate 2 additional search variations to improve retrieval:

1. A more SPECIFIC, TECHNICAL variation (using medical terminology)
2. A BROADER, CONTEXTUAL variation (considering related topics)

Original query: {query}

Respond in this format:
SPECIFIC: <your specific variation>
BROADER: <your broader variation>

Example:
User query: "What are side effects of aripiprazole?"
SPECIFIC: aripiprazole adverse reactions pharmacological effects dopamine antagonist
BROADER: atypical antipsychotic medication side effects safety profile tolerability

Now generate variations for the query above:"""

        # Generate variations
        response = self.llm.invoke([{"role": "user", "content": expansion_prompt}])
        response_text = response.content

        # Parse response
        queries = [query]  # Always include original

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('SPECIFIC:'):
                specific = line.replace('SPECIFIC:', '').strip()
                if specific:
                    queries.append(specific)
            elif line.startswith('BROADER:'):
                broader = line.replace('BROADER:', '').strip()
                if broader:
                    queries.append(broader)

        # Ensure we have exactly 3 queries
        if len(queries) < 3:
            # Fallback: duplicate original if parsing failed
            while len(queries) < 3:
                queries.append(query)

        queries = queries[:3]  # Take first 3

        logger.info(f"Expanded query into {len(queries)} variations")
        for i, q in enumerate(queries, 1):
            logger.debug(f"  {i}. {q[:80]}...")

        return queries

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with query expansion and reranking.

        Args:
            query: Search query string
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score
        """
        # Validate
        assert query and query.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Advanced search: query='{query[:50]}...', top_k={top_k}")

        # Stage 1: Expand query
        queries = await self.expand_query(query)

        # Stage 2: Search all query variations
        all_candidates = []
        seen_chunk_ids = set()

        for i, q in enumerate(queries, 1):
            # Generate embedding
            query_embedding = self.encoder.encode(q).tolist()

            # Build SQL query
            sql, params = self._build_query(query_embedding, top_k, filters)

            # Execute search
            results = await self.pool.fetch(sql, *params)

            # Deduplicate by chunk_id
            for row in results:
                chunk_id = row["chunk_id"]
                if chunk_id not in seen_chunk_ids:
                    all_candidates.append(row)
                    seen_chunk_ids.add(chunk_id)

            logger.debug(f"Query {i}: found {len(results)} results")

        if not all_candidates:
            logger.warning("No candidates found from any query variation")
            return []

        logger.info(
            f"Collected {len(all_candidates)} unique candidates "
            f"from {len(queries)} query variations"
        )

        # Stage 3: Rerank all candidates with ORIGINAL query
        candidate_texts = [row["chunk_text"] for row in all_candidates]
        rerank_scores = self.reranker.rerank(query, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(all_candidates, rerank_scores):
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
            f"Reranked {len(all_candidates)} → {len(final_results)} results "
            f"(score range: {final_results[0]['rerank_score']:.3f} - "
            f"{final_results[-1]['rerank_score']:.3f})"
        )

        return final_results

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query (same as other retrievers)."""
        sql = """
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
        FROM vector_chunks
        """

        params = [embedding]
        param_index = 2

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
