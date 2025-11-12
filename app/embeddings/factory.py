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
    openai_api_key: str = "",
    aliyun_api_key: str = ""
) -> EmbeddingProvider:
    """
    Create embedding provider with explicit parameters.

    This function uses explicit parameters instead of a settings object,
    making it easier to trace where values come from during debugging.

    Args:
        provider_type: Provider type ("local", "openrouter", "aliyun")
        embedding_model: Model name (e.g., "Qwen/Qwen3-Embedding-0.6B")
        device: Device for local provider ("mps", "cuda", "cpu")
        openai_api_key: API key for OpenRouter (required if provider_type="openrouter")
        aliyun_api_key: API key for Aliyun (required if provider_type="aliyun")

    Returns:
        Configured embedding provider instance

    Raises:
        AssertionError: If provider_type is invalid or required API keys missing
        Exception: If provider initialization fails (propagates naturally)

    Example:
        >>> from app.embeddings.factory import create_embedding_provider
        >>> provider = create_embedding_provider(
        ...     provider_type="local",
        ...     embedding_model="Qwen/Qwen3-Embedding-0.6B",
        ...     device="mps"
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
            batch_size=4,  # Default batch size
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
            batch_size=10,  # OpenRouter API batch size
        )

        logger.info("OpenRouter provider initialized: model=qwen/qwen3-embedding-0.6b")

    elif provider_type == "aliyun":
        assert aliyun_api_key, \
            "Aliyun API key required. Set ALIYUN_API_KEY environment variable."

        provider = AliyunEmbeddingProvider(
            api_key=aliyun_api_key,
            batch_size=10,  # Aliyun API batch size
        )

        logger.info("Aliyun provider initialized: model=text-embedding-v4")

    else:
        # Should never reach here due to config validation, but defensive check
        assert False, \
            f"Invalid provider_type: '{provider_type}'. " \
            f"Valid options: 'local', 'openrouter', 'aliyun'"

    return provider


class EmbeddingProviderFactory:
    """
    Factory class for creating embedding providers.

    This class wraps the create_embedding_provider function for backward compatibility
    with tests that expect a class-based factory pattern.
    """

    @staticmethod
    def create_provider(settings: "Settings") -> EmbeddingProvider:
        """
        Create embedding provider from settings object.

        Args:
            settings: Application settings with provider configuration

        Returns:
            Configured embedding provider instance

        Raises:
            AssertionError: If provider_type is invalid or required API keys missing
            Exception: If provider initialization fails (propagates naturally)

        Example:
            >>> from app.config import settings
            >>> from app.embeddings.factory import EmbeddingProviderFactory
            >>> provider = EmbeddingProviderFactory.create_provider(settings)
        """
        return create_embedding_provider(
            provider_type=settings.embedding_provider,
            embedding_model=settings.EMBEDDING_MODEL,
            device=settings.device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key,
        )
