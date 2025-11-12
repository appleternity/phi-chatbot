"""
EmbeddingProvider Protocol - Abstract interface for all embedding providers.

This contract defines the required methods and signatures that all embedding
providers (local, OpenRouter, Aliyun) must implement.
"""

from typing import Protocol, Union, List, Dict
import numpy as np


class EmbeddingProvider(Protocol):
    """
    Abstract interface for embedding providers.

    All embedding providers must implement this protocol to ensure consistent
    behavior across local and cloud-based implementations.
    """

    def encode(
        self, texts: Union[str, List[str]]
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for input text(s).

        Args:
            texts: Single text string or list of text strings

        Returns:
            - If single text: numpy array of shape (1024,)
            - If multiple texts: list of numpy arrays, each of shape (1024,)

        Raises:
            ValueError: If texts is empty or contains invalid inputs
            RuntimeError: If embedding generation fails (API errors, model errors)

        Example:
            >>> provider = LocalEmbeddingProvider()
            >>> # Single text
            >>> embedding = provider.encode("What are side effects?")
            >>> embedding.shape
            (1024,)
            >>> # Multiple texts
            >>> embeddings = provider.encode(["Text 1", "Text 2"])
            >>> len(embeddings)
            2
        """
        ...

    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension for this provider.

        All current providers return 1024-dimensional embeddings.

        Returns:
            Embedding dimension size (1024)

        Example:
            >>> provider.get_embedding_dimension()
            1024
        """
        ...

    def get_provider_name(self) -> str:
        """
        Get the provider name for logging and debugging.

        Returns:
            Provider name string

        Valid values:
            - "local_qwen3": Local Qwen3-Embedding-0.6B
            - "openrouter": OpenRouter API (Qwen3-Embedding-0.6B)
            - "aliyun": Aliyun text-embedding-v4

        Example:
            >>> provider.get_provider_name()
            'local_qwen3'
        """
        ...

    def validate_dimension(self, expected_dim: int) -> None:
        """
        Validate embedding dimension matches database schema.

        This method should be called during provider initialization to ensure
        the provider's output dimension matches the database vector column dimension.

        Args:
            expected_dim: Expected dimension from database schema (config.embedding_dim)

        Raises:
            ValueError: If actual dimension != expected dimension

        Example:
            >>> provider = LocalEmbeddingProvider()
            >>> provider.validate_dimension(1024)  # Passes
            >>> provider.validate_dimension(768)   # Raises ValueError
            ValueError: Provider local_qwen3 returns 1024-dim embeddings,
                        but database expects 768-dim. Database re-indexing required.
        """
        ...


# Type alias for convenience
# TODO: this is also not used anywhere?
# TODO: actually this whole file is not used anywhere?
Embedding = Union[np.ndarray, List[np.ndarray]]
