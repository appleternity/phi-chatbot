"""
Qwen3-Embedding-0.6B encoder with Apple MPS support.

This module provides the Qwen3EmbeddingProvider class for generating 1024-dimensional
embeddings using the Qwen3-Embedding-0.6B model with MPS (Metal Performance Shaders)
acceleration on Apple Silicon.

Key Features:
- Apple MPS, CUDA, and CPU device support with automatic fallback
- Batch processing with configurable batch size
- Mean pooling on last_hidden_state
- Optional L2 normalization
- torch.float32 for MPS compatibility (float16 not supported on MPS)
- Ultra fail-fast design: all exceptions propagate naturally

Usage:
    from app.embeddings.local_encoder import Qwen3EmbeddingProvider

    provider = Qwen3EmbeddingProvider(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        device="mps",
        batch_size=16,
        normalize_embeddings=True
    )

    # Single text
    embedding = provider.encode("What are the side effects of aripiprazole?")

    # Multiple texts
    embeddings = provider.encode([
        "What are the side effects of aripiprazole?",
        "How does aripiprazole work?"
    ])
"""

import logging
from typing import List, Union, Optional, Literal

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from app.embeddings.base import EmbeddingProvider


# Configure logging
logger = logging.getLogger(__name__)


class Qwen3EmbeddingProvider(EmbeddingProvider):
    """
    Qwen3-Embedding-0.6B local provider with MPS support.

    This provider generates 1024-dimensional embeddings using the Qwen3-Embedding-0.6B
    model with support for MPS (Apple Silicon), CUDA, and CPU devices.

    Attributes:
        model_name: HuggingFace model ID
        batch_size: Batch size for embedding generation
        max_length: Maximum token length for inputs
        normalize_embeddings: Whether to L2 normalize embeddings
        instruction: Optional task-specific instruction prefix
        device: Selected device (mps, cuda, or cpu)
        model: Loaded Qwen3-Embedding model
        tokenizer: Loaded Qwen3-Embedding tokenizer
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: Literal["mps", "cuda", "cpu"] = "mps",
        batch_size: int = 1,
        max_length: int = 8196,
        normalize_embeddings: bool = True,
        instruction: Optional[str] = None,
    ):
        """
        Initialize Qwen3EmbeddingProvider with direct parameters.

        Args:
            model_name: HuggingFace model ID (default: Qwen/Qwen3-Embedding-0.6B)
            device: Inference device - "mps", "cuda", or "cpu" (default: mps)
            batch_size: Batch size for embedding generation (default: 1, range: 1-128)
            max_length: Maximum token length for inputs (default: 8196, range: 128-32768)
            normalize_embeddings: Whether to L2 normalize embeddings (default: True)
            instruction: Optional task-specific instruction prefix (default: None)

        Raises:
            AssertionError: If parameters are invalid
            Exception: If model/tokenizer loading fails (propagates naturally)
        """
        # Validate parameters
        assert batch_size >= 1, f"batch_size must be >= 1, got {batch_size}"
        assert max_length >= 1, f"max_length must be >= 1, got {max_length}"

        # Store parameters
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.normalize_embeddings = normalize_embeddings
        self.instruction = instruction

        # Device selection with automatic fallback
        self.device = self._select_device(device)
        logger.info(f"Using device: {self.device}")

        # Load tokenizer (let exceptions propagate)
        logger.info(f"Loading tokenizer: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Load model with MPS-compatible float32 (let exceptions propagate)
        logger.info(f"Loading model: {model_name}")
        self.model = (
            AutoModel.from_pretrained(
                model_name,
                torch_dtype=torch.float32,  # MPS requires float32 (float16 not supported)
            )
            .to(self.device)
            .eval()
        )

        logger.info(
            f"Qwen3 provider initialized: device={self.device}, "
            f"batch_size={batch_size}, "
            f"normalize={normalize_embeddings}"
        )

    def _select_device(self, preferred_device: str) -> str:
        """
        Select device with automatic fallback.

        Priority: MPS > CUDA > CPU

        Args:
            preferred_device: Preferred device from config ("mps", "cuda", "cpu")

        Returns:
            Selected device string

        Raises:
            RuntimeError: If no compatible device is available
        """
        if preferred_device == "mps":
            if torch.backends.mps.is_available():
                return "mps"
            else:
                logger.warning("MPS requested but not available, falling back to CUDA or CPU")
                preferred_device = "cuda"

        if preferred_device == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                preferred_device = "cpu"

        if preferred_device == "cpu":
            return "cpu"

        raise RuntimeError(f"Invalid device: {preferred_device}")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for input text(s).

        Args:
            texts: Single text string or list of text strings
            batch_size: Batch size for processing (default: from config)
            show_progress: Whether to log progress (default: False)

        Returns:
            - If single text: numpy array of shape (1024,)
            - If multiple texts: list of numpy arrays, each of shape (1024,)

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
        # Handle single text input
        is_single = isinstance(texts, str)
        text_list: List[str]
        if is_single:
            text_list = [texts]  # type: ignore[list-item]
        else:
            text_list = texts  # type: ignore[assignment]

        # Validate inputs
        assert text_list, "texts cannot be empty"
        assert all(text and text.strip() for text in text_list), "texts contains empty or whitespace-only strings"

        logger.info(f"Encoding {len(text_list)} texts with local Qwen3 provider")

        # Use instance batch size if not specified
        if batch_size is None:
            batch_size = self.batch_size

        # Process in batches
        all_embeddings = []
        num_batches = (len(text_list) + batch_size - 1) // batch_size

        for i in range(0, len(text_list), batch_size):
            batch_texts = text_list[i : i + batch_size]
            batch_num = i // batch_size + 1

            if show_progress:
                logger.info(
                    f"Processing batch {batch_num}/{num_batches} ({len(batch_texts)} texts)"
                )

            # Let exceptions propagate naturally
            batch_embeddings = self._encode_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)

        # Return single embedding if single text input
        if is_single:
            return all_embeddings[0]

        return all_embeddings

    def _encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Encode a batch of texts into embeddings.

        Args:
            texts: List of text strings to encode

        Returns:
            List of numpy arrays, each of shape (1024,)

        Raises:
            Exception: If encoding fails (propagates naturally)
        """
        # Tokenize with instruction prefix if specified
        if self.instruction:
            texts = [f"{self.instruction} {text}" for text in texts]

        # Tokenize
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_length,
        )

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embeddings (no gradient computation)
        with torch.no_grad():
            outputs = self.model(**inputs)

            # Mean pooling on last_hidden_state
            # Shape: (batch_size, seq_length, hidden_size)
            last_hidden_state = outputs.last_hidden_state

            # Average over sequence length dimension
            # Shape: (batch_size, hidden_size)
            embeddings = last_hidden_state.mean(dim=1)

            # L2 normalization if enabled
            if self.normalize_embeddings:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

            # Move to CPU and convert to numpy
            embeddings = embeddings.cpu().numpy()

        # Convert to list of 1D arrays
        embedding_list = [embeddings[i] for i in range(embeddings.shape[0])]

        return embedding_list

    def get_provider_name(self) -> str:
        """
        Get the provider name for logging and debugging.

        Returns:
            Provider name string ("qwen3_local")

        Example:
            >>> provider = Qwen3EmbeddingProvider()
            >>> provider.get_provider_name()
            'qwen3_local'
        """
        return "qwen3_local"

    def __repr__(self) -> str:
        """String representation of provider."""
        return (
            f"Qwen3EmbeddingProvider("
            f"model={self.model_name}, "
            f"device={self.device}, "
            f"batch_size={self.batch_size}, "
            f"normalize={self.normalize_embeddings})"
        )
