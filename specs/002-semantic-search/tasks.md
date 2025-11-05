---

description: "Task list for semantic search implementation with PostgreSQL and pgvector"
---

# Tasks: Semantic Search with PostgreSQL and pgvector

**Input**: Design documents from `/specs/002-semantic-search/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in this feature specification, so test tasks are NOT included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Architecture Separation

**Offline Batch Indexing** (`src/embeddings/`):
- CLI tool for batch processing JSON files
- Embedding generation for indexing
- Not used by RAG agent at runtime

**Online Runtime Retrieval** (`app/core/`):
- PostgreSQLRetriever for query-time search
- Qwen3Reranker for result reranking
- Used by RAG agent for semantic search

**Shared Database** (`app/db/`):
- PostgreSQL schema and migrations
- Connection pooling utilities
- Used by both indexing and retrieval

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Docker database setup

- [X] T001 Install Python dependencies in requirements: transformers>=4.51.0, torch>=2.0.0, psycopg2-binary, asyncpg, typer, rich, tqdm, pydantic
- [X] T002 [P] Create Docker Compose configuration in docker-compose.yml for pgvector/pgvector:pg15 with volume persistence and healthcheck
- [X] T003 [P] Create environment variable template in .env.example with PostgreSQL connection settings (host, port, database, user, password)
- [X] T004 [P] Create Docker setup script in scripts/setup_postgres.sh with container startup, health checks, and initialization
- [X] T005 Create project structure: src/embeddings/, app/db/, app/core/ (extends existing), scripts/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Define batch indexing models in src/embeddings/models.py: ChunkMetadata, VectorDocument, EmbeddingConfig (Pydantic validation)
- [X] T007 [P] Create database schema in app/db/schema.py with CREATE TABLE vector_chunks (chunk_id, embedding vector(1024), metadata fields, timestamps)
- [X] T008 [P] Implement database connection pooling in app/db/connection.py with asyncpg pool management, retry logic, and health checks
- [ ] T009 Run database migration to create vector_chunks table with pgvector extension enabled
- [ ] T010 Create HNSW index on embedding column: CREATE INDEX USING hnsw (embedding vector_cosine_ops)
- [X] T011 [P] Implement Qwen3EmbeddingEncoder class in src/embeddings/encoder.py with MPS support, batch processing, and L2 normalization

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Index All Chunked Documents (Priority: P1) 🎯 MVP

**Goal**: Index all existing chunked medical documents from `data/chunking_final` into the vector database

**Independent Test**: Run indexing script against data directory and verify all chunks are stored in PostgreSQL with embeddings. Success measured by comparing count of JSON files to database records.

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement JSON chunk file parser in src/embeddings/indexer.py with ChunkMetadata extraction from chunk_text, source_document, chapter_title, section_title, subsection_title, summary, token_count fields
- [X] T013 [P] [US1] Implement batch embedding generation in src/embeddings/indexer.py using Qwen3EmbeddingEncoder with MPS acceleration and memory management
- [X] T014 [US1] Implement database insertion logic in src/embeddings/indexer.py with ON CONFLICT (chunk_id) DO NOTHING for duplicate handling
- [X] T015 [US1] Create CLI index command in src/embeddings/cli.py with --input (directory), --config (JSON), --batch-size, --skip-existing, --verbose arguments
- [X] T016 [US1] Add error handling to indexing pipeline: log failures to indexing_errors.log, continue processing remaining files, exit code 1 for partial failures
- [X] T017 [US1] Implement progress tracking with rich progress bar showing: current file, total progress, ETA, success/failure counts
- [X] T018 [US1] Create embedding configuration template in config/embedding_config.json with model_name: "Qwen/Qwen3-Embedding-0.6B", device: "mps", batch_size: 16, max_length: 1024, normalize_embeddings: true
- [X] T019 [US1] Add validation after indexing completes: verify chunk count matches files, check embedding dimensions are 1024, validate no NaN/infinity values
- [X] T020 [US1] Create metadata indexes on source_document and chapter_title columns for filtered search optimization

**Checkpoint**: At this point, all 500+ chunks should be indexed with embeddings in PostgreSQL and queryable

---

## Phase 4: User Story 2 - Query with Semantic Search (Priority: P1)

**Goal**: Enable natural language queries that return semantically relevant document chunks

**Independent Test**: Send natural language query to chat backend and verify returned chunks are semantically relevant. Example: "side effects of aripiprazole" should return aripiprazole side effects chunks.

### Implementation for User Story 2

- [X] T021 [P] [US2] Create runtime models in app/models.py or app/core/models.py: SearchQuery (query_text, query_embedding, top_k, filters, timestamp), SearchResult (chunk_id, content, metadata, similarity_score, rerank_score, rank)
- [X] T022 [P] [US2] Implement PostgreSQLRetriever class in app/core/postgres_retriever.py inheriting from DocumentRetriever with __init__(db_url, embedding_model, reranker_model)
- [X] T023 [US2] Implement async search() method in app/core/postgres_retriever.py: generate query embedding, execute pgvector similarity search with ORDER BY embedding <=> query_vector LIMIT top_k
- [X] T024 [US2] Implement VectorDocument to Document conversion in app/core/postgres_retriever.py: map chunk_id→id, chunk_text→content, metadata fields (source_document, chapter_title, section_title, subsection_title, summary, token_count, similarity_score)
- [X] T025 [US2] Add metadata filtering support in search() method: WHERE source_document = $filter OR chapter_title = $filter when filters parameter provided
- [X] T026 [US2] Implement connection pool lifecycle methods: async initialize() creates asyncpg pool (min_size=5, max_size=20), async close() cleans up pool
- [X] T027 [US2] Implement query embedding generation in PostgreSQLRetriever: load Qwen3-Embedding-0.6B model with MPS device, encode query text, L2 normalize, convert to list for pgvector
- [X] T028 [US2] Add error handling: raise ValueError for empty queries, ConnectionError for database failures, RuntimeError for embedding generation failures
- [X] T029 [US2] Update RAG agent initialization in app/graph/builder.py or app/main.py to use PostgreSQLRetriever instead of FAISSRetriever

**Checkpoint**: At this point, semantic search queries should return top-5 relevant chunks without reranking

---

## Phase 5: User Story 3 - Rerank Search Results (Priority: P2)

**Goal**: Improve search result quality by reranking top candidates with Qwen3-Reranker

**Independent Test**: Compare search results before and after reranking. Reranked results should show measurably better relevance scores.

### Implementation for User Story 3

- [X] T030 [P] [US3] Implement Qwen3Reranker class in app/core/qwen3_reranker.py with __init__(model_name="Qwen/Qwen3-Reranker-0.6B", device="mps", batch_size=8)
- [X] T031 [US3] Implement rerank() method in Qwen3Reranker: format (query, document) pairs with instruction template, tokenize with yes/no token IDs, compute logits, extract relevance scores
- [X] T032 [US3] Implement two-stage retrieval in PostgreSQLRetriever.search(): retrieve top_k * 4 candidates (e.g., 20 for top_k=5), pass to reranker, return top_k after reranking
- [X] T033 [US3] Add rerank_score to Document metadata alongside similarity_score for debugging and observability
- [X] T034 [US3] Sort final results by rerank_score (highest first) instead of similarity_score in search() method
- [X] T035 [US3] Add reranker lazy loading in PostgreSQLRetriever: initialize reranker only on first search() call to reduce startup time
- [X] T036 [US3] Optimize reranking performance: use batch_size=8, ensure <2s processing time for 20 candidates with profiling and logging

**Checkpoint**: All user stories should now be independently functional - search returns top-5 reranked results

---

## Phase 6: User Story 4 - Local Development Setup (Priority: P2)

**Goal**: Enable developers to set up vector database locally using Docker without external infrastructure

**Independent Test**: Run Docker setup script and verify PostgreSQL + pgvector database is accessible and ready to accept connections.

### Implementation for User Story 4

- [ ] T037 [P] [US4] Create initialization SQL script in scripts/init-scripts/01-init-pgvector.sql: CREATE EXTENSION vector, CREATE TABLE vector_chunks with all columns and constraints
- [ ] T038 [P] [US4] Add healthcheck configuration to docker-compose.yml: test with pg_isready command, interval 10s, timeout 5s, retries 5
- [ ] T039 [P] [US4] Create quickstart validation script in scripts/validate_setup.sh: check Docker running, database accessible, pgvector extension enabled, table created
- [ ] T040 [US4] Document Docker setup workflow in quickstart.md: docker-compose up -d, verify logs, test connection, troubleshooting common issues
- [ ] T041 [US4] Add troubleshooting section to quickstart.md: MPS unavailable (fallback to CPU), connection refused (check Docker), OOM errors (reduce batch_size), slow indexing (check MPS acceleration)
- [ ] T042 [US4] Add volume persistence validation: stop container, verify data persists, restart container, query indexed data to confirm persistence

**Checkpoint**: Local development environment should be fully functional with persistent database

---

## Phase 7: CLI Additional Commands

**Purpose**: Complete CLI tooling for indexing validation and statistics

- [ ] T043 [P] Implement reindex command in src/embeddings/cli.py with --chunk-ids (comma-separated), --config arguments, force re-embedding for specified chunks
- [ ] T044 [P] Implement validate command in src/embeddings/cli.py with --input (directory), --check-embeddings, --verbose: compare JSON files to database records, validate embedding dimensions and values
- [ ] T045 [P] Implement stats command in src/embeddings/cli.py: query total chunks, embedding dimension, database storage size, chunks per source_document (if --verbose)
- [ ] T046 Add exit code handling for all CLI commands: 0 (complete success), 1 (partial failure with some chunks failed), 2 (fatal error), 3 (validation failures for validate command)
- [ ] T047 Add argument validation with Typer: required arguments raise clear errors, invalid paths detected, config JSON validated against EmbeddingConfig Pydantic model

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T048 [P] Add structured logging to PostgreSQLRetriever: log session_id for search operations, query text (truncated), candidate_count, rerank_count, final_result_count, search_duration_ms
- [ ] T049 [P] Add structured logging to indexing pipeline: log chunk_id for each indexed chunk, success/failure status, embedding_duration_ms, batch statistics
- [ ] T050 [P] Update CLAUDE.md with semantic search documentation: indexing commands (index, reindex, validate, stats), search testing examples, Docker setup, CLI usage patterns
- [ ] T051 Code cleanup: remove FAISSRetriever references from RAG agent if no longer needed, consolidate error handling patterns, ensure consistent async/await usage
- [ ] T052 Performance validation: benchmark indexing (target <30min for 500+ chunks), search queries (target <3s p95), reranking (target <2s p95), log metrics
- [ ] T053 Security review: validate SQL injection protection (parameterized queries only), check environment variables not committed to git, ensure input sanitization in CLI arguments

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - US1 (Indexing) can start after Foundational
  - US2 (Search) can be implemented in parallel with US1 but integration testing requires US1 data
  - US3 (Reranking) depends on US2 (Search) being functional
  - US4 (Docker Setup) can start after Foundational, runs in parallel with US1-US3
- **CLI Commands (Phase 7)**: Depends on US1 (Indexing) being complete
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1 - Indexing)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1 - Search)**: Can be implemented in parallel with US1, but needs indexed data for integration testing
- **User Story 3 (P2 - Reranking)**: Depends on US2 (Search) being functional - Reranking enhances existing search
- **User Story 4 (P2 - Docker Setup)**: Can start after Foundational (Phase 2) - Independent of other stories but supports all development workflows

### Within Each User Story

- **US1**: Parser and embedder can run in parallel → Database insertion → CLI → Validation
- **US2**: Models and PostgreSQLRetriever in parallel → Embedding generation → Database query → RAG integration
- **US3**: Qwen3Reranker in parallel with retriever enhancement → Integration → Performance optimization
- **US4**: SQL script, Docker config, quickstart docs in parallel → Validation → Troubleshooting guide

### Parallel Opportunities

- **Setup**: T002, T003, T004 can run in parallel (Docker config, env template, setup script)
- **Foundational**: T007, T008, T011 can run in parallel (schema, connection, encoder)
- **US1**: T012, T013 can run in parallel (parser and embedder)
- **US2**: T021, T022 can start in parallel (models and retriever skeleton)
- **US3**: T030 can run in parallel with other US3 tasks (reranker implementation)
- **US4**: T037, T038, T039 can run in parallel (SQL, healthcheck, validation script)
- **Phase 7**: T043, T044, T045 can all run in parallel (reindex, validate, stats commands)
- **Phase 8**: T048, T049, T050 can run in parallel (logging additions and documentation)

---

## Parallel Example: Foundational Phase

```bash
# Launch foundational components together:
Task: "Create database schema in app/db/schema.py"
Task: "Implement database connection pooling in app/db/connection.py"
Task: "Implement Qwen3EmbeddingEncoder class in src/embeddings/encoder.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch models and retriever skeleton together:
Task: "Create runtime models in app/models.py: SearchQuery, SearchResult"
Task: "Implement PostgreSQLRetriever class in app/core/postgres_retriever.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2 Only)

1. Complete Phase 1: Setup (5 tasks)
2. Complete Phase 2: Foundational (6 tasks) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 - Indexing (9 tasks)
4. Complete Phase 4: User Story 2 - Search (9 tasks)
5. **STOP and VALIDATE**: Test semantic search independently with queries like "side effects of aripiprazole"
6. Deploy/demo if ready - basic semantic search is functional

**Suggested MVP Scope**: Phases 1-4 (29 tasks) provide complete semantic search functionality without reranking

### Full Feature Delivery (All User Stories)

1. Complete MVP (Phases 1-4) → Test thoroughly
2. Add User Story 3 (Reranking) → Compare relevance with/without reranking → Measure 1-5% improvement
3. Add User Story 4 (Docker Setup) → Verify local development workflow → Document for team
4. Add Phase 7 (CLI Commands) → Complete tooling for validation and maintenance
5. Add Phase 8 (Polish) → Production-ready with logging, performance validation, security review

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (all hands on deck for foundation)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (Indexing pipeline) + Phase 7 (CLI commands)
   - **Developer B**: User Story 2 (PostgreSQLRetriever) + US3 (Reranking after US2 complete)
   - **Developer C**: User Story 4 (Docker Setup) + Phase 8 (Documentation and polish)
3. Integration point: After US1 + US2 complete, test end-to-end search workflow
4. Final integration: Add US3 reranking and validate improvement

---

## Architecture Diagram

```
Offline Batch Indexing (src/embeddings/):
  JSON Files → Qwen3EmbeddingEncoder → PostgreSQL
       ↓              ↓                     ↓
  ChunkMetadata  Embedding (1024)    vector_chunks table

Online Runtime Retrieval (app/core/):
  User Query → PostgreSQLRetriever → pgvector search → Qwen3Reranker → Top 5 Results
                      ↓                    ↓               ↓
              Embedding Generation   Cosine Similarity  Relevance Scoring
                      ↓                    ↓               ↓
              app/core/postgres_retriever.py → app/core/qwen3_reranker.py

RAG Agent (app/agents/):
  RAG Agent → PostgreSQLRetriever.search() → Reranked Documents → Generate Response
      ↓              ↓                            ↓
  Closure     DocumentRetriever Interface    List[Document]
```

---

## Notes

- **[P]** tasks = different files, no dependencies
- **[Story]** label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Critical Success Criteria**:
  - SC-001: All 500+ chunks indexed in under 30 minutes
  - SC-002: Search queries return top 5 results in under 3 seconds (p95)
  - SC-003: Reranking completes in under 2 seconds (p95)
  - SC-006: 80% of test queries return highly relevant chunk in top 3 results
- **Interface Compatibility**: PostgreSQLRetriever MUST implement DocumentRetriever interface without modifying RAG agent code
- **Reranking**: Mandatory (always enabled), not optional - improves result quality by 1-5%
- **Docker**: Required for local development, production uses externally managed PostgreSQL
- **MPS Support**: Critical for Apple Silicon performance, fallback to CPU if unavailable
- **Architecture Separation**: `src/embeddings/` for offline batch indexing, `app/core/` for runtime retrieval, `app/db/` for shared database infrastructure
