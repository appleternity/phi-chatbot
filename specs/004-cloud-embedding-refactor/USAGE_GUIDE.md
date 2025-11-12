# Cloud Embedding Provider Usage Guide

**Quick reference for using the new embedding provider abstraction layer**

---

## Basic Usage

### Import Pattern (NEW)

```python
from app.embeddings.local_encoder import LocalEmbeddingProvider
from app.embeddings.factory import EmbeddingProviderFactory
from app.config import settings

# Option 1: Direct instantiation (local provider)
provider = LocalEmbeddingProvider(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device="mps",
    batch_size=16
)

# Option 2: Factory pattern (recommended for production)
provider = EmbeddingProviderFactory.create_provider(settings)
```

### Old Import Pattern (DEPRECATED)

```python
# ⚠️ DEPRECATED - Still works but will be removed in future
from src.embeddings.encoder import Qwen3EmbeddingEncoder

encoder = Qwen3EmbeddingEncoder(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device="mps",
    batch_size=16
)
```

---

## Configuration

### Environment Variables (.env)

```bash
# Embedding Provider Selection
EMBEDDING_PROVIDER=local  # Options: local, openrouter (future), aliyun (future)

# Local Provider Settings (default)
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B

# Cloud Provider Settings (for future use)
# OPENAI_API_KEY=your_openrouter_key_here  # Used for OpenRouter
# ALIYUN_API_KEY=your_aliyun_key_here      # For Aliyun DashScope

# Database Settings
TABLE_NAME=vector_chunks  # For A/B testing different embedding tables
```

### Python Configuration (app/config.py)

```python
from app.config import settings

# Current settings (Phase 2)
settings.embedding_provider  # "local" (default)
settings.EMBEDDING_MODEL     # "Qwen/Qwen3-Embedding-0.6B"
settings.table_name          # "vector_chunks"
settings.aliyun_api_key      # "" (empty, for future use)

# Validation is automatic via Pydantic
# Invalid embedding_provider values will raise ValueError
```

---

## API Reference

### EmbeddingProvider Protocol

All providers (local, OpenRouter, Aliyun) implement this interface:

```python
from app.embeddings.base import EmbeddingProvider

class EmbeddingProvider(Protocol):
    def encode(self, texts: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """Generate embeddings for input text(s)."""
        ...

    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension (1024 for all current providers)."""
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging ("local_qwen3", "openrouter", "aliyun")."""
        ...

    def validate_dimension(self, expected_dim: int) -> None:
        """Validate embedding dimension matches database schema."""
        ...
```

### LocalEmbeddingProvider

```python
from app.embeddings.local_encoder import LocalEmbeddingProvider

provider = LocalEmbeddingProvider(
    model_name="Qwen/Qwen3-Embedding-0.6B",  # HuggingFace model ID
    device="mps",                             # "mps", "cuda", or "cpu"
    batch_size=16,                            # Batch size for processing
    max_length=8196,                          # Max token length
    normalize_embeddings=True,                # L2 normalization
    instruction=None                          # Optional instruction prefix
)

# Single text
embedding = provider.encode("What are the side effects?")
print(embedding.shape)  # (1024,)

# Multiple texts
embeddings = provider.encode(["Text 1", "Text 2", "Text 3"])
print(len(embeddings))  # 3
print(embeddings[0].shape)  # (1024,)

# Metadata
print(provider.get_provider_name())      # "local_qwen3"
print(provider.get_embedding_dimension()) # 1024

# Dimension validation
provider.validate_dimension(1024)  # Passes
provider.validate_dimension(768)   # Raises ValueError
```

### EmbeddingProviderFactory

```python
from app.embeddings.factory import EmbeddingProviderFactory
from app.config import settings

# Create provider based on settings.embedding_provider
provider = EmbeddingProviderFactory.create_provider(settings)

# Provider is auto-validated against settings.embedding_dim
# No need to call validate_dimension() manually

# Use provider
embeddings = provider.encode(["Query 1", "Query 2"])
```

---

## Migration Guide

### For Application Code

**Before (DEPRECATED)**:
```python
from src.embeddings.encoder import Qwen3EmbeddingEncoder

encoder = Qwen3EmbeddingEncoder(model_name="Qwen/Qwen3-Embedding-0.6B", device="mps")
result = encoder.encode("query")
```

**After (CURRENT)**:
```python
from app.embeddings.local_encoder import LocalEmbeddingProvider

provider = LocalEmbeddingProvider(model_name="Qwen/Qwen3-Embedding-0.6B", device="mps")
result = provider.encode("query")
```

**Production (RECOMMENDED)**:
```python
from app.embeddings.factory import EmbeddingProviderFactory
from app.config import settings

provider = EmbeddingProviderFactory.create_provider(settings)
result = provider.encode("query")
```

### For Retrieval Strategies

**Before**:
```python
from src.embeddings.encoder import Qwen3EmbeddingEncoder

def __init__(self, pool: DatabasePool, encoder: Qwen3EmbeddingEncoder):
    self.encoder = encoder
```

**After**:
```python
from app.embeddings.local_encoder import LocalEmbeddingProvider

def __init__(self, pool: DatabasePool, encoder: LocalEmbeddingProvider):
    self.encoder = encoder
```

---

## Testing

### Unit Testing

```python
import pytest
from app.embeddings.local_encoder import LocalEmbeddingProvider

def test_local_provider():
    provider = LocalEmbeddingProvider()

    # Test single text
    embedding = provider.encode("test query")
    assert embedding.shape == (1024,)

    # Test multiple texts
    embeddings = provider.encode(["query 1", "query 2"])
    assert len(embeddings) == 2
    assert embeddings[0].shape == (1024,)

    # Test metadata
    assert provider.get_provider_name() == "local_qwen3"
    assert provider.get_embedding_dimension() == 1024

    # Test validation
    provider.validate_dimension(1024)  # Should pass

    with pytest.raises(ValueError):
        provider.validate_dimension(768)  # Should raise
```

### Integration Testing

```python
from app.embeddings.factory import EmbeddingProviderFactory
from app.config import settings

async def test_provider_factory():
    # Test factory creates correct provider
    provider = EmbeddingProviderFactory.create_provider(settings)
    assert provider.get_provider_name() == "local_qwen3"

    # Test encoding works
    embedding = provider.encode("test")
    assert embedding.shape == (1024,)
```

---

## Troubleshooting

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'src.embeddings'`

**Solution**: Update imports to use `app.embeddings.local_encoder`

### Configuration Errors

**Error**: `ValueError: Invalid embedding_provider: 'invalid'`

**Solution**: Set `EMBEDDING_PROVIDER` to one of: `local`, `openrouter`, `aliyun`

### Dimension Mismatch

**Error**: `ValueError: Provider local_qwen3 returns 1024-dim embeddings, but database expects 768-dim`

**Solution**: Your database was indexed with a different embedding model. Re-index with current model or update `embedding_dim` in config.

---

## Best Practices

1. **Use Factory Pattern**: Always use `EmbeddingProviderFactory.create_provider()` in production
2. **Validate Early**: Factory automatically validates dimension - no manual validation needed
3. **Environment Configuration**: Use `.env` files for configuration, not hardcoded values
4. **Type Hints**: All providers follow `EmbeddingProvider` protocol for type safety
5. **Error Handling**: Provider methods raise clear exceptions - catch and handle appropriately

---

## Future: Cloud Providers (Phase 3)

Coming soon (not yet implemented):

### OpenRouter Provider
```python
# Future usage
EMBEDDING_PROVIDER=openrouter
OPENAI_API_KEY=your_key_here

provider = EmbeddingProviderFactory.create_provider(settings)
# Uses OpenRouter API with Qwen3-Embedding-0.6B
```

### Aliyun Provider
```python
# Future usage
EMBEDDING_PROVIDER=aliyun
ALIYUN_API_KEY=your_key_here

provider = EmbeddingProviderFactory.create_provider(settings)
# Uses Aliyun text-embedding-v4
```

---

## Summary

- **Current**: Local Qwen3 provider working through new abstraction
- **Migration**: Update imports from `src.embeddings.encoder` to `app.embeddings.local_encoder`
- **Configuration**: Use `.env` file with `EMBEDDING_PROVIDER=local`
- **Production**: Use `EmbeddingProviderFactory.create_provider(settings)`
- **Future**: OpenRouter and Aliyun providers coming in Phase 3
