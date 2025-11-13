# Feature Specification: Cloud-Based Embedding Refactoring

**Feature Branch**: `004-cloud-embedding-refactor`
**Created**: 2025-11-12
**Updated**: 2025-11-12
**Status**: Draft
**Input**: User description: "Refactor embedding architecture to support cloud-based endpoints (OpenRouter and Aliyun text-embedding-v4) with provider abstraction, move Qwen3EmbeddingEncoder from src to app folder, and add configuration parameter for selecting embedding provider"

## Clarifications

### Session 2025-11-12

- Q: What database migration strategy should be used for renaming `vector_chunks`? → A: No migration or table renaming. System is in dev/experimentation stage for comparing embedding models. Add `table_name` configuration parameter in config.py. Each embedding model variant gets its own table (e.g., "qwen_local_vector", "qwen_openrouter_vector", "text_embedding_v4_vector") for A/B testing and performance comparison. Switch between tables by changing `table_name` config parameter.

- Q: What automated metrics should be tracked for comparing embedding model performance across different table configurations? → A: No automated metrics tracking needed for model comparison. Comparison will be done through manual review of sample queries and user feedback. Metrics collection for model experimentation is out of scope for this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seamless Provider Switching (Priority: P1)

System operators need to switch between different embedding providers (local Qwen3 model, OpenRouter API, or Aliyun text-embedding-v4) without code changes, only by updating configuration parameters. This enables cost optimization, performance tuning, and disaster recovery scenarios.

**Why this priority**: Core infrastructure change that enables all other capabilities. Without provider abstraction, adding cloud endpoints would create technical debt and inflexible architecture.

**Independent Test**: Can be fully tested by:
1. Configuring different embedding providers in config.py
2. Restarting the service
3. Verifying that queries return semantically equivalent results (>95% retrieval overlap for identical queries)
4. Measuring response time differences between providers

**Acceptance Scenarios**:

1. **Given** system is configured to use local Qwen3 embedding, **When** operator changes config to OpenRouter provider and restarts service, **Then** system successfully initializes with OpenRouter API (base_url: https://openrouter.ai/api/v1) using OpenAI client with model "qwen/qwen3-embedding-0.6b" and generates dense embeddings via API calls without errors
2. **Given** system is running with OpenRouter provider, **When** operator changes config to Aliyun text-embedding-v4 provider and restarts service, **Then** system successfully switches to Aliyun OpenAI-compatible API (base_url: https://dashscope.aliyuncs.com/compatible-mode/v1) using OpenAI client with model "text-embedding-v4" and retrieval results remain semantically consistent (>95% overlap with previous results)
3. **Given** system is configured with invalid API credentials for cloud provider, **When** service starts, **Then** system fails fast with clear error message indicating authentication failure (HTTP 401/403) and specific provider name (OpenRouter or Aliyun)
4. **Given** embedding provider configuration is missing or invalid (not in ["local", "openrouter", "aliyun"]), **When** service starts, **Then** system logs clear error message with valid options and exits with non-zero status code

---

### Edge Cases

- **What happens when cloud API endpoint is unreachable (network outage, rate limiting)?**
  - System retries with exponential backoff (3 attempts: 2s, 4s, 8s delays)
  - After retries exhausted, system logs error with provider name, API endpoint, and HTTP status code
  - For retrieval queries: return error response to user with retry suggestion
  - For indexing: mark batch as failed and continue with next batch (resumable indexing)

- **How does system handle embedding dimension mismatches when switching providers?**
  - All providers use 1024-dimensional dense embeddings (local Qwen3-Embedding-0.6B, OpenRouter Qwen3-Embedding-0.6B, Aliyun text-embedding-v4)
  - Validation: System checks embedding dimension at startup against database schema
  - Error: If mismatch detected, fail fast with clear error message indicating expected vs actual dimensions
  - Migration path: If future provider with different dimensions is added, require database re-indexing before switching

- **What happens when API key is valid but quota/credits are exhausted?**
  - Detect HTTP 429 (rate limit) or 402 (payment required) status codes
  - Log clear error message: "Provider [name] quota exceeded, check provider dashboard at [URL]"
  - For retrieval: return error to user with actionable message
  - For batch indexing: pause processing and alert operator (do not silently fail)

- **How does system handle partial failures in batch processing (e.g., 5 out of 10 texts fail)?**
  - Continue processing successful texts in batch
  - Log failed texts with error details (text index, error message, HTTP status code)
  - Return partial results with clear indication of which texts failed
  - Provide retry mechanism for failed texts only (avoid re-processing successes)

- **What happens when provider returns embeddings with unexpected format or structure?**
  - Validate response schema against expected format (JSON structure, array dimensions, data types)
  - If validation fails, log detailed error with actual response structure and expected format
  - Raise exception with clear message indicating provider name and specific validation failure
  - Do not silently coerce data to unexpected shapes or dimensions

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an abstract interface that defines standard embedding operations (encode text → generate embedding, get embedding dimension, get provider name) independent of provider implementation
- **FR-002**: System MUST implement three concrete embedding providers:
  - **Local provider**: Uses Qwen3EmbeddingEncoder for on-device embedding generation (1024-dim dense embeddings)
  - **OpenRouter provider**: Calls OpenRouter API endpoint (`https://openrouter.ai/api/v1/embeddings`) using OpenAI-compatible API format with model "qwen/qwen3-embedding-0.6b" (1024-dim dense embeddings)
  - **Aliyun provider**: Calls Aliyun DashScope OpenAI-compatible API endpoint (`https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`) using OpenAI client with model "text-embedding-v4" (1024-dim dense embeddings)

- **FR-003**: System MUST move `Qwen3EmbeddingEncoder` from `src/embeddings/encoder.py` to `app/embeddings/local_encoder.py` to align with architectural principle that `app/` contains core service components and `src/` contains preprocessing utilities

- **FR-004**: System MUST update all import statements across codebase (retrieval modules, indexing scripts, tests) to reflect new local encoder location (`from app.embeddings.local_encoder import Qwen3EmbeddingEncoder`)

- **FR-005**: System MUST add configuration parameter `embedding_provider` in `app/config.py` with allowed values: `["local", "openrouter", "aliyun"]` (default: `"local"` for backward compatibility)

- **FR-006**: System MUST add configuration parameter `table_name` in `app/config.py` to specify which database table to use for vector storage and retrieval. Examples: `"qwen_local_vector"`, `"qwen_openrouter_vector"`, `"text_embedding_v4_vector"`. Default: `"vector_chunks"` for backward compatibility.

- **FR-007**: System MUST validate `embedding_provider` and `table_name` values at startup and fail fast with clear error message listing valid options if values are invalid or missing

- **FR-008**: OpenRouter provider MUST use OpenAI-compatible API format:
  - API base URL: `https://openrouter.ai/api/v1`
  - Model name: `"qwen/qwen3-embedding-0.6b"`
  - Client: Use standard OpenAI Python client with custom `base_url` parameter
  - Authentication: API key from `openai_api_key` config (same key used for LLM calls)
  - Request parameters: `{"model": "qwen/qwen3-embedding-0.6b", "input": [texts]}`

- **FR-009**: Aliyun provider MUST use OpenAI-compatible API format:
  - API base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - Model name: `"text-embedding-v4"`
  - Client: Use standard OpenAI Python client with custom `base_url` parameter
  - Authentication: API key from `aliyun_api_key` config (environment variable: `DASHSCOPE_API_KEY`)
  - Request parameters: `{"model": "text-embedding-v4", "input": text, "dimensions": 1024, "encoding_format": "float"}`
  - Returns dense embeddings (1024-dim float array)

- **FR-010**: System MUST support configurable table name for vector storage via `table_name` parameter:
  - Each embedding model variant uses dedicated table (e.g., "qwen_local_vector", "qwen_openrouter_vector", "text_embedding_v4_vector")
  - Table schema: chunk_id (primary key), chunk_text, embedding (vector 1024), source_document, chapter_title, section_title, summary, token_count
  - Indexing: chunk_id as primary key, source_document as secondary index
  - Table selection: Based on `table_name` configuration parameter

- **FR-011**: System MUST implement dense embedding query strategy:
  - Query configured table using cosine similarity search (`1 - (embedding <=> query_embedding)`)
  - Single table active at a time (no cross-table queries or result merging)

- **FR-012**: System MUST handle API authentication failures gracefully:
  - Detect HTTP 401/403 status codes from OpenRouter or Aliyun APIs
  - Log clear error message with provider name, API endpoint, and authentication issue description
  - Fail fast on startup rather than during first query (validate credentials during initialization)

- **FR-013**: System MUST implement retry logic for transient API failures:
  - Retry mechanism: 3 attempts with exponential backoff (2s, 4s, 8s delays)
  - Retry conditions: HTTP 5xx errors, network timeouts, connection errors
  - Non-retry conditions: HTTP 4xx errors (except 429 rate limit), authentication failures (401/403)
  - Log each retry attempt with attempt number, wait duration, and error details

- **FR-014**: System MUST log API call metrics for cloud providers:
  - Request timestamp (ISO 8601 format)
  - Provider name and model name
  - Token count (input tokens from response `usage` object)
  - Response time (milliseconds from request start to response received)
  - Success/failure status (HTTP status code)
  - Error details if failed (error message, error type, HTTP body)

- **FR-015**: System MUST maintain consistent interface across all providers:
  - `encode(texts: Union[str, List[str]]) -> np.ndarray` for dense embeddings (all providers)
  - `get_embedding_dimension() -> int` for dimension introspection (returns 1024 for all providers)
  - `get_provider_name() -> str` for logging and debugging

- **FR-016**: System MUST support batch processing for cloud providers:
  - Batch size limits: OpenRouter (no explicit limit, use 100 as default), Aliyun (no explicit limit, use 100 as default)
  - Automatic batch splitting if input exceeds provider limit
  - Preserve order of results to match input order after batch processing
  - Log batch processing progress for long-running operations (e.g., "Processing batch 3/10")

- **FR-017**: System MUST validate embedding dimensions match database schema:
  - Check dimension at provider initialization by encoding test string
  - Compare against database vector column dimension from config (`embedding_dim` parameter)
  - Fail fast if mismatch detected with clear error message: "Provider [name] returns [actual]-dim embeddings, but database expects [expected]-dim. Database re-indexing required."

### Key Entities *(include if feature involves data)*

- **EmbeddingProvider (Abstract Interface)**: Defines contract for all embedding providers with methods: `encode()`, `get_embedding_dimension()`, `get_provider_name()`. Ensures consistent interface across local and cloud implementations.

- **LocalEmbeddingProvider**: Concrete provider wrapping Qwen3EmbeddingEncoder for on-device embedding generation. Attributes: model instance, device (MPS/CUDA/CPU), batch size, normalization settings. Generates 1024-dim dense embeddings.

- **OpenRouterEmbeddingProvider**: Concrete provider for OpenRouter API using OpenAI client. Attributes: API base URL (https://openrouter.ai/api/v1), API key, model name ("qwen/qwen3-embedding-0.6b"), retry configuration, request timeout settings. Uses standard OpenAI Python client with custom base_url parameter. Generates 1024-dim dense embeddings.

- **AliyunEmbeddingProvider**: Concrete provider for Aliyun text-embedding-v4 using OpenAI-compatible API. Attributes: API key, model name ("text-embedding-v4"), batch size, dimension (1024). Uses OpenAI client with base_url https://dashscope.aliyuncs.com/compatible-mode/v1. Generates 1024-dim dense embeddings.

- **EmbeddingProviderConfig**: Configuration data structure containing provider selection and provider-specific settings. Fields: `embedding_provider` (local/openrouter/aliyun), API credentials (`openai_api_key`, `aliyun_api_key`), `table_name`, retry settings, timeout values.

- **EmbeddingResponse**: Response structure for embeddings. Fields: `embedding` (np.ndarray of shape (1024,)), `dimension` (int), `metadata` (token count, response time, provider name).

- **VectorChunk**: Database entity for vector storage. Fields: chunk_id, chunk_text, embedding (vector 1024), source_document, chapter_title, section_title, summary, token_count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System startup time remains under 10 seconds when switching between providers (measured from config load to ready state), ensuring operational efficiency during provider changes

- **SC-002**: Embedding generation latency for cloud providers (OpenRouter, Aliyun) is under 500ms for single text queries (95th percentile) and under 2000ms for batch processing (10 texts), providing acceptable user experience for real-time retrieval and indexing

- **SC-003**: Retrieval accuracy maintains >95% precision@5 overlap when switching between providers for identical queries on same corpus, ensuring semantic consistency across provider implementations

- **SC-004**: System successfully handles API failures with graceful degradation: 100% of transient failures (HTTP 5xx, network timeouts) trigger retry logic with exponential backoff, and 100% of permanent failures (HTTP 4xx, auth errors) fail fast with actionable error messages within 500ms

- **SC-005**: Code organization improvement: All `app/` modules (retrieval, agents, API endpoints) import embedding functionality from `app/embeddings/` namespace, eliminating cross-boundary imports from `src/` folder (validated by static analysis: `grep -r "from src" app/` returns zero results)

- **SC-006**: Provider switching requires zero code changes: operators configure provider selection through `app/config.py` parameters only (`embedding_provider`, `table_name`), deploy configuration change, and restart service to activate new provider

- **SC-007**: All providers successfully generate 1024-dimensional embeddings with dimension validation: embeddings consistently return 1024 dimensions (measured on sample of 100 medical/technical documents)

- **SC-008**: Retrieval queries correctly target the configured table specified by `table_name` parameter: system queries only the configured table (e.g., "qwen_local_vector", "qwen_openrouter_vector", "text_embedding_v4_vector") with no cross-table queries or result merging (validated by query logs showing single table access per retrieval request matching configured `table_name`)

## Assumptions

- **Database schema assumption**: System is in dev/experimentation stage for comparing embedding models. Multiple tables coexist with different embedding model variants (e.g., "qwen_local_vector", "qwen_openrouter_vector", "text_embedding_v4_vector"). All tables have identical schema: chunk_id (PK), chunk_text, embedding (vector 1024), source_document, chapter_title, section_title, summary, token_count. Operators switch between tables using `table_name` config parameter for A/B testing. No migration or table renaming required.

- **API endpoint assumption**: OpenRouter and Aliyun API endpoints are stable and will not change frequently. If endpoint URLs change, configuration parameters (`openrouter_api_base`, `aliyun_api_base`) will be added to `app/config.py` for flexibility.

- **API compatibility assumption**: Both OpenRouter and Aliyun use OpenAI-compatible API format, allowing unified implementation with standard OpenAI Python client. Only difference is base_url and model name parameters.

- **Network reliability assumption**: Cloud providers (OpenRouter, Aliyun) are expected to have >99% uptime. For production deployments with strict SLA requirements, consider implementing circuit breaker patterns or fallback to local provider on repeated cloud failures (out of scope for initial implementation).

- **Single-table retrieval assumption**: System queries only one table at a time based on `table_name` configuration. Hybrid retrieval (querying multiple tables and merging results) is out of scope for this implementation.

- **Configuration management assumption**: Provider configuration changes require service restart. Live configuration reload (hot-swapping providers) is out of scope for initial implementation. Graceful restart strategy ensures zero downtime for production deployments.

- **Model compatibility assumption**: All providers support text inputs up to 8196 tokens (Qwen3's max_length, Aliyun's documented limit). Longer inputs will be truncated by tokenizer before sending to provider. OpenRouter inherits same limit from Qwen3-Embedding-0.6B model.

- **Authentication security assumption**: API keys are stored in `.env` file and loaded through pydantic-settings. Production deployments should use secret management services (e.g., HashiCorp Vault, AWS Secrets Manager) for enhanced security. Aliyun API key is separate from OpenRouter/OpenAI key to allow independent credential rotation.

- **Batch processing assumption**: OpenRouter and Aliyun have no documented batch size limits. System uses default batch size of 100 for cloud providers for efficiency.
