"""
Embedding Provider Factory.

Factory for creating embedding provider instances with explicit parameters.
Supports local Qwen3, OpenRouter API, and Aliyun DashScope providers.
"""

import logging
from typing import TYPE_CHECKING

from app.embeddings.base import EmbeddingProvider
from app.embeddings.local_encoder import Qwen3EmbeddingProvider
from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


def create_embedding_provider(
    provider_type: str,
    embedding_model: str,
    device: str,
    batch_size: int = 10,
    openai_api_key: str = "",
    aliyun_api_key: str = ""
) -> EmbeddingProvider:
    """
    Create embedding provider with explicit parameters.

    This function uses explicit parameters instead of a settings object,
    making it easier to trace where values come from during debugging.

    Args:
        provider_type: Provider type ("local", "openrouter", "aliyun")
        embedding_model: Model name/identifier
            - Local: HuggingFace model ID (e.g., "Qwen/Qwen3-Embedding-0.6B")
            - OpenRouter: Model path (e.g., "qwen/qwen3-embedding-0.6b")
            - Aliyun: Model name (e.g., "text-embedding-v4")
        device: Device for local provider ("mps", "cuda", "cpu")
        batch_size: Batch size for processing (default: 10)
        openai_api_key: API key for OpenRouter (required if provider_type="openrouter")
        aliyun_api_key: API key for Aliyun (required if provider_type="aliyun")

    Returns:
        Configured embedding provider instance

    Raises:
        AssertionError: If provider_type is invalid or required API keys missing
        Exception: If provider initialization fails (propagates naturally)

    Example:
        >>> from app.embeddings.factory import create_embedding_provider
        >>> # Local provider
        >>> provider = create_embedding_provider(
        ...     provider_type="local",
        ...     embedding_model="Qwen/Qwen3-Embedding-0.6B",
        ...     device="mps"
        ... )
        >>> # OpenRouter provider with custom model
        >>> provider = create_embedding_provider(
        ...     provider_type="openrouter",
        ...     embedding_model="custom/embedding-model",
        ...     openai_api_key="sk-or-..."
        ... )
        >>> embeddings = provider.encode("test query")
    """
    provider_type = provider_type.lower()

    logger.info(f"Creating embedding provider: {provider_type}")

    provider: EmbeddingProvider

    if provider_type == "local":
        # Create local provider with Qwen3-Embedding-0.6B
        provider = Qwen3EmbeddingProvider(
            model_name=embedding_model,
            device=device,  # Use configured device (auto-fallback to CUDA/CPU if unavailable)
            batch_size=batch_size,
            normalize_embeddings=True,
        )

        logger.info(
            f"Qwen3 local provider initialized: model={embedding_model}, device={device}"
        )

    elif provider_type == "openrouter":
        assert openai_api_key, \
            "OpenRouter API key required. Set OPENAI_API_KEY environment variable."

        provider = OpenRouterEmbeddingProvider(
            api_key=openai_api_key,
            model=embedding_model,  # User-specified model (e.g., qwen/qwen3-embedding-0.6b)
            batch_size=batch_size,
        )

        logger.info(f"OpenRouter provider initialized: model={embedding_model}")

    elif provider_type == "aliyun":
        assert aliyun_api_key, \
            "Aliyun API key required. Set ALIYUN_API_KEY environment variable."

        provider = AliyunEmbeddingProvider(
            api_key=aliyun_api_key,
            model=embedding_model,  # User-specified model (e.g., text-embedding-v4)
            batch_size=batch_size,
        )

        logger.info(f"Aliyun provider initialized: model={embedding_model}")

    else:
        # Should never reach here due to config validation, but defensive check
        assert False, \
            f"Invalid provider_type: '{provider_type}'. " \
            f"Valid options: 'local', 'openrouter', 'aliyun'"

    return provider
