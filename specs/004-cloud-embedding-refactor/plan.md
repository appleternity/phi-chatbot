# Implementation Plan: Cloud-Based Embedding Refactoring

**Branch**: `004-cloud-embedding-refactor` | **Date**: 2025-11-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-cloud-embedding-refactor/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Refactor embedding architecture to support cloud-based endpoints (OpenRouter and Aliyun text-embedding-v4) with provider abstraction, move Qwen3EmbeddingEncoder from src to app folder, and add configuration parameter for selecting embedding provider. This enables cost optimization, performance tuning, and disaster recovery scenarios through seamless provider switching without code changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.115+, LangGraph 0.6.0, LangChain-Core 0.3+, transformers, torch (MPS support), psycopg2/asyncpg, pgvector, sentence-transformers, openai (OpenAI Python client)
**Storage**: PostgreSQL 15+ with pgvector extension
**Testing**: pytest 8.3+, pytest-asyncio 0.24+, pytest-cov 6.0+
**Target Platform**: macOS (MPS), Linux (CUDA/CPU)
**Project Type**: Web application (FastAPI backend + retrieval service)
**Performance Goals**: <500ms single text query latency (p95), <2s batch processing (10 texts), <10s service startup
**Constraints**: Backward compatibility with local Qwen3 encoder, 1024-dim embeddings across all providers, single-table query strategy
**Scale/Scope**: 3 embedding providers (local, OpenRouter, Aliyun), all generating dense embeddings only, configurable table names for A/B testing, support for 10k+ documents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ I. Agent-First Architecture
**Status**: NOT APPLICABLE
**Rationale**: This feature is infrastructure-level (embedding provider abstraction), not agent functionality. No new agents or agent capabilities are introduced.

### ✅ II. State Management Discipline
**Status**: NOT APPLICABLE
**Rationale**: Feature does not introduce new agent state or StateGraph nodes. Embedding provider configuration is stateless service initialization.

### ✅ III. Test-First Development (NON-NEGOTIABLE)
**Status**: COMPLIANT - PENDING IMPLEMENTATION
**Plan**:
1. Contract tests: EmbeddingProvider interface (encode_dense, encode_sparse, get_embedding_dimension, get_provider_name)
2. Integration tests: Provider switching, API authentication, retry logic, batch processing
3. Unit tests: Configuration validation, dimension checking, error handling

**Test Design Sequence** (Phase 2 - `/speckit.tasks`):
- Contract tests → Integration tests → Unit tests
- TDD red-green-refactor cycle for each provider implementation

### ✅ IV. Observability & Debugging
**Status**: COMPLIANT - PENDING IMPLEMENTATION
**Plan**:
- Structured logging with context: provider name, model name, request timestamp, token count, response time
- Error boundaries: Authentication failures (401/403) fail fast with clear provider-specific messages
- Retry logic: 3 attempts with exponential backoff (2s, 4s, 8s) logged with attempt number and wait duration
- Performance metrics: API call latency, batch processing progress, dimension validation results

### ✅ V. Abstraction & Dependency Injection
**Status**: COMPLIANT - PENDING IMPLEMENTATION
**Plan**:
- Abstract EmbeddingProvider interface defining contract for all providers
- Configuration-based provider selection (dependency injection through factory pattern)
- Testable with mocks (OpenRouter/Aliyun API calls mocked in unit tests)

### ✅ VI. Simplicity & Modularity (YAGNI)
**Status**: COMPLIANT
**Justification**:
- **Why 3 providers**: Current system only supports local Qwen3. Business need for cloud providers is established (cost optimization, disaster recovery). OpenRouter provides same Qwen3 model via API (migration validation). Aliyun provides alternative dense embedding model for comparison (text-embedding-v4).
- **Simpler alternative rejected**: Starting with only OpenRouter would not validate if different embedding models (text-embedding-v4) maintain semantic consistency. Starting with only Aliyun would create vendor lock-in without API parity validation.
- **Complexity mitigation**: **All providers use OpenAI Python client with custom base_url** (no custom HTTP client needed). All providers implement identical interface (encode, get_embedding_dimension, get_provider_name). Total implementation: ~150 lines for cloud providers (~50 lines each).

### Summary (Pre-Phase 0)
**Gates Passed**: 6/6 applicable principles (all COMPLIANT)
**Violations**: NONE (sparse mode removed, all providers now use OpenAI client)
**Proceed to Phase 0**: YES

---

## Constitution Check (Post-Phase 1 Re-Evaluation)

*Re-evaluation after Phase 1 design (research.md, data-model.md, contracts/, quickstart.md completed)*

### ✅ I. Agent-First Architecture
**Status**: NOT APPLICABLE (unchanged from pre-Phase 0)
**Rationale**: Infrastructure-level feature, no agent functionality added

### ✅ II. State Management Discipline
**Status**: NOT APPLICABLE (unchanged from pre-Phase 0)
**Rationale**: No new agent state or StateGraph nodes

### ✅ III. Test-First Development (NON-NEGOTIABLE)
**Status**: COMPLIANT - DESIGN COMPLETE
**Updated Plan** (based on research.md findings):

**Contract Tests** (Phase 2 - First Priority):
- `test_embedding_provider_interface.py`:
  - Test all providers implement EmbeddingProvider protocol
  - Verify method signatures match protocol definition
  - Test dimension consistency (1024 for all providers)
  - Test provider name strings ("local_qwen3", "openrouter", "aliyun")

**Integration Tests** (Phase 2 - Second Priority):
- `test_provider_switching.py`:
  - Test config changes trigger correct provider initialization
  - Test dimension validation at provider initialization
  - Test service startup with each provider type
- `test_openrouter_provider.py`:
  - Test OpenAI client with custom base_url
  - Test retry logic with exponential backoff (mocked API failures)
  - Test batch processing with automatic splitting
- `test_aliyun_provider.py`:
  - Test Aliyun provider using OpenAI client with custom base_url
  - Test batch processing with automatic splitting
  - Test dense embedding format validation (1024-dim)

**Unit Tests** (Phase 2 - Third Priority):
- `test_embedding_factory.py`:
  - Test factory provider selection based on config
  - Test invalid provider type raises ValueError
  - Test missing API keys raise clear errors
- `test_config_validation.py`:
  - Test embedding_provider enum validation
  - Test required API keys based on provider type
  - Test table_name validation

**Test Design Complete**: All test scenarios identified in research.md and data-model.md

### ✅ IV. Observability & Debugging
**Status**: COMPLIANT - DESIGN COMPLETE
**Updated Plan** (based on research.md findings):

**Structured Logging**:
- Provider initialization: Log provider name, model name, device/API endpoint
- API calls: Log request timestamp, token count, response time, success/failure status
- Batch processing: Log batch number, total batches, texts in current batch
- Retry logic: Log attempt number, wait duration, error details

**Error Boundaries**:
- Authentication failures (401/403): Fail fast with provider name, API endpoint, error message
- Dimension mismatch: Clear error with actual vs. expected dimensions, actionable guidance
- Batch size errors: Provider-specific limits with clear constraint messages
- API failures: HTTP status code, error type, request_id (if available)

**Performance Metrics** (research.md defines targets):
- API call latency: <500ms for single text (p95), <2s for batch (10 texts)
- Dimension validation: <100ms test encoding during initialization
- Batch processing: Progress logging every batch (INFO level)

**Observability Design Complete**: All logging and error handling patterns defined

### ✅ V. Abstraction & Dependency Injection
**Status**: COMPLIANT - DESIGN COMPLETE
**Updated Plan** (based on data-model.md):

**Abstract Interface**: `EmbeddingProvider` protocol with 4 methods:
- `encode()`: Generate dense embeddings (all providers)
- `get_embedding_dimension()`: Return dimension (1024)
- `get_provider_name()`: Return provider identifier
- `validate_dimension()`: Check dimension match with database schema

**Dependency Injection**: `EmbeddingProviderFactory.create_provider(settings)` creates provider based on config
- Config-based selection (no hardcoded provider instantiation)
- Testable with mocks (API clients mocked in tests)
- Retrieval modules receive provider via factory (no direct instantiation)

**Abstraction Design Complete**: Protocol defined in contracts/embedding_provider_protocol.py

### ✅ VI. Simplicity & Modularity (YAGNI)
**Status**: COMPLIANT - COMPLEXITY ELIMINATED
**Updated Justification** (based on research.md + sparse removal):

**Complexity Removed**: Sparse mode eliminated from requirements (user decision)

**Simplified Design**:
1. **All providers use OpenAI client**: Local (wraps Qwen3), OpenRouter (Qwen3 API), Aliyun (text-embedding-v4 API)
2. **No custom HTTP client needed**: Aliyun now uses OpenAI-compatible endpoint (no native DashScope API)
3. **Total code impact**: ~150 lines for cloud providers (~50 lines each, identical pattern)

**Complexity Mitigation Achieved**:
- **ALL providers**: Same OpenAI client pattern with different base_url and model_name
- **NO special cases**: No sparse mode, no dual-mode provider, no custom HTTP client
- **Batch processing**: Identical across all providers
- **Retry logic**: Shared utility function (`retry_with_backoff()`)

**Simpler Alternatives Re-Evaluated**:
- ❌ Single cloud provider: Would not validate cross-provider semantic consistency or model comparison
- ✅ **Current design (dense-only)**: Minimal code, zero duplication, maximum simplicity

**Complexity Minimized**: Sparse removal eliminated all custom HTTP client code and dual-mode complexity

---

### Post-Phase 1 Summary
**Gates Passed**: 6/6 applicable principles (all COMPLIANT after sparse removal)
**Violations**: NONE (sparse mode eliminated, all providers use OpenAI client)
**Design Artifacts**: research.md, data-model.md, contracts/, quickstart.md ✅ COMPLETE (updated for dense-only)
**Agent Context**: CLAUDE.md updated with new technologies ✅ COMPLETE
**Proceed to Phase 2**: YES (ready for `/speckit.tasks` to generate implementation tasks)

## Project Structure

### Documentation (this feature)

```text
specs/004-cloud-embedding-refactor/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (OpenRouter API patterns, Aliyun API formats, migration strategy)
├── data-model.md        # Phase 1 output (EmbeddingProvider interface, provider configs, response structures)
├── quickstart.md        # Phase 1 output (setup guide, provider switching workflows)
├── contracts/           # Phase 1 output (EmbeddingProvider protocol, OpenRouter/Aliyun API schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
app/
├── embeddings/
│   ├── __init__.py                      # Export EmbeddingProviderFactory
│   ├── base.py                          # EmbeddingProvider abstract interface (Protocol)
│   ├── local_encoder.py                 # MOVED from src/embeddings/encoder.py (LocalEmbeddingProvider wrapping Qwen3EmbeddingEncoder)
│   ├── openrouter_provider.py           # NEW: OpenRouter embedding provider using OpenAI client
│   ├── aliyun_provider.py               # NEW: Aliyun text-embedding-v4 provider using OpenAI client
│   └── factory.py                       # NEW: EmbeddingProviderFactory for config-based provider selection
├── retrieval/
│   ├── simple.py                        # UPDATE: Import from app.embeddings.local_encoder
│   ├── rerank.py                        # UPDATE: Import from app.embeddings.local_encoder
│   ├── advanced.py                      # UPDATE: Import from app.embeddings.local_encoder
│   └── factory.py                       # UPDATE: Use EmbeddingProviderFactory
├── config.py                            # UPDATE: Add embedding_provider, aliyun_embedding_mode, aliyun_api_key, table_name

src/
└── embeddings/
    └── encoder.py                       # DEPRECATED: Move to app/embeddings/local_encoder.py

tests/
├── contract/
│   └── test_embedding_provider_interface.py   # NEW: Contract tests for EmbeddingProvider protocol
├── integration/
│   ├── test_provider_switching.py             # NEW: Test provider config changes and service restart
│   ├── test_openrouter_provider.py            # NEW: OpenRouter API integration tests (mocked responses)
│   └── test_aliyun_provider.py                # NEW: Aliyun API integration tests (dense + sparse modes)
└── unit/
    ├── test_local_encoder.py                  # UPDATE: Import from app.embeddings.local_encoder
    ├── test_embedding_factory.py              # NEW: Factory provider selection logic
    └── test_config_validation.py              # NEW: Configuration validation tests
```

**Structure Decision**: Web application structure with FastAPI backend. Embedding providers live in `app/embeddings/` (service components). Retrieval modules in `app/retrieval/` updated to use new import paths. Tests organized by contract/integration/unit hierarchy per Constitution principle III.

## Complexity Tracking

**NO VIOLATIONS** - Sparse mode removed, all providers use identical OpenAI client pattern

| Simplification | How Achieved | Benefit |
|----------------|--------------|---------|
| Removed dual-mode Aliyun provider | User decision to remove sparse embedding support | Eliminated custom HTTP client (~100 lines), single embedding mode only |
| Unified all providers with OpenAI client | All providers (local wrapper, OpenRouter, Aliyun) use OpenAI Python client | Zero code duplication, identical API patterns, minimal implementation (~50 lines per provider) |
| Single table schema | Removed sparse table schema and JSONB sparse_embedding column | Simplified database schema, single query strategy, no mode switching |
