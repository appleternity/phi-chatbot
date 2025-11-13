"""Simple retrieval strategy: query → embedding → search → results.

No reranking, fastest retrieval approach.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from app.db.connection import DatabasePool
from app.retrieval.utils import extract_retrieval_query
from app.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


class SimpleRetriever:
    """Simple retrieval: embedding + pgvector similarity search.

    Process:
        1. Generate query embedding
        2. pgvector cosine similarity search
        3. Return top_k results

    Attributes:
        pool: Database connection pool
        encoder: Embedding provider (local/cloud)
        table_name: Vector table name (supports special characters)
    """

    def __init__(
        self,
        pool: DatabasePool,
        encoder: EmbeddingProvider,
        table_name: str = "vector_chunks",
    ):
        """Initialize simple retriever.

        Args:
            pool: Initialized database pool
            encoder: Initialized embedding encoder
            table_name: Table name (default: "vector_chunks")
        """
        self.pool = pool
        self.encoder = encoder
        self.table_name = table_name

        logger.info(f"SimpleRetriever initialized (table={table_name}, no reranking)")

    async def search(
        self,
        query: List[BaseMessage],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: List of conversation messages.
                   For SimpleRetriever, only the last human message is used (max_history=1).
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"source_document": "..."})

        Returns:
            List of result dictionaries with document data and similarity scores
        """
        # Extract query string from last human message
        query_str = extract_retrieval_query(query, max_history=1)

        # Validate
        assert query_str and query_str.strip(), "Query cannot be empty"
        assert top_k > 0, f"top_k must be positive, got {top_k}"

        logger.info(f"Simple search: query='{query_str[:50]}...', top_k={top_k}")

        # Generate embedding
        query_embedding = self.encoder.encode(query_str).tolist()

        # Build SQL query
        sql, params = self._build_query(query_embedding, top_k, filters)

        # Execute search
        results = await self.pool.fetch(sql, *params)

        # Convert to dictionaries
        documents = [
            {
                "chunk_id": row["chunk_id"],
                "chunk_text": row["chunk_text"],
                "source_document": row["source_document"],
                "chapter_title": row["chapter_title"],
                "section_title": row["section_title"],
                "subsection_title": row["subsection_title"],
                "summary": row["summary"],
                "token_count": row["token_count"],
                "similarity_score": float(row["similarity_score"]),
            }
            for row in results
        ]

        logger.info(f"Found {len(documents)} results")
        return documents

    def _build_query(
        self,
        embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query with optional filters.

        Args:
            embedding: Query embedding vector (list of floats)
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            Tuple of (sql_query, parameters)
        """
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

        # Add filters
        if filters:
            where_clauses = []
            for key, value in filters.items():
                if key in ["source_document", "chapter_title"]:
                    where_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        # Add ordering and limit
        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)

        return sql, params
