# Tasks: Multi-Query Expansion and Keyword Matching

**Input**: Design documents from `/specs/005-multi-query-keyword-search/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included (TDD required by constitution - Principle III)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: Repository root structure
- `app/` for application code
- `tests/` for test code (contract/, integration/, unit/)

---

## Phase 1: Setup (Database Infrastructure)

**Purpose**: Enable PostgreSQL pg_trgm extension and create required indexes

- [X] T001 Create database migration function `enable_keyword_search()` in app/db/schema.py
- [X] T002 Add configuration parameter `enable_keyword_search: bool = False` in app/config.py
- [X] T003 Execute database migration to enable pg_trgm extension and create GIN index on vector_chunks.chunk_text

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core retrieval infrastructure modifications that MUST be complete before user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Modify AdvancedRetriever.__init__() to accept `max_queries: int = 10` parameter in app/retrieval/advanced.py
- [X] T005 Update AdvancedRetriever.expand_query() prompt to remove key prefixes and support 1-10 queries in app/retrieval/advanced.py
- [X] T006 Update AdvancedRetriever.expand_query() parsing logic to split by newline instead of key matching in app/retrieval/advanced.py
- [X] T007 Add structured logging for query expansion (query_count, generation_time) in app/retrieval/advanced.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Multi-Query Generation for Complex Comparisons (Priority: P1) 🎯 MVP

**Goal**: Decompose comparative/multi-faceted queries into 1-10 focused sub-queries to improve retrieval coverage

**Independent Test**: Submit "Compare aripiprazole and risperidone" and verify system generates 2-5+ separate queries for each drug, executes them independently, and merges results without duplicates

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US1] Integration test for single-topic query generation (1-2 queries) in tests/integration/test_advanced_retriever.py
- [X] T009 [P] [US1] Integration test for comparative query generation (5-10 queries) in tests/integration/test_advanced_retriever.py
- [X] T010 [P] [US1] Integration test for result deduplication across multiple queries in tests/integration/test_advanced_retriever.py

### Implementation for User Story 1

- [X] T011 [US1] Implement parallel query execution using asyncio.gather() for vector search in app/retrieval/advanced.py
- [X] T012 [US1] Add fallback logic: use original query if query generation produces 0 valid queries in app/retrieval/advanced.py
- [X] T013 [US1] Implement `_merge_results()` method for chunk_id-based deduplication in app/retrieval/advanced.py
- [X] T014 [US1] Update search() method to integrate multi-query generation with existing reranker in app/retrieval/advanced.py
- [X] T015 [US1] Add error handling and logging for query generation failures in app/retrieval/advanced.py

**Checkpoint**: At this point, User Story 1 should be fully functional - multi-query generation and deduplication working end-to-end

---

## Phase 4: User Story 2 - Query Quality Control and Deduplication (Priority: P2)

**Goal**: Validate generated queries, remove duplicates, and filter malformed queries before execution

**Independent Test**: Trigger edge cases (ambiguous input, repeated terms) and verify duplicate/malformed queries are filtered before database execution

### Tests for User Story 2 ⚠️

- [X] T016 [P] [US2] Unit test for duplicate query detection (exact string match) in tests/unit/test_query_validation.py
- [X] T017 [P] [US2] Unit test for malformed query filtering (empty, punctuation-only) in tests/unit/test_query_validation.py
- [X] T018 [P] [US2] Unit test for query ranking by relevance (top-10 selection) in tests/unit/test_query_validation.py

### Implementation for User Story 2

- [X] T019 [P] [US2] Implement query validation logic (non-empty, meaningful content) in app/retrieval/advanced.py
- [X] T020 [P] [US2] Implement duplicate detection using exact string matching in app/retrieval/advanced.py
- [X] T021 [US2] Integrate validation into expand_query() workflow in app/retrieval/advanced.py
- [X] T022 [US2] Add logging for filtered queries (duplicates, malformed) in app/retrieval/advanced.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - multi-query with quality control active

---

## Phase 5: User Story 3 - Hybrid Keyword+Vector Search with pg_trgm (Priority: P3)

**Goal**: Add PostgreSQL pg_trgm trigram-based lexical matching alongside vector semantic search for term-specific queries

**Independent Test**: Submit query with specific drug name (e.g., "阿立哌唑副作用") and verify documents containing "aripiprazole" are retrieved via keyword search

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Integration test for keyword-only search using pg_trgm in tests/integration/test_keyword_search.py
- [X] T024 [P] [US3] Integration test for hybrid search (vector + keyword) result merging in tests/integration/test_keyword_search.py
- [X] T025 [P] [US3] Integration test for keyword search with specific drug names in tests/integration/test_keyword_search.py

### Implementation for User Story 3

- [X] T026 [US3] Implement `_keyword_search()` method using pg_trgm similarity operator in app/retrieval/advanced.py
- [X] T027 [US3] Add parallel execution for keyword search using asyncio.gather() in app/retrieval/advanced.py
- [X] T028 [US3] Integrate keyword search into search() method (conditional on enable_keyword_search flag) in app/retrieval/advanced.py
- [X] T029 [US3] Update `_merge_results()` to handle both vector and keyword results in app/retrieval/advanced.py
- [X] T030 [US3] Add structured logging for keyword search (candidates_retrieved, search_time, keyword_scores) in app/retrieval/advanced.py
- [X] T031 [US3] Add graceful degradation to vector-only if pg_trgm extension missing in app/retrieval/advanced.py

**Checkpoint**: All user stories (1-3) should now work independently - full hybrid search pipeline functional

---

## Phase 6: User Story 4 - Cross-Language Query Handling (Priority: P4)

**Goal**: Handle Chinese→English translation in LLM query expansion, preserving medical terminology accurately

**Independent Test**: Submit Chinese query "阿立哌唑的作用机制" and verify LLM generates accurate English queries with correct medical terms

### Tests for User Story 4 ⚠️

- [X] T032 [P] [US4] Integration test for Chinese query translation with drug name preservation in tests/integration/test_cross_language.py
- [X] T033 [P] [US4] Integration test for mixed Chinese+Latin query handling (e.g., "5-HT2A受体") in tests/integration/test_cross_language.py

### Implementation for User Story 4

- [X] T034 [US4] Update expand_query() prompt to explicitly handle Chinese→English translation in app/retrieval/advanced.py
- [X] T035 [US4] Add prompt instruction to preserve Latin/English terms exactly while translating Chinese in app/retrieval/advanced.py
- [X] T036 [US4] Add logging for cross-language query expansion (original_language, translated_queries) in app/retrieval/advanced.py

**Checkpoint**: Complete hybrid multi-query system with cross-language support fully functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T037 [P] Update CLAUDE.md with new retrieval features and configuration in CLAUDE.md
- [X] T038 [P] Verify all quickstart.md examples work end-to-end in specs/005-multi-query-keyword-search/quickstart.md
- [X] T039 Code review for security: verify parameterized SQL queries in keyword search
- [X] T040 Performance validation: verify end-to-end latency <3s at 95th percentile
- [X] T041 [P] Add unit tests for edge cases (0 queries, >10 queries, query truncation) in tests/unit/test_edge_cases.py
- [X] T042 Run full integration test suite and verify all user stories work independently

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 query generation but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Uses US1 multi-query + US2 validation, independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Enhances US1 query expansion, independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Integration tests before implementation tasks
- Core implementation before error handling/logging
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks (Phase 1) can run sequentially (only 3 quick tasks)
- All Foundational tasks (Phase 2) can run sequentially (modifying same file)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests within a user story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Integration test for single-topic query generation in tests/integration/test_advanced_retriever.py"
Task: "Integration test for comparative query generation in tests/integration/test_advanced_retriever.py"
Task: "Integration test for result deduplication in tests/integration/test_advanced_retriever.py"
```

---

## Parallel Example: User Story 3

```bash
# Launch all tests for User Story 3 together:
Task: "Integration test for keyword-only search in tests/integration/test_keyword_search.py"
Task: "Integration test for hybrid search merging in tests/integration/test_keyword_search.py"
Task: "Integration test for keyword search with drug names in tests/integration/test_keyword_search.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (database migration)
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (multi-query generation)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

**Result**: Users can now ask comparative questions and get comprehensive multi-query results

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (~100 lines modified)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP - multi-query working!)
3. Add User Story 2 → Test independently → Deploy/Demo (quality control active)
4. Add User Story 3 → Test independently → Deploy/Demo (hybrid search enabled)
5. Add User Story 4 → Test independently → Deploy/Demo (cross-language polished)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (~100 lines, single file)
2. Once Foundational is done:
   - Developer A: User Story 1 (multi-query)
   - Developer B: User Story 2 (quality control)
   - Developer C: User Story 3 (keyword search)
   - Developer D: User Story 4 (cross-language)
3. Stories complete and integrate independently

---

## Success Metrics Mapping

**User Story 1**:
- SC-001: Multi-query improves accuracy by ≥30% for comparative queries
- SC-002: Query generation completes in <500ms for up to 10 queries
- SC-006: Query deduplication reduces redundant queries by ≥40%

**User Story 2**:
- SC-006: Deduplication reduces redundant database queries by ≥40%

**User Story 3**:
- SC-003: Hybrid retrieval improves recall by ≥25% for term-specific queries
- SC-004: End-to-end retrieval maintains <3s latency for top-5 results
- SC-007: Reranker achieves ≥80% user satisfaction with top-5 results

**User Story 4**:
- SC-005: LLM translates ≥90% of Chinese queries accurately

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Red-Green-Refactor)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution requirement: TDD workflow strictly enforced
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
