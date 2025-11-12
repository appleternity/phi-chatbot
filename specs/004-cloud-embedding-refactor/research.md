# Phase 0 Research: Cloud-Based Embedding Refactoring

**Branch**: `004-cloud-embedding-refactor` | **Date**: 2025-11-12

## Research Tasks

### 1. OpenRouter API Integration Pattern

**Decision**: Use OpenAI Python client with custom `base_url` parameter for OpenRouter API integration

**Rationale**:
- OpenRouter provides OpenAI-compatible embedding API endpoint (`https://openrouter.ai/api/v1/embeddings`)
- Same model available on OpenRouter: `qwen/qwen3-embedding-0.6b` (matching local Qwen3-Embedding-0.6B)
- Standard OpenAI client supports custom base URL without additional HTTP client implementation
- Reduces code duplication and leverages OpenAI client's built-in retry, timeout, and error handling

**Implementation Pattern**:
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openai_api_key,  # Same key used for LLM calls
)

response = client.embeddings.create(
    model="qwen/qwen3-embedding-0.6b",
    input=texts,  # List[str] or str
)

embeddings = [item.embedding for item in response.data]
```

**API Response Format** (OpenAI-compatible):
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.123, -0.456, ...]  // 1024-dimensional array
    }
  ],
  "model": "qwen/qwen3-embedding-0.6b",
  "usage": {
    "prompt_tokens": 42,
    "total_tokens": 42
  }
}
```

**Error Handling**:
- HTTP 401/403: Authentication failure (invalid API key)
- HTTP 429: Rate limit exceeded
- HTTP 500+: Server-side errors (retry with exponential backoff)
- Network errors: Connection timeout, DNS failure (retry with exponential backoff)

**Alternatives Considered**:
- ❌ Custom HTTP client using `requests` library: More code, duplicates OpenAI client features
- ❌ Direct REST API calls with `httpx`: Similar to requests, lacks OpenAI client's conveniences
- ✅ OpenAI client with custom base_url: Minimal code, standard patterns, built-in error handling

---

### 2. Aliyun DashScope API Integration Strategy

**Decision**: Use OpenAI-compatible endpoint with OpenAI client for Aliyun text-embedding-v4

**Rationale**:
- Aliyun provides OpenAI-compatible endpoint: `https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`
- Same OpenAI client pattern as OpenRouter (minimal code, consistent implementation)
- Leverages OpenAI client's built-in retry, timeout, and error handling
- Separate API key (`aliyun_api_key`) from OpenRouter/OpenAI for independent credential rotation

**Implementation Pattern**:
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=settings.aliyun_api_key,  # Separate from openai_api_key
)

response = client.embeddings.create(
    model="text-embedding-v4",
    input=text,  # Single str or List[str]
    dimensions=1024,  # Required parameter
    encoding_format="float",  # float or base64
)

embeddings = [item.embedding for item in response.data]
```

**API Response Format** (OpenAI-compatible):
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.234, -0.567, ...]  // 1024-dimensional array
    }
  ],
  "model": "text-embedding-v4",
  "usage": {
    "prompt_tokens": 42,
    "total_tokens": 42
  }
}
```

**Error Handling**:
- HTTP 401: Invalid API key (`DASHSCOPE_API_KEY` environment variable)
- HTTP 400: Invalid request parameters (missing required fields)
- HTTP 429: Rate limit exceeded (Aliyun quotas)
- HTTP 500+: Server-side errors (retry with exponential backoff)

**Alternatives Considered**:
- ❌ Native DashScope API: Requires custom HTTP client, more complex implementation
- ❌ Custom HTTP client using `requests` library: Duplicates OpenAI client features
- ✅ OpenAI client with custom base_url: Minimal code, identical pattern to OpenRouter

---

### 3. Embedding Dimension Validation Strategy

**Decision**: Validate embedding dimension at provider initialization by encoding test string and comparing against database schema

**Rationale**:
- All providers (local Qwen3, OpenRouter Qwen3, Aliyun text-embedding-v4) produce 1024-dimensional dense embeddings
- Dimension mismatch between provider and database causes runtime errors during insertion or retrieval
- Early validation (at startup) prevents cascading failures during query execution
- Test string encoding is lightweight (<100ms) and provides definitive dimension confirmation

**Implementation Pattern**:
```python
class EmbeddingProvider(Protocol):
    def validate_dimension(self, expected_dim: int) -> None:
        """
        Validate embedding dimension matches database schema.

        Args:
            expected_dim: Expected dimension from database schema (config.embedding_dim)

        Raises:
            ValueError: If actual dimension != expected dimension
        """
        # Encode test string to determine actual dimension
        test_embedding = self.encode_dense("test")
        actual_dim = len(test_embedding)

        if actual_dim != expected_dim:
            raise ValueError(
                f"Provider {self.get_provider_name()} returns {actual_dim}-dim embeddings, "
                f"but database expects {expected_dim}-dim. Database re-indexing required."
            )
```

**Validation Timing**:
- Provider initialization: Immediately after model loading or API client setup
- Service startup: Before FastAPI app accepts requests
- Configuration change: When switching providers via config update

**Error Messages**:
- Clear indication of dimension mismatch with actual vs. expected values
- Actionable guidance (database re-indexing required)
- Provider name included for multi-provider debugging

**Alternatives Considered**:
- ❌ Hardcode dimension checks: Brittle, breaks if providers change dimension defaults
- ❌ Skip validation and fail on insertion: Late detection, cascading failures, poor UX
- ✅ Runtime validation with test encoding: Definitive, early detection, clear error messages

---

### 4. Retry Logic Best Practices

**Decision**: Implement exponential backoff with jitter for transient API failures, no retry for client errors

**Rationale**:
- Cloud API failures are common (network timeouts, server overload, rate limiting)
- Exponential backoff prevents thundering herd problem during provider outages
- Jitter (random delay) distributes retry attempts across time to avoid synchronized spikes
- Client errors (4xx) should not be retried (invalid API key, malformed request)
- Rate limit errors (429) should be retried with longer backoff

**Implementation Pattern**:
```python
import time
import random
from typing import Callable, TypeVar

T = TypeVar("T")

def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 10.0,
) -> T:
    """
    Retry function with exponential backoff and jitter.

    Args:
        func: Function to retry
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 2.0)
        max_delay: Maximum delay in seconds (default: 10.0)

    Returns:
        Function result

    Raises:
        Exception: Last exception if all retries exhausted
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            # Don't retry on client errors (4xx except 429)
            if hasattr(e, "status_code"):
                if 400 <= e.status_code < 500 and e.status_code != 429:
                    logger.error(f"Client error {e.status_code}, not retrying: {e}")
                    raise

            # Last attempt, raise exception
            if attempt == max_retries:
                logger.error(f"All {max_retries} retries exhausted: {e}")
                raise

            # Calculate backoff with jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            total_delay = delay + jitter

            logger.warning(
                f"Retry {attempt + 1}/{max_retries} after {total_delay:.2f}s: {e}"
            )
            time.sleep(total_delay)
```

**Retry Conditions**:
- ✅ HTTP 5xx errors (server-side failures)
- ✅ HTTP 429 (rate limit exceeded)
- ✅ Network timeouts, connection errors, DNS failures
- ❌ HTTP 401/403 (authentication failures - permanent errors)
- ❌ HTTP 400 (bad request - permanent errors)
- ❌ HTTP 404 (not found - permanent errors)

**Backoff Schedule** (3 retries, base_delay=2s):
- Attempt 1: Immediate
- Attempt 2: 2s + jitter (0-0.2s)
- Attempt 3: 4s + jitter (0-0.4s)
- Attempt 4: 8s + jitter (0-0.8s)
- Total max delay: ~15s

**Alternatives Considered**:
- ❌ Fixed delay retry: Causes thundering herd, inefficient for distributed systems
- ❌ Retry all errors: Wastes time on permanent failures (auth errors, bad requests)
- ✅ Exponential backoff with jitter: Industry standard, proven pattern, prevents synchronization

---

### 5. Batch Processing Strategy

**Decision**: Provider-specific batch size limits with automatic splitting and order preservation

**Rationale**:
- Different providers have different batch size characteristics:
  - Local Qwen3: Memory-bound (default 16 for MPS)
  - OpenRouter: No documented limit (use 100 as safe default)
  - Aliyun: No documented limit (use 100 as safe default)
- Large batches improve throughput but risk hitting provider limits
- Automatic batch splitting abstracts provider differences from caller
- Order preservation is critical for aligning results with input texts

**Implementation Pattern**:
```python
def encode_dense_batch(
    self,
    texts: List[str],
    provider_batch_size: int,
) -> List[np.ndarray]:
    """
    Encode texts in batches with automatic splitting.

    Args:
        texts: List of texts to encode
        provider_batch_size: Maximum texts per API call (provider-specific)

    Returns:
        List of embeddings matching input order
    """
    all_embeddings = []
    num_batches = (len(texts) + provider_batch_size - 1) // provider_batch_size

    for i in range(0, len(texts), provider_batch_size):
        batch_texts = texts[i:i + provider_batch_size]
        batch_num = i // provider_batch_size + 1

        logger.info(
            f"Processing batch {batch_num}/{num_batches} "
            f"({len(batch_texts)} texts)"
        )

        # Call provider API with retry logic
        batch_embeddings = self._encode_api_call(batch_texts)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings
```

**Provider Batch Limits**:
- **LocalEmbeddingProvider**: `batch_size=16` (MPS default, configurable)
- **OpenRouterEmbeddingProvider**: `batch_size=100` (no documented limit, safe default)
- **AliyunEmbeddingProvider**: `batch_size=100` (no documented limit, safe default)

**Progress Logging**:
- Log batch number, total batches, texts in current batch
- INFO level for batch processing progress
- DEBUG level for individual embedding results

**Alternatives Considered**:
- ❌ Single batch size across all providers: Inefficient for providers with higher limits
- ❌ Expose batch limits to caller: Leaks provider implementation details
- ✅ Provider-specific limits with auto-splitting: Abstracts complexity, optimal performance

---

### 6. Migration Strategy from `src/embeddings/` to `app/embeddings/`

**Decision**: Move `src/embeddings/encoder.py` to `app/embeddings/local_encoder.py` and update all import statements

**Rationale**:
- Current architecture violates separation of concerns:
  - `src/`: Preprocessing utilities (chunking, indexing scripts)
  - `app/`: Core service components (retrieval, agents, API endpoints)
- Embedding provider is core service component (used by retrieval modules, API endpoints)
- Moving to `app/embeddings/` aligns with architectural principle that service components live in `app/`
- Enables consistent provider abstraction (all providers in same module)

**Migration Steps**:
1. Create `app/embeddings/` directory structure
2. Copy `src/embeddings/encoder.py` → `app/embeddings/local_encoder.py`
3. Wrap `Qwen3EmbeddingEncoder` in `LocalEmbeddingProvider` implementing `EmbeddingProvider` protocol
4. Update all import statements:
   - `app/retrieval/simple.py`: `from app.embeddings.local_encoder import LocalEmbeddingProvider`
   - `app/retrieval/rerank.py`: `from app.embeddings.local_encoder import LocalEmbeddingProvider`
   - `app/retrieval/advanced.py`: `from app.embeddings.local_encoder import LocalEmbeddingProvider`
   - `app/retrieval/factory.py`: `from app.embeddings.factory import EmbeddingProviderFactory`
5. Update tests:
   - `tests/unit/test_local_encoder.py`: Update import path
   - Add deprecation warning to `src/embeddings/encoder.py` (keep for backward compatibility)
6. Validate all imports with static analysis: `grep -r "from src.embeddings" app/` should return 0 results

**Backward Compatibility**:
- Keep `src/embeddings/encoder.py` with deprecation warning for external scripts
- Scripts in `src/` (chunking, indexing) can continue using old import path during transition
- Future cleanup: Remove `src/embeddings/encoder.py` after all scripts migrated

**Verification**:
```bash
# Check for cross-boundary imports (should return 0 results)
grep -r "from src" app/

# Check all tests pass with new import paths
pytest tests/unit/test_local_encoder.py -v
pytest tests/integration/ -v
```

**Alternatives Considered**:
- ❌ Keep encoder in src/, create wrapper in app/: Code duplication, maintenance burden
- ❌ Symlink from app/ to src/: Confusing, breaks architectural clarity
- ✅ Move to app/embeddings/, update imports: Clean, aligns with architecture, one-time migration

---

## Summary

### Technology Decisions

| Technology | Choice | Rationale |
|-----------|--------|-----------|
| OpenRouter API client | OpenAI Python client with custom base_url | OpenAI-compatible API, minimal code, built-in error handling |
| Aliyun API client | OpenAI Python client with custom base_url | OpenAI-compatible API, identical pattern to OpenRouter |
| Retry mechanism | Exponential backoff with jitter (3 retries: 2s, 4s, 8s) | Industry standard, prevents thundering herd, efficient |
| Batch processing | Provider-specific limits with auto-splitting | Optimal performance, abstracts complexity from caller |
| Dimension validation | Test string encoding at provider initialization | Early detection, prevents cascading failures, clear errors |
| Code organization | Move `src/embeddings/` → `app/embeddings/` | Aligns with architecture (app/ = service components) |

### Implementation Risks

| Risk | Mitigation |
|------|-----------|
| API authentication failures during startup | Fail fast with clear error messages, validate credentials before accepting requests |
| Dimension mismatch after provider switch | Dimension validation at initialization, prevent service startup if mismatch detected |
| Rate limiting during batch indexing | Exponential backoff with jitter, batch size limits, progress logging for long-running operations |
| Import path breaking changes | Update all imports atomically, keep backward compatibility shim in src/embeddings/encoder.py |

### Open Questions (Resolved)

All technical unknowns from plan.md Technical Context have been resolved:
- ✅ OpenRouter API integration pattern (OpenAI client with custom base_url)
- ✅ Aliyun API integration strategy (OpenAI client with custom base_url, identical to OpenRouter)
- ✅ Dimension validation approach (test string encoding at initialization)
- ✅ Retry logic best practices (exponential backoff with jitter, 3 retries)
- ✅ Batch processing strategy (provider-specific limits with auto-splitting)
- ✅ Migration path from src/ to app/ (atomic import updates, backward compatibility shim)
