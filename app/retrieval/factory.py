"""Factory for creating retrieval strategy instances.

Selects appropriate retriever based on settings.RETRIEVAL_STRATEGY.
"""

import logging
from typing import Union

from app.config import settings
from app.db.connection import DatabasePool
from src.embeddings.encoder import Qwen3EmbeddingEncoder
from app.core.qwen3_reranker import Qwen3Reranker
from app.retrieval.simple import SimpleRetriever
from app.retrieval.rerank import RerankRetriever
from app.retrieval.advanced import AdvancedRetriever

logger = logging.getLogger(__name__)


def get_retriever(
    pool: DatabasePool,
    encoder: Qwen3EmbeddingEncoder,
    reranker: Qwen3Reranker | None = None,
) -> Union[SimpleRetriever, RerankRetriever, AdvancedRetriever]:
    """Create retriever based on settings.RETRIEVAL_STRATEGY.

    Strategies:
        - "simple": SimpleRetriever (no reranking, fastest)
        - "rerank": RerankRetriever (requires reranker)
        - "advanced": AdvancedRetriever (requires reranker + LLM query expansion)

    Args:
        pool: Initialized database pool
        encoder: Initialized embedding encoder
        reranker: Initialized reranker (required for "rerank" and "advanced")

    Returns:
        Configured retriever instance

    Raises:
        ValueError: If strategy is unknown or reranker missing for strategies that need it

    Example:
        >>> from app.retrieval import get_retriever
        >>> retriever = get_retriever(pool, encoder, reranker)
        >>> results = await retriever.search("aripiprazole side effects")
    """
    strategy = settings.RETRIEVAL_STRATEGY.lower()

    logger.info(f"Creating retriever with strategy: {strategy}")

    if strategy == "simple":
        # No reranking needed
        return SimpleRetriever(pool=pool, encoder=encoder)

    elif strategy == "rerank":
        # Requires reranker
        assert reranker is not None, (
            "Reranker required for 'rerank' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return RerankRetriever(pool=pool, encoder=encoder, reranker=reranker)

    elif strategy == "advanced":
        # Requires reranker for final stage
        assert reranker is not None, (
            "Reranker required for 'advanced' strategy. "
            "Initialize Qwen3Reranker and pass to factory."
        )
        return AdvancedRetriever(pool=pool, encoder=encoder, reranker=reranker)

    else:
        raise ValueError(
            f"Unknown retrieval strategy: '{strategy}'. "
            f"Valid options: 'simple', 'rerank', 'advanced'"
        )
