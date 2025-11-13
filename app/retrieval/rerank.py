"""Rerank retrieval strategy: query → search → rerank → results.

Two-stage retrieval for improved relevance.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from app.db.connection import DatabasePool
from app.retrieval.utils import extract_retrieval_query
from app.embeddings import EmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker

logger = logging.getLogger(__name__)


class RerankRetriever:
    """Rerank retrieval: embedding + pgvector + reranker.

    Process:
        1. Generate query embedding
        2. pgvector search for top_k * 4 candidates
        3. Rerank candidates with Qwen3-Reranker
        4. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding provider (local/cloud)
        reranker: Qwen3-Reranker for scoring
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: EmbeddingProvider,
        reranker: Qwen3Reranker,
        table_name: str = "vector_chunks",
    ):
        """Initialize rerank retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            reranker: Initialized reranker model
            table_name: Table name (default: "vector_chunks")
        """
        self.pool = pool
        self.encoder = encoder
        self.reranker = reranker
        self.table_name = table_name

        logger.info(f"RerankRetriever initialized (table={table_name}, two-stage retrieval)")

    async def search(
        self,
        query: List[BaseMessage],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search with reranking for improved relevance.

        Args:
            query: List of conversation messages.
                   For RerankRetriever, only the last human message is used (max_history=1).
                   The reranker provides semantic richness, so no extra history needed.
            top_k: Number of final results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries sorted by rerank_score (highest first)
        """
        # Extract query string from last human message
        query_str = extract_retrieval_query(query, max_history=1)

        # Validate
        assert query_str and query_str.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Rerank search: query='{query_str[:50]}...', top_k={top_k}")

        # Stage 1: Retrieve candidates (4x oversampling)
        candidate_count = top_k * 4

        # Generate embedding
        query_embedding = self.encoder.encode(query_str).tolist()

        # Build SQL query for candidates
        sql, params = self._build_query(query_embedding, candidate_count, filters)

        # Execute search
        candidates = await self.pool.fetch(sql, *params)

        if not candidates:
            logger.warning("No candidates found")
            return []

        logger.info(f"Retrieved {len(candidates)} candidates for reranking")

        # Stage 2: Rerank candidates
        candidate_texts = [row["chunk_text"] for row in candidates]
        rerank_scores = self.reranker.rerank(query_str, candidate_texts)

        # Combine scores with candidates
        results_with_scores = []
        for row, score in zip(candidates, rerank_scores):
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
            f"Reranked {len(candidates)} → {len(final_results)} results "
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
        """Build SQL query (same as SimpleRetriever)."""
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
