"""PostgreSQL retriever with pgvector similarity search and Qwen3 reranking.

This module provides PostgreSQLRetriever, a DocumentRetriever implementation that:
- Uses pgvector extension for fast cosine similarity search (~1.5ms with HNSW index)
- Generates query embeddings using Qwen3-Embedding-0.6B (1024 dims)
- Reranks results with Qwen3-Reranker-0.6B for improved relevance
- Supports metadata filtering (source_document, chapter_title)
- Implements async connection pooling with proper lifecycle management
- Maps VectorDocument database records to Document interface for RAG agents

Key Features:
- Two-stage retrieval: retrieve top_k * 4 candidates, rerank to top_k
- HNSW index for sub-second similarity search
- MPS (Apple Silicon) acceleration for embeddings and reranking
- Lazy loading of reranker to reduce startup time
- Async operations with asyncpg
- Proper error handling and connection management
- Interface compatibility with DocumentRetriever for zero-code RAG integration

Performance Targets:
- Query embedding generation: <500ms
- pgvector similarity search: <1s
- Reranking (20 candidates): <2s
- Total search latency (p95): <3s

Usage:
    # Initialize database pool
    pool = DatabasePool(min_size=5, max_size=20)
    await pool.initialize()

    # Create retriever (models lazy load by default)
    retriever = PostgreSQLRetriever(
        pool=pool,
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        reranker_model="Qwen/Qwen3-Reranker-0.6B",
        use_reranking=True
    )

    # Optional: Preload models during startup
    # await retriever.initialize()

    # Search (models lazy load on first call if not preloaded)
    results = await retriever.search(
        query="What are the side effects of aripiprazole?",
        top_k=5,
        filters={"source_document": "02_aripiprazole"}
    )

    for doc in results:
        print(f"Rerank score: {doc.metadata['rerank_score']:.3f}")
        print(f"Similarity score: {doc.metadata['similarity_score']:.3f}")
        print(f"Content: {doc.content[:200]}")

    # Cleanup
    await retriever.close()
    await pool.close()

References:
- Interface: app/core/retriever.py (DocumentRetriever, Document)
- Reranker: app/core/qwen3_reranker.py
- Encoder: src/embeddings/encoder.py
- Tasks: T021-T029 in specs/002-semantic-search/tasks.md
"""

import logging
from typing import List, Optional, Dict, Any

import numpy as np

from app.core.retriever import DocumentRetriever, Document
from app.core.qwen3_reranker import Qwen3Reranker
from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder

logger = logging.getLogger(__name__)


class PostgreSQLRetriever(DocumentRetriever):
    """PostgreSQL-based document retriever with pgvector similarity search.

    Implements DocumentRetriever interface for seamless RAG agent integration.
    Uses Qwen3-Embedding-0.6B for query encoding and pgvector for fast search.

    Attributes:
        db_pool: DatabasePool instance (must be initialized externally)
        encoder: Qwen3EmbeddingEncoder for generating query embeddings (lazy loaded)
        embedding_model: Name of embedding model (Qwen3-Embedding-0.6B)
        reranker_model: Name of reranker model (Qwen3-Reranker-0.6B)
        reranker: Qwen3Reranker for reranking search results (lazy loaded)
        use_reranking: Whether to enable two-stage retrieval with reranking
    """

    def __init__(
        self,
        pool: DatabasePool,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        reranker_model: str = "Qwen/Qwen3-Reranker-0.6B",
        use_reranking: bool = True,
    ):
        """Initialize PostgreSQL retriever.

        Args:
            pool: DatabasePool instance (must be initialized)
            embedding_model: HuggingFace model ID for embeddings
            reranker_model: HuggingFace model ID for reranking
            use_reranking: Enable two-stage retrieval with reranking

        Note:
            Models are lazy loaded by default. Call initialize() to preload.
        """
        self.db_pool = pool
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model
        self.use_reranking = use_reranking

        # Models (lazy loaded)
        self.encoder: Optional[Qwen3EmbeddingEncoder] = None
        self.reranker: Optional[Qwen3Reranker] = None

        logger.info(
            f"PostgreSQLRetriever created: "
            f"embedding={embedding_model}, reranker={reranker_model}, "
            f"use_reranking={use_reranking}"
        )

    async def initialize(self) -> None:
        """Initialize (preload) embedding encoder and reranker models.

        This is optional - models will lazy load on first use if not called.
        Call this during startup if you want to preload models.

        Raises:
            RuntimeError: If model loading fails
        """
        if self.encoder is not None and self.reranker is not None:
            logger.info("Models already initialized")
            return

        # Load encoder
        logger.info(f"Loading encoder: {self.embedding_model}")
        self.encoder = Qwen3EmbeddingEncoder(
            model_name=self.embedding_model,
            device="mps",
            batch_size=16,
            max_length=1024,
            normalize_embeddings=True,
            instruction=None
        )
        logger.info(f"✅ Encoder loaded on device: {self.encoder.device}")

        # Load reranker if enabled
        if self.use_reranking:
            logger.info(f"Loading reranker: {self.reranker_model}")
            self.reranker = Qwen3Reranker(
                model_name=self.reranker_model,
                device="mps",
                batch_size=8
            )
            logger.info("✅ Reranker loaded")
        else:
            logger.info("ℹ️  Reranking disabled, skipping reranker initialization")

    async def close(self) -> None:
        """Cleanup resources (models remain loaded, pool cleanup handled by app)."""
        logger.info("PostgreSQLRetriever closed (pool cleanup handled by app)")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for relevant documents using pgvector similarity search.

        Models are lazy loaded on first call if not preloaded.

        Process:
        1. Validate inputs
        2. Lazy load encoder if needed
        3. Generate query embedding using Qwen3-Embedding-0.6B
        4. Execute pgvector cosine similarity search with HNSW index
        5. Apply metadata filters if provided
        6. Retrieve top_k * 4 candidates (20 for top_k=5) if reranking enabled
        7. Lazy load reranker if needed
        8. Rerank candidates with Qwen3-Reranker-0.6B and select top_k
        9. Convert VectorDocument records to Document objects

        Args:
            query: Natural language search query
            top_k: Number of top results to return (default: 5)
            filters: Optional metadata filters (e.g., {"source_document": "02_aripiprazole"})

        Returns:
            List of Document objects sorted by relevance (highest first)

        Example:
            results = await retriever.search(
                query="What are side effects?",
                top_k=5,
                filters={"source_document": "02_aripiprazole"}
            )
        """
        # Validate inputs
        assert query and query.strip(), "Query cannot be empty"
        assert self.db_pool is not None, "Database pool not initialized"

        # Lazy load encoder if not yet loaded
        if self.encoder is None:
            logger.info("Lazy loading encoder (first search call)...")
            self.encoder = Qwen3EmbeddingEncoder(
                model_name=self.embedding_model,
                device="mps",
                batch_size=16,
                max_length=1024,
                normalize_embeddings=True,
                instruction=None
            )

        # Generate query embedding
        logger.info(f"Generating embedding for query: {query[:100]}...")
        query_embedding = self._generate_query_embedding(query)

        # Calculate candidate count for reranking (4x oversampling)
        candidate_count = top_k * 4 if self.use_reranking else top_k

        # Build SQL query with optional metadata filters
        sql_query, params = self._build_search_query(
            query_embedding=query_embedding,
            top_k=candidate_count,
            filters=filters
        )

        # Execute pgvector similarity search
        logger.info(
            f"Executing pgvector search (top_k={candidate_count}, filters={filters})"
        )
        results = await self.db_pool.fetch(sql_query, *params)

        logger.info(f"Retrieved {len(results)} candidates from database")

        if not results:
            logger.warning("No candidates found for query")
            return []

        # Rerank candidates if enabled
        if self.use_reranking and len(results) > 0:
            # Lazy load reranker if not yet loaded
            if self.reranker is None:
                logger.info("Lazy loading reranker (first search with reranking)...")
                self.reranker = Qwen3Reranker(
                    model_name=self.reranker_model,
                    device="mps",
                    batch_size=8
                )

            # Extract candidate texts for reranking
            candidate_texts = [row["chunk_text"] for row in results]

            logger.debug(f"Reranking {len(candidate_texts)} candidates")
            rerank_scores = self.reranker.rerank(
                query=query,
                documents=candidate_texts
            )

            # Attach rerank scores to results
            for i, row in enumerate(results):
                # Convert asyncpg.Record to dict if needed
                if hasattr(row, '_asdict'):
                    row_dict = dict(row)
                    row_dict["rerank_score"] = rerank_scores[i]
                    results[i] = row_dict
                else:
                    row["rerank_score"] = rerank_scores[i]

            # Sort by rerank_score (highest first)
            results = sorted(
                results,
                key=lambda x: x["rerank_score"] if isinstance(x, dict) else x.get("rerank_score", 0),
                reverse=True
            )

            # Take top_k after reranking
            results = results[:top_k]

            logger.info(
                f"Reranked {len(candidate_texts)} candidates, returning top {len(results)} results"
            )
        else:
            # No reranking - use similarity scores directly
            results = results[:top_k]
            logger.info(f"Returning {len(results)} results (no reranking)")

        # Convert database records to Document objects
        documents = self._convert_to_documents(results)

        return documents

    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding vector for query text.

        Args:
            query: Natural language query text

        Returns:
            1024-dimensional embedding vector as list
        """
        assert self.encoder is not None, "Encoder not initialized"

        # Encode query text (returns numpy array of shape (1024,))
        embedding = self.encoder.encode(query)

        # Convert to list for pgvector compatibility
        assert isinstance(embedding, np.ndarray), f"Unexpected embedding type: {type(embedding)}"
        embedding_list: List[float] = embedding.tolist()

        logger.debug(
            f"Generated embedding: dimension={len(embedding_list)}, "
            f"sample={embedding_list[:3]}..."
        )

        return embedding_list

    def _build_search_query(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[str, List[Any]]:
        """Build SQL query with pgvector similarity search and optional filters.

        Args:
            query_embedding: Query embedding vector (1024 dimensions)
            top_k: Number of results to retrieve
            filters: Optional metadata filters

        Returns:
            Tuple of (sql_query, parameters)

        Example SQL (no filters):
            SELECT chunk_id, chunk_text, source_document, ...
            FROM vector_chunks
            ORDER BY embedding <=> $1
            LIMIT $2

        Example SQL (with filters):
            SELECT chunk_id, chunk_text, source_document, ...
            FROM vector_chunks
            WHERE source_document = $1 OR chapter_title = $2
            ORDER BY embedding <=> $3
            LIMIT $4
        """
        # Base SELECT clause
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

        # Add WHERE clause if filters provided
        params = [query_embedding]
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

        # Add ORDER BY and LIMIT
        sql += f"""
        ORDER BY embedding <=> $1
        LIMIT ${param_index}
        """
        params.append(top_k)  # type: ignore[arg-type]

        return sql, params

    def _convert_to_documents(self, records: List[Any]) -> List[Document]:
        """Convert database records to Document objects.

        Maps VectorDocument fields to Document interface:
        - chunk_id → id
        - chunk_text → content
        - metadata fields → metadata dict
        - similarity_score → metadata["similarity_score"]
        - rerank_score → metadata["rerank_score"] (if reranking enabled)

        Args:
            records: List of asyncpg.Record objects from database query

        Returns:
            List of Document objects compatible with DocumentRetriever interface
        """
        documents = []

        for record in records:
            # Convert asyncpg.Record to dict for easier access
            if isinstance(record, dict):
                row = record
            else:
                row = dict(record)

            # Build metadata dict
            metadata = {
                "source_document": row.get("source_document", ""),
                "chapter_title": row.get("chapter_title", ""),
                "section_title": row.get("section_title", ""),
                "subsection_title": row.get("subsection_title", []),
                "summary": row.get("summary", ""),
                "token_count": row.get("token_count", 0),
                "similarity_score": row.get("similarity_score", 0.0),
            }

            # Add rerank_score if available
            if "rerank_score" in row:
                metadata["rerank_score"] = float(row["rerank_score"])

            # Create Document object
            document = Document(
                id=row.get("chunk_id"),
                content=row.get("chunk_text", ""),
                metadata=metadata,
                parent_id=None,  # Not used in semantic search
                child_ids=[],  # Not used in semantic search
                timestamp_start=None,  # Not used in semantic search
                timestamp_end=None,  # Not used in semantic search
            )

            documents.append(document)

        return documents

    async def add_documents(self, docs: List[Document]) -> None:
        """Not implemented - use CLI for indexing.

        This POC uses CLI-based indexing for better performance and control.
        Runtime document addition is not supported.

        Use the CLI for indexing:
            python -m src.embeddings.cli index --input data/chunking_final/

        Args:
            docs: List of Document objects to index

        Raises:
            NotImplementedError: Always raised - use CLI indexing instead
        """
        raise NotImplementedError(
            "Runtime document addition not supported in this POC.\n"
            "Use CLI for indexing: python -m src.embeddings.cli index --input data/chunking_final/\n"
            "See CLAUDE.md 'Semantic Search Commands' section for details."
        )

    async def __aenter__(self) -> "PostgreSQLRetriever":
        """Context manager entry: initialize retriever.

        Example:
            async with PostgreSQLRetriever(db_url) as retriever:
                results = await retriever.search("query")
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit: cleanup retriever."""
        await self.close()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"PostgreSQLRetriever("
            f"embedding_model={self.embedding_model}, "
            f"reranker_model={self.reranker_model}, "
            f"use_reranking={self.use_reranking}, "
            f"pool_initialized={self.db_pool is not None}, "
            f"encoder_loaded={self.encoder is not None}, "
            f"reranker_loaded={self.reranker is not None})"
        )
