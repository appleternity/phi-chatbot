"""Document reranking using cross-encoder models."""

from typing import List
import logging
import torch
from sentence_transformers import CrossEncoder

from app.core.retriever import Document

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Reranker using cross-encoder models for improved relevance scoring.

    Cross-encoders evaluate query-document pairs jointly, providing more
    accurate relevance scores than bi-encoder retrieval alone. This improves
    precision for top-k results in RAG pipelines.

    Typical usage:
        1. Initial retrieval with bi-encoder (fast, broad recall)
        2. Reranking with cross-encoder (slower, precise top-k)

    Performance considerations:
        - Cross-encoders are computationally expensive (process pairs)
        - Use for small candidate sets (10-100 documents)
        - Significant accuracy improvement over bi-encoder similarity
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length: int = 512,
    ) -> None:
        """Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace model name for cross-encoder
            max_length: Maximum sequence length for model input

        Raises:
            RuntimeError: If model fails to load
        """
        self._model_name = model_name
        self._max_length = max_length

        # Detect and configure device (MPS for Apple Silicon, fallback to CPU)
        if torch.backends.mps.is_available():
            self._device = "mps"
            logger.info(f"Using device: mps for reranking (Apple Metal Performance Shaders)")
        else:
            self._device = "cpu"
            logger.info(f"Using device: cpu for reranking")

        try:
            # Initialize cross-encoder model
            self._model = CrossEncoder(
                model_name,
                max_length=max_length,
                device=self._device
            )
            logger.info(
                f"Loaded cross-encoder model: {model_name} "
                f"(device: {self._device}, max_length: {max_length})"
            )
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model '{model_name}': {e}")
            raise RuntimeError(
                f"Failed to initialize CrossEncoderReranker with model '{model_name}': {e}"
            ) from e

    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: int = 3,
    ) -> List[Document]:
        """Rerank documents by relevance to query using cross-encoder scoring.

        Args:
            query: Search query to compare against documents
            documents: List of candidate documents to rerank
            top_k: Number of top-ranked documents to return

        Returns:
            List of documents sorted by relevance score (highest first),
            limited to top_k results

        Raises:
            ValueError: If documents list is empty or top_k is invalid

        Example:
            >>> reranker = CrossEncoderReranker()
            >>> docs = retriever.search("quantum computing", top_k=10)
            >>> reranked = reranker.rerank("quantum computing", docs, top_k=3)
            >>> # Returns 3 most relevant docs from initial 10 candidates
        """
        # Edge case: empty documents
        if not documents:
            logger.warning("Rerank called with empty documents list")
            return []

        # Edge case: invalid top_k
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")

        # Edge case: top_k larger than document count
        effective_top_k = min(top_k, len(documents))
        if effective_top_k < top_k:
            logger.debug(
                f"Requested top_k={top_k} but only {len(documents)} documents available"
            )

        # Edge case: single document (no reranking needed)
        if len(documents) == 1:
            logger.debug("Single document, returning without reranking")
            return documents[:effective_top_k]

        try:
            # Create (query, document) pairs for cross-encoder
            pairs = [[query, doc.content] for doc in documents]

            # Get relevance scores from cross-encoder
            # Scores are logits (not probabilities), higher = more relevant
            scores = self._model.predict(pairs, show_progress_bar=False)

            # Sort documents by score (descending order)
            # Use enumerate to preserve original indices during sorting
            scored_docs = list(zip(scores, documents))
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            # Extract top_k documents
            reranked_documents = [doc for _, doc in scored_docs[:effective_top_k]]

            # Log reranking statistics
            if len(documents) > 0:
                score_min = float(min(scores))
                score_max = float(max(scores))
                score_mean = float(sum(scores) / len(scores))
                logger.info(
                    f"Reranked {len(documents)} documents → top {effective_top_k} "
                    f"(scores: min={score_min:.3f}, max={score_max:.3f}, mean={score_mean:.3f})"
                )

            return reranked_documents

        except Exception as e:
            logger.error(
                f"Reranking failed for query '{query[:50]}...' "
                f"with {len(documents)} documents: {e}"
            )
            # Graceful degradation: return original documents if reranking fails
            logger.warning(
                f"Returning original document order due to reranking failure"
            )
            return documents[:effective_top_k]

    @property
    def model_name(self) -> str:
        """Get the name of the loaded cross-encoder model."""
        return self._model_name

    @property
    def device(self) -> str:
        """Get the device used for inference (cpu, cuda, mps)."""
        return self._device

    @property
    def max_length(self) -> int:
        """Get the maximum sequence length for model input."""
        return self._max_length
