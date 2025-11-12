"""
EmbeddingProvider ABC - Abstract base class for all embedding providers.

This interface defines the required methods that all embedding providers
(local, OpenRouter, Aliyun) must implement through explicit inheritance.

Design Decision: ABC over Protocol
- Fail-fast at import time (not runtime or type-check time)
- Explicit inheritance makes intent clear
- Better IDE support for autocomplete and type checking
- Simpler for fixed number of known providers
"""

from abc import ABC, abstractmethod
from typing import Union, List
import numpy as np


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding providers must explicitly inherit from this class and
    implement all abstract methods.
    """

    @abstractmethod
    def encode(self, texts: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for input text(s).

        Args:
            texts: Single text string or list of text strings

        Returns:
            - If single text: numpy array of shape (dimension,)
            - If multiple texts: list of numpy arrays, each of shape (dimension,)

        Raises:
            AssertionError: If texts is empty or contains invalid inputs
            Exception: If embedding generation fails (propagates naturally)

        Example:
            >>> provider = Qwen3EmbeddingProvider()
            >>> # Single text
            >>> embedding = provider.encode("What are side effects?")
            >>> embedding.shape
            (1024,)
            >>> # Multiple texts
            >>> embeddings = provider.encode(["Text 1", "Text 2"])
            >>> len(embeddings)
            2
        """
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension for this provider.

        Dimension depends on model:
        - Qwen3-Embedding-0.6B: 1024
        - Aliyun text-embedding-v4: 1024

        Returns:
            Embedding dimension size

        Example:
            >>> provider.get_embedding_dimension()
            1024
        """
        # TODO: we probably don't need this function? Where did we use it?
        # TODO: it is hardcoded values and I don't think those values make sense if we change the model.
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the provider name for logging and debugging.

        Returns:
            Provider name string

        Valid values:
            - "qwen3_local": Local Qwen3-Embedding-0.6B
            - "qwen3_openrouter": OpenRouter API (Qwen3-Embedding-0.6B)
            - "aliyun_dashscope": Aliyun text-embedding-v4

        Example:
            >>> provider.get_provider_name()
            'qwen3_local'
        """
        pass
