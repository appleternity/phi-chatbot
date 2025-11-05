"""
Qwen3-Embedding-0.6B encoder with Apple MPS support.

This module provides the Qwen3EmbeddingEncoder class for generating 1024-dimensional
embeddings using the Qwen3-Embedding-0.6B model with MPS (Metal Performance Shaders)
acceleration on Apple Silicon.

Key Features:
- Apple MPS, CUDA, and CPU device support with automatic fallback
- Batch processing with configurable batch size
- Mean pooling on last_hidden_state
- Optional L2 normalization
- torch.float32 for MPS compatibility (float16 not supported on MPS)

Usage:
    from src.embeddings.encoder import Qwen3EmbeddingEncoder

    encoder = Qwen3EmbeddingEncoder(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        device="mps",
        batch_size=16,
        normalize_embeddings=True
    )

    # Single text
    embedding = encoder.encode("What are the side effects of aripiprazole?")

    # Multiple texts
    embeddings = encoder.encode([
        "What are the side effects of aripiprazole?",
        "How does aripiprazole work?"
    ])
"""

import logging
from typing import List, Union, Optional, Literal

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


# Configure logging
logger = logging.getLogger(__name__)


class Qwen3EmbeddingEncoder:
    """
    Qwen3-Embedding-0.6B encoder with MPS support for Apple Silicon.

    This encoder generates 1024-dimensional embeddings using the Qwen3-Embedding-0.6B
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
        Initialize Qwen3EmbeddingEncoder with direct parameters.

        Args:
            model_name: HuggingFace model ID (default: Qwen/Qwen3-Embedding-0.6B)
            device: Inference device - "mps", "cuda", or "cpu" (default: mps)
            batch_size: Batch size for embedding generation (default: 1, range: 1-128)
            max_length: Maximum token length for inputs (default: 8196, range: 128-32768)
            normalize_embeddings: Whether to L2 normalize embeddings (default: True)
            instruction: Optional task-specific instruction prefix (default: None)

        Raises:
            RuntimeError: If model fails to load or device is unavailable
            ValueError: If parameters are out of valid ranges
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

        # Load tokenizer
        logger.info(f"Loading tokenizer: {model_name}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {e}")
            raise RuntimeError(f"Failed to load tokenizer from {model_name}: {e}")

        # Load model with MPS-compatible float32
        logger.info(f"Loading model: {model_name}")
        try:
            self.model = AutoModel.from_pretrained(
                model_name,
                dtype=torch.float32,  # MPS requires float32 (float16 not supported)
            ).to(self.device).eval()
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Failed to load model from {model_name}: {e}")

        logger.info(
            f"Encoder initialized: device={self.device}, "
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
        show_progress: bool = False
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
            ValueError: If texts is empty or contains empty strings
            RuntimeError: If embedding generation fails

        Example:
            >>> encoder = Qwen3EmbeddingEncoder(config)
            >>> # Single text
            >>> embedding = encoder.encode("What are side effects?")
            >>> embedding.shape
            (1024,)
            >>> # Multiple texts
            >>> embeddings = encoder.encode(["Text 1", "Text 2"])
            >>> len(embeddings)
            2
        """
        # Handle single text input
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        # Validate inputs
        if not texts:
            raise ValueError("texts cannot be empty")
        if any(not text or not text.strip() for text in texts):
            raise ValueError("texts contains empty or whitespace-only strings")

        # Use instance batch size if not specified
        if batch_size is None:
            batch_size = self.batch_size

        # Process in batches
        all_embeddings = []
        num_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_num = i // batch_size + 1

            if show_progress:
                logger.info(f"Processing batch {batch_num}/{num_batches} ({len(batch_texts)} texts)")

            try:
                batch_embeddings = self._encode_batch(batch_texts)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Failed to encode batch {batch_num}: {e}")
                raise RuntimeError(f"Failed to encode batch {batch_num}: {e}")

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
            RuntimeError: If encoding fails
        """
        try:
            # Tokenize with instruction prefix if specified
            if self.instruction:
                texts = [f"{self.instruction} {text}" for text in texts]

            # Tokenize
            inputs = self.tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length
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

        except Exception as e:
            logger.error(f"Batch encoding failed: {e}")
            raise RuntimeError(f"Batch encoding failed: {e}")

    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension for this model.

        Dynamically determines dimension by encoding a test string on first call,
        then caches the result. Works with any embedding model.

        Returns:
            Embedding dimension size (e.g., 1024 for Qwen3-Embedding-0.6B)
        """
        # Cache dimension from first encoding
        if not hasattr(self, '_embedding_dim'):
            test_embedding = self.encode(["test"], show_progress=False)[0]
            self._embedding_dim = len(test_embedding)

        return self._embedding_dim

    def __repr__(self) -> str:
        """String representation of encoder."""
        return (
            f"Qwen3EmbeddingEncoder("
            f"model={self.model_name}, "
            f"device={self.device}, "
            f"batch_size={self.batch_size}, "
            f"normalize={self.normalize_embeddings})"
        )
