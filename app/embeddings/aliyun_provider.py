"""
Aliyun DashScope embedding provider.

Implements EmbeddingProvider ABC using Aliyun's text-embedding-v4 model.
Ultra fail-fast design: all exceptions propagate naturally.
"""

import logging
from typing import Union, List
import numpy as np
import openai
from app.embeddings.base import EmbeddingProvider
from app.embeddings.utils import retry_with_backoff

logger = logging.getLogger(__name__)


class AliyunEmbeddingProvider(EmbeddingProvider):
    """
    Aliyun DashScope embedding provider using text-embedding-v4.

    This provider calls Aliyun DashScope API to generate 1024-dimensional embeddings
    using the text-embedding-v4 model with dense output format.

    API Configuration:
        - Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
        - Model: text-embedding-v4
        - Dimension: 1024 (dense format)
        - Batch size: 100 texts per request

    Args:
        api_key: Aliyun DashScope API key (required)
        batch_size: Maximum texts per batch (default: 100)

    Example:
        >>> provider = AliyunEmbeddingProvider(api_key="sk-...")
        >>> embedding = provider.encode("What are side effects?")
        >>> embedding.shape
        (1024,)
        >>> embeddings = provider.encode(["Text 1", "Text 2"])
        >>> len(embeddings)
        2
    """

    def __init__(self, api_key: str, batch_size: int = 100):
        """
        Initialize Aliyun embedding provider.

        Args:
            api_key: Aliyun DashScope API key (required)
            batch_size: Maximum texts per batch (default: 100)

        Raises:
            AssertionError: If api_key is empty or None
        """
        assert api_key, "Aliyun API key is required"

        # Initialize OpenAI client with custom base_url for Aliyun
        self.client = openai.OpenAI(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=api_key,
        )
        self.batch_size = batch_size
        self.model = "text-embedding-v4"
        self.dimension = 1024

        logger.info(
            f"Initialized Aliyun provider: model={self.model}, "
            f"dimension={self.dimension}, batch_size={self.batch_size}"
        )

    def encode(self, texts: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for input text(s) using Aliyun DashScope API.

        Args:
            texts: Single text string or list of text strings

        Returns:
            - If single text: numpy array of shape (1024,)
            - If multiple texts: list of numpy arrays, each of shape (1024,)

        Raises:
            AssertionError: If texts is empty or contains invalid inputs
            Exception: If API call fails (propagates naturally with retry)

        Example:
            >>> embedding = provider.encode("What are side effects?")
            >>> embedding.shape
            (1024,)
        """
        # Validate input
        assert texts, "texts cannot be empty"

        # Handle single text vs list
        is_single = isinstance(texts, str)
        text_list: List[str]
        if is_single:
            text_list = [texts]  # type: ignore[list-item]
        else:
            text_list = texts  # type: ignore[assignment]

        # Validate all texts are non-empty strings
        for i, text in enumerate(text_list):
            assert isinstance(text, str) and text.strip(), f"Text at index {i} is empty or not a string"

        # Batch processing - split into chunks of batch_size
        all_embeddings = []
        for i in range(0, len(text_list), self.batch_size):
            batch = text_list[i : i + self.batch_size]

            # Encode with retry logic (let exceptions propagate)
            embeddings = self._encode_with_retry(batch)
            all_embeddings.extend(embeddings)

        # Return format matching input
        if is_single:
            return all_embeddings[0]
        return all_embeddings

    def _encode_with_retry(self, texts: List[str]) -> List[np.ndarray]:
        """
        Encode texts with retry logic for transient failures.

        Args:
            texts: List of text strings to encode

        Returns:
            List of numpy arrays, each of shape (1024,)

        Raises:
            Exception: If API call fails after all retries (propagates naturally)
        """
        import time

        start_time = time.time()

        def api_call() -> openai.types.CreateEmbeddingResponse:
            # Call Aliyun embeddings API with text-embedding-v4 and dimensions=1024
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=1024,  # Dense embedding format
            )
            return response

        # Retry with exponential backoff (let exceptions propagate)
        response = retry_with_backoff(api_call, max_retries=3)

        # Extract embeddings from response
        embeddings = [np.array(item.embedding, dtype=np.float32) for item in response.data]

        # Log successful API call
        elapsed = time.time() - start_time
        total_tokens = sum(len(text.split()) for text in texts)
        logger.info(
            f"Aliyun API success: {len(texts)} texts, "
            f"{total_tokens} est. tokens, {elapsed:.2f}s"
        )

        return embeddings

    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension for this provider.

        Returns:
            Embedding dimension size (1024)

        Example:
            >>> provider.get_embedding_dimension()
            1024
        """
        return self.dimension

    def get_provider_name(self) -> str:
        """
        Get the provider name for logging and debugging.

        Returns:
            Provider name string ("aliyun")

        Example:
            >>> provider.get_provider_name()
            'aliyun'
        """
        return "aliyun"
