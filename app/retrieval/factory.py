"""Factory for creating retrieval strategy instances.

Creates appropriate retriever based on explicit strategy parameter.
"""

import logging

from app.db.connection import DatabasePool
from app.embeddings import EmbeddingProvider
from app.core.qwen3_reranker import Qwen3Reranker
from app.retrieval.simple import SimpleRetriever
from app.retrieval.rerank import RerankRetriever
from app.retrieval.advanced import AdvancedRetriever

logger = logging.getLogger(__name__)


def create_retriever(
    strategy: str,
    pool: DatabasePool,
    encoder: EmbeddingProvider,
    reranker: Qwen3Reranker | None = None,
    table_name: str = "vector_chunks",
) -> SimpleRetriever | RerankRetriever | AdvancedRetriever:
    """Create retriever with explicit strategy parameter.

    This function uses an explicit strategy parameter instead of reading from settings,
    making it easier to trace where values come from during debugging.

    Strategies:
        - "simple": SimpleRetriever (no reranking, fastest)
        - "rerank": RerankRetriever (requires reranker)
        - "advanced": AdvancedRetriever (requires reranker + LLM query expansion)

    Args:
        strategy: Retrieval strategy ("simple", "rerank", "advanced")
        pool: Initialized database pool
        encoder: Initialized embedding encoder
        reranker: Initialized reranker (required for "rerank" and "advanced")
        table_name: Table name (default: "vector_chunks")

    Returns:
        Configured retriever instance

    Raises:
        ValueError: If strategy is unknown
        AssertionError: If reranker is missing for strategies that need it

    Example:
        >>> from app.retrieval.factory import create_retriever
        >>> retriever = create_retriever(
        ...     strategy="advanced",
        ...     pool=pool,
        ...     encoder=encoder,
        ...     reranker=reranker,
        ...     table_name="text-embedding-v4"
        ... )
        >>> results = await retriever.search("aripiprazole side effects")
    """
    strategy = strategy.lower()

    logger.info(f"Creating retriever with strategy: {strategy}, table: {table_name}")

    if strategy == "simple":
        # No reranking needed
        return SimpleRetriever(pool=pool, encoder=encoder, table_name=table_name)

    elif strategy == "rerank":
        # Requires reranker
        assert reranker is not None, (
            "Reranker required for 'rerank' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return RerankRetriever(pool=pool, encoder=encoder, reranker=reranker, table_name=table_name)

    elif strategy == "advanced":
        # Requires reranker for final stage
        assert reranker is not None, (
            "Reranker required for 'advanced' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return AdvancedRetriever(pool=pool, encoder=encoder, reranker=reranker, table_name=table_name)

    else:
        raise ValueError(
            f"Unknown retrieval strategy: '{strategy}'. "
            f"Valid options: 'simple', 'rerank', 'advanced'"
        )
