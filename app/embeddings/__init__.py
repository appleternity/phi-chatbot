"""
Embedding providers module.

Provides abstraction layer for local and cloud-based embedding generation.
Supports local Qwen3, OpenRouter API, and Aliyun DashScope providers.
"""

from app.embeddings.base import EmbeddingProvider
from app.embeddings.local_encoder import Qwen3EmbeddingProvider
from app.embeddings.openrouter_provider import OpenRouterEmbeddingProvider
from app.embeddings.aliyun_provider import AliyunEmbeddingProvider
from app.embeddings.factory import create_embedding_provider
from app.embeddings.utils import retry_with_backoff

# Backward compatibility alias
LocalEmbeddingProvider = Qwen3EmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "Qwen3EmbeddingProvider",
    "LocalEmbeddingProvider",  # Alias for backward compatibility
    "OpenRouterEmbeddingProvider",
    "AliyunEmbeddingProvider",
    "create_embedding_provider",
    "retry_with_backoff",
]
