# Implementation Plan: Semantic Search with PostgreSQL and pgvector

**Branch**: `002-semantic-search` | **Date**: 2025-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-semantic-search/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Replace the existing FAISS-based in-memory retrieval system with PostgreSQL + pgvector semantic search. The system will index 500+ chunked medical documents using Qwen3-Embedding-0.6B (Apple MPS optimized), store embeddings in PostgreSQL with pgvector, and integrate with the existing LangGraph RAG agent through a drop-in PostgreSQLRetriever that implements the DocumentRetriever interface. Includes Qwen3-Reranker-0.6B for result reranking. BM25 hybrid search is deferred.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: transformers, torch (MPS support), psycopg2/asyncpg, pgvector, sentence-transformers, LangGraph, FastAPI
**Storage**: PostgreSQL 15+ with pgvector extension
**Testing**: pytest, pytest-cov (≥80% unit, ≥70% integration)
**Target Platform**: macOS (Apple Silicon MPS) for development, Linux for production
**Project Type**: Single project (backend service with CLI tooling)
**Performance Goals**: <30min indexing for 500+ chunks, <3s search queries (p95), <2s reranking (p95)
**Constraints**: Apple MPS compatibility required, must implement DocumentRetriever interface, no modifications to RAG agent code
**Scale/Scope**: 500+ medical document chunks, single-model embedding (Qwen3-Embedding-0.6B), production-ready indexing pipeline

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Agent-First Architecture ✅ PASS
**Status**: Compliant
- PostgreSQLRetriever implemented as standalone component with clear DocumentRetriever interface
- Indexing pipeline is separate standalone script (not part of agent)
- RAG agent remains unchanged, retriever injected via closure pattern
- Clear boundaries: indexing (offline batch) vs search (runtime agent capability)

### Principle II: State Management Discipline ✅ PASS
**Status**: Compliant
- No new state fields required in MedicalChatState (retriever injected, not stored in state)
- Search results flow through existing state.documents field
- PostgreSQLRetriever maintains no session state (stateless search operations)
- Database connection management separate from agent state

### Principle III: Test-First Development (NON-NEGOTIABLE) ⚠️ NEEDS ATTENTION
**Status**: Requires strict adherence during implementation
- Contract tests MUST be written first: DocumentRetriever interface compliance, database schema contracts
- Integration tests MUST be written before implementation: indexing pipeline end-to-end, search + rerank workflows
- Unit tests for: embedding generation, vector operations, error handling
- **Action**: User approval of test scenarios required before implementation begins

### Principle IV: Observability & Debugging ✅ PASS
**Status**: Implementation plan includes observability
- Structured logging required: session_id in search operations, chunk_id in indexing
- Error boundaries: embedding failures (log and continue), database connection errors (retry with exponential backoff)
- Performance metrics: indexing throughput, search latency, reranking time
- State inspection: search results with similarity scores, metadata for debugging relevance

### Principle V: Abstraction & Dependency Injection ✅ PASS
**Status**: Compliant
- PostgreSQLRetriever implements abstract DocumentRetriever interface
- Database connection via environment-based configuration (Pydantic Settings)
- Embedding model abstraction allows swapping Qwen3 for alternatives
- Docker-based local setup + externally managed production database

### Principle VI: Simplicity & Modularity (YAGNI) ⚠️ ATTENTION NEEDED
**Status**: Compliant with noted complexity
- Starting simple: semantic search only, BM25 deferred
- Reranker is mandatory: user requirement for production-quality relevance (not optional)
- Docker setup adds complexity: justified by production requirement for external database management
- **Complexity Justified**: Separate indexing script (offline batch vs real-time), reranker (user-specified mandatory requirement)

### Compliance Summary
**Pre-Research Status**: 4 PASS, 2 NEEDS ATTENTION
- ✅ Architecture, state management, abstraction, observability meet standards
- ⚠️ TDD discipline must be enforced: test scenarios require user approval
- ⚠️ Complexity justified but monitor: reranker and Docker setup are necessary complexity

**Post-Design Re-evaluation**: ✅ CONSTITUTION COMPLIANT

**Design Artifacts Completed**:
- ✅ research.md: All technical unknowns resolved with evidence-based decisions
- ✅ data-model.md: 6 entities defined with Pydantic validation, clear relationships
- ✅ contracts/: 3 contracts (retriever_interface.py, database_schema.sql, indexing_cli.md)
- ✅ quickstart.md: 15-20 minute setup guide with troubleshooting

**Constitution Re-evaluation Results**:

### Principle I: Agent-First Architecture ✅ STRENGTHENED
**Design Impact**: PostgreSQLRetriever contract explicitly defines DocumentRetriever interface compatibility. Clear separation between indexing pipeline (CLI) and search capability (retriever). No modifications to RAG agent required.

### Principle II: State Management Discipline ✅ CONFIRMED
**Design Impact**: SearchQuery and SearchResult models defined with Pydantic validation. No new state fields in MedicalChatState (retriever remains injected via closure). Database connection management isolated from agent state.

### Principle III: Test-First Development (NON-NEGOTIABLE) ✅ CONTRACT-DEFINED
**Design Impact**: Contracts explicitly document test requirements:
- retriever_interface.py: 7 contract test categories (interface compliance, async behavior, return type validation, error handling, metadata compatibility, filter support, ranking behavior)
- database_schema.sql: 5 validation categories (schema validation, index validation, vector operations, data integrity, timestamp behavior)
- indexing_cli.md: 8 test requirements (command availability, argument validation, output format, error handling, exit codes, config validation, performance, idempotency)

**Action Required**: User approval of test scenarios before implementation begins (as noted in initial evaluation).

### Principle IV: Observability & Debugging ✅ DETAILED
**Design Impact**:
- EmbeddingConfig and RerankerConfig models include device and batch_size for performance monitoring
- SearchResult model includes both similarity_score and rerank_score for debugging relevance
- Database schema includes created_at and updated_at timestamps for tracking
- CLI contract specifies error logging to indexing_errors.log

### Principle V: Abstraction & Dependency Injection ✅ VALIDATED
**Design Impact**:
- PostgreSQLRetriever implements abstract DocumentRetriever interface (contract-defined)
- EmbeddingConfig and RerankerConfig support multiple devices (mps, cuda, cpu) via configuration
- Database connection via environment variables (Pydantic Settings pattern in quickstart)
- Docker-based local setup documented in quickstart.md

### Principle VI: Simplicity & Modularity (YAGNI) ✅ MAINTAINED
**Design Impact**:
- Data model limited to 6 core entities (no speculative features)
- Single table design (vector_chunks) with HNSW index
- CLI with 4 essential commands (index, reindex, validate, stats)
- Reranker complexity justified: user requirement, mandatory for production-quality relevance

**Complexity Assessment**:
- No new complexity introduced beyond initial plan
- Reranker is mandatory (always enabled, not optional)
- Docker setup complexity justified: production requirement for external database management
- All entities map directly to functional requirements (no gold-plating)

**Final Status**: ✅ ALL PRINCIPLES SATISFIED
- No constitution violations detected in design
- Contract tests define clear quality gates
- Implementation can proceed to Phase 2 (/speckit.tasks)

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── embeddings/              # NEW: Embedding and indexing pipeline
│   ├── __init__.py
│   ├── models.py            # EmbeddingConfig, ChunkMetadata, VectorDocument
│   ├── encoder.py           # Qwen3EmbeddingEncoder (MPS support)
│   ├── reranker.py          # Qwen3Reranker
│   ├── indexer.py           # Batch indexing pipeline
│   └── cli.py               # CLI commands: index, reindex, validate
│
├── vector_store/            # NEW: PostgreSQL + pgvector integration
│   ├── __init__.py
│   ├── postgres_retriever.py # PostgreSQLRetriever (DocumentRetriever impl)
│   ├── schema.py            # Database schema, migrations
│   └── connection.py        # Connection pooling, retry logic
│
└── core/
    ├── retriever.py         # EXISTING: DocumentRetriever interface
    └── models.py            # EXISTING: Document dataclass

tests/
├── contract/
│   ├── test_retriever_interface.py  # NEW: DocumentRetriever contract tests
│   └── test_database_schema.py      # NEW: Schema validation tests
│
├── integration/
│   ├── test_indexing_pipeline.py    # NEW: End-to-end indexing tests
│   ├── test_search_workflow.py      # NEW: Search + rerank integration
│   └── test_mps_acceleration.py     # NEW: Apple MPS compatibility tests
│
└── unit/
    ├── test_encoder.py               # NEW: Embedding generation tests
    ├── test_reranker.py              # NEW: Reranking logic tests
    ├── test_postgres_retriever.py    # NEW: Retriever unit tests
    └── test_vector_operations.py     # NEW: Vector similarity tests

scripts/
└── setup_postgres.sh        # NEW: Docker-based PostgreSQL + pgvector setup

data/
└── chunking_final/          # EXISTING: 500+ chunk JSON files
    ├── medications/
    ├── chapters/
    └── videos/
```

**Structure Decision**: Single project structure (Option 1) selected. This feature adds two new modules (`src/embeddings/` for indexing pipeline, `src/vector_store/` for database integration) alongside existing `src/core/` infrastructure. The separation reflects offline indexing vs runtime retrieval concerns. Docker setup isolated in `scripts/` for local development environment.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
