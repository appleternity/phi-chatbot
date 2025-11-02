# Tasks: LLM-Based Contextual Document Chunking for RAG

**Feature Branch**: `001-llm-contextual-chunking` | **Date**: 2025-10-29
**Input**: Design documents from `/specs/001-llm-contextual-chunking/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Tests**: Tests are NOT explicitly requested in the feature specification. Following TDD principle from constitution, tests will be written but not as separate tasks per the project methodology.

## Format: `- [ ] [ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure: src/chunking/ and tests/chunking/ with __init__.py files
- [X] T002 Initialize Python dependencies: requests, tiktoken, pydantic, python-dotenv, typer in requirements.txt
- [X] T003 [P] Configure pytest, pytest-mock, pytest-cov in requirements.txt for testing
- [X] T004 [P] Create .env.example template with OPENROUTER_API_KEY, OPENROUTER_BASE_URL, CACHE_DIR variables
- [X] T005 [P] Setup .cache/ directory structure with .gitignore to exclude cache files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Implement Pydantic models in src/chunking/models.py: Document, Section, Structure, BoundaryType, SegmentBoundary, ChunkMetadata, ProcessingMetadata, Chunk, ProcessingReport, ProcessingResult, BatchReport, BatchProcessingResult
- [X] T007 [P] Implement abstract LLMProvider interface in src/chunking/llm_provider.py with chat_completion method
- [X] T008 [P] Implement abstract CacheStore interface in src/chunking/cache_store.py with get/set methods
- [X] T009 Implement OpenRouterProvider in src/chunking/llm_provider.py using requests library with error handling
- [X] T010 [P] Implement FileCacheStore in src/chunking/cache_store.py with JSON file storage in .cache/structures/
- [X] T011 [P] Implement MockLLMProvider in src/chunking/llm_provider.py for testing with call_history tracking
- [X] T012 [P] Implement TokenCounter utility in src/chunking/models.py with tiktoken support and character-based fallback
- [X] T013 [P] Create custom exception hierarchy in src/chunking/models.py: ChunkingError, StructureAnalysisError, BoundaryDetectionError, SegmentationError, TextCoverageError, MetadataValidationError, LLMProviderError
- [X] T014 [P] Implement MetadataValidator utility in src/chunking/metadata_validator.py with validation rules from data-model.md
- [X] T015 [P] Setup structured logging configuration with INFO, DEBUG, ERROR levels including document_id and phase context
- [X] T016 Create test fixtures directory tests/chunking/fixtures/ with mock LLM response templates for all three phases
- [X] T017 [P] Create base test utilities in tests/chunking/conftest.py with pytest fixtures for mock providers and test documents

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Process Book Chapter for RAG Retrieval (Priority: P1) 🎯 MVP

**Goal**: Take a single document and produce quality, contextually-enriched chunks with proper metadata, size constraints, and semantic coherence

**Independent Test**: Provide a sample chapter document, run the chunking process, validate that output chunks contain proper metadata, are within size constraints (≤1000 tokens), have contextual enrichment, maintain semantic coherence, and achieve 100% text coverage

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement StructureAnalyzer in src/chunking/structure_analyzer.py with LLM-based document hierarchy analysis
- [X] T019 [P] [US1] Create structure analysis prompt template in src/chunking/structure_analyzer.py following TSV format from contracts/prompt_templates.md
- [X] T020 [US1] Implement TSV response parser in src/chunking/structure_analyzer.py with validation for 5-column format and section overlap checking
- [X] T021 [US1] Add cache integration to StructureAnalyzer using document file_hash as cache key with cache hit tracking
- [X] T022 [P] [US1] Implement BoundaryDetector in src/chunking/boundary_detector.py with semantic boundary identification
- [X] T023 [P] [US1] Create boundary detection prompt template in src/chunking/boundary_detector.py following TSV format from contracts/prompt_templates.md
- [X] T024 [US1] Implement boundary detection logic: section size evaluation, LLM calls for oversized sections, TSV parsing for 3-column format
- [X] T025 [US1] Add boundary ordering validation and completeness checks (DOCUMENT_START at 0, DOCUMENT_END at document length)
- [X] T026 [P] [US1] Implement DocumentSegmenter in src/chunking/document_segmenter.py with chunk generation and text cleaning
- [X] T027 [P] [US1] Create metadata generation prompt template in src/chunking/document_segmenter.py following TSV format from contracts/prompt_templates.md
- [X] T028 [P] [US1] Create contextual prefix generation prompt template in src/chunking/document_segmenter.py following plain text format from contracts/prompt_templates.md
- [X] T029 [US1] Implement chunk segmentation: extract text segments, generate metadata via LLM, generate contextual prefix, clean text
- [X] T030 [US1] Add metadata completeness validation and token count enforcement (≤1000) in DocumentSegmenter
- [X] T031 [P] [US1] Implement TextAligner in src/chunking/text_aligner.py using difflib.SequenceMatcher for coverage verification
- [X] T032 [US1] Add text coverage validation logic: reconstruct document from chunks, calculate coverage ratio, fail if <99%
- [X] T033 [US1] Implement ChunkingPipeline orchestrator in src/chunking/chunking_pipeline.py coordinating all three phases
- [X] T034 [US1] Add process_document method in ChunkingPipeline: Phase 1 (structure) → Phase 2 (boundaries) → Phase 3 (segment) → Validation (coverage + metadata)
- [X] T035 [US1] Implement ProcessingResult generation with metrics: chunk count, token consumption per phase, coverage ratio, cache hits
- [X] T036 [US1] Add comprehensive error handling with fail-fast behavior and detailed error messages for all phases
- [ ] T037 [P] [US1] Create contract tests in tests/chunking/contract/ for StructureAnalyzer, BoundaryDetector, DocumentSegmenter following contracts/component_interfaces.md
- [ ] T038 [P] [US1] Create integration test in tests/chunking/integration/test_end_to_end_chunking.py for full pipeline with mock LLM
- [ ] T039 [P] [US1] Create unit tests in tests/chunking/unit/ for TextAligner, MetadataValidator, TokenCounter utilities
- [ ] T040 [US1] Validate end-to-end: process sample chapter, verify 100% coverage, verify metadata completeness, verify token limits

**Checkpoint**: At this point, User Story 1 should be fully functional - single document processing works correctly with quality chunks

---

## Phase 4: User Story 2 - Batch Process Multiple Chapters (Priority: P2)

**Goal**: Process an entire folder of book chapters efficiently with automatic document handling and consolidated results for downstream RAG ingestion

**Independent Test**: Provide a folder containing 5-10 chapter files, execute batch process, verify all chapters processed without errors, confirm consolidated output maintains proper document boundaries and identifiers

### Implementation for User Story 2

- [X] T041 [P] [US2] Implement process_folder method in src/chunking/chunking_pipeline.py with file discovery for .txt and .md files
- [X] T042 [US2] Add sequential document processing loop with fail-fast behavior on first error
- [X] T043 [US2] Implement BatchProcessingResult aggregation with per-document results and consolidated metrics
- [X] T044 [US2] Add document identifier preservation: ensure each chunk includes source_document field tracing to original file
- [X] T045 [US2] Implement consolidated JSONL output writer: write all chunks to single file with document boundaries maintained
- [X] T046 [US2] Add batch-level error reporting: capture document ID, error type, and error message for failed documents
- [X] T047 [US2] Implement batch metrics calculation: total documents, successful count, failed count, total chunks, aggregate token consumption
- [ ] T048 [P] [US2] Create integration test in tests/chunking/integration/test_batch_processing.py with 5 mock documents
- [ ] T049 [US2] Test batch failure scenario: verify processing halts on first error with clear failure reporting
- [ ] T050 [US2] Test document identifier preservation: verify all chunks trace back to correct source documents
- [ ] T051 [US2] Validate batch processing: process 5 sample chapters, verify consolidated output format, verify document boundaries

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - single document and batch folder processing both functional

---

## Phase 5: User Story 3 - Cost-Optimized Processing with Caching (Priority: P3)

**Goal**: Minimize API costs by leveraging caching mechanisms for structure analysis, especially when reprocessing documents or processing similar document structures

**Independent Test**: Process the same document twice, measure token usage on both runs, verify the second run consumes significantly fewer tokens (50%+ reduction expected for structure analysis)

### Implementation for User Story 3

- [ ] T052 [P] [US3] Implement prompt caching headers in OpenRouterProvider: add Cache-Control headers for structure analysis requests
- [ ] T053 [US3] Add cache key generation strategy in StructureAnalyzer: hash document content for structure cache, hash section + max_tokens for boundaries
- [ ] T054 [US3] Implement cache hit tracking in ProcessingMetadata: add cache_hit field and update in StructureAnalyzer
- [ ] T055 [US3] Add token consumption tracking across all phases: capture phase_1_tokens, phase_2_tokens, phase_3_tokens in ProcessingReport
- [ ] T056 [US3] Implement cache statistics aggregation in BatchReport: total cache hits, token savings percentage
- [ ] T057 [US3] Add cache warming strategy for batch processing: reuse cached structures for similar document patterns
- [ ] T058 [US3] Optimize cache storage: implement cache expiration and cleanup logic in FileCacheStore
- [ ] T059 [P] [US3] Create integration test in tests/chunking/integration/test_caching_workflow.py for cache hit/miss scenarios
- [ ] T060 [US3] Test reprocessing workflow: process same document twice, verify second run uses cache, measure token reduction
- [ ] T061 [US3] Test similar document caching: process documents with similar structure, verify structure cache reuse
- [ ] T062 [US3] Validate caching effectiveness: process 10 similar chapters, verify 50%+ token reduction after first chapter

**Checkpoint**: All user stories should now be independently functional - caching provides significant cost optimization

---

## Phase 6: User Interface (CLI Implementation)

**Purpose**: User-facing command-line interface for document processing

- [X] T063 Create CLI application in src/chunking/cli.py using typer framework with typer.Option and Annotated
- [X] T064 [P] Implement process command with options: --input, --output, --structure-model, --boundary-model, --segmentation-model, --max-tokens, --log-level
- [X] T065 [P] Add input path validation: check if file or folder exists, auto-detect processing mode (single file vs batch)
- [X] T066 [P] Implement logging configuration based on --log-level option with structured output
- [X] T067 Add progress indicators for batch processing: show current document, progress percentage, estimated time
- [X] T068 [P] Implement rich console output with colorized success/error messages and formatted results
- [X] T069 [P] Add cache management command: --stats to display cache statistics, --clear to clear all cached data
- [X] T070 Implement proper exit codes: 0 (success), 1 (processing error), 2 (validation error)
- [X] T071 Add environment variable support: load OPENROUTER_API_KEY, model overrides, cache directory from .env
- [X] T072 Create comprehensive CLI help documentation with examples for all options
- [ ] T073 [P] Create CLI integration tests in tests/chunking/integration/test_cli.py using typer testing utilities
- [ ] T074 Test CLI with various input scenarios: single file, folder, invalid paths, missing API key, invalid models
- [ ] T075 Validate CLI output format: verify JSONL structure, verify error messages, verify progress indicators

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T076 [P] Add comprehensive docstrings to all public methods following Google Python style guide
- [ ] T077 [P] Create README.md in src/chunking/ with module overview and usage examples
- [ ] T078 [P] Validate quickstart.md examples: run all example commands, verify outputs match documentation
- [ ] T079 [P] Add type hints to all function signatures and verify with mypy
- [ ] T080 [P] Configure ruff linting rules in pyproject.toml and fix all linting issues
- [ ] T081 [P] Run test suite with coverage: pytest --cov=src.chunking --cov-report=html, verify 80%+ unit coverage
- [ ] T082 [P] Security audit: check for API key exposure in logs, validate input sanitization, review error messages
- [ ] T083 [P] Performance profiling: identify bottlenecks in chunking pipeline, optimize hot paths if needed
- [ ] T084 Code cleanup: remove debug print statements, consolidate duplicate code, improve variable naming
- [ ] T085 Final integration test: process real book chapters end-to-end, validate all success criteria from spec.md
- [ ] T086 Update CLAUDE.md with project technologies, commands, and code style conventions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User Story 1 (P1): Single document processing - foundation for all other stories
  - User Story 2 (P2): Builds on US1 by adding batch processing capability
  - User Story 3 (P3): Enhances US1 and US2 with caching optimization
- **CLI (Phase 6)**: Depends on US1, US2, US3 completion - provides user interface
- **Polish (Phase 7)**: Depends on all phases being functionally complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after US1 complete - Reuses ChunkingPipeline.process_document method
- **User Story 3 (P3)**: Can start after US1 complete - Enhances existing components with caching

### Within Each User Story

**User Story 1 (Single Document Processing)**:
1. StructureAnalyzer, BoundaryDetector, DocumentSegmenter can be developed in parallel (T018-T030)
2. TextAligner can be developed in parallel (T031-T032)
3. ChunkingPipeline requires all components complete (T033-T036)
4. Tests can be written in parallel with implementation (T037-T039)

**User Story 2 (Batch Processing)**:
1. All tasks sequential, building on US1's ChunkingPipeline
2. Tests can be written in parallel (T048)

**User Story 3 (Caching)**:
1. Cache integration tasks can be done in parallel (T052-T054)
2. Token tracking and statistics sequential (T055-T056)
3. Tests can be written in parallel (T059)

### Parallel Opportunities

- All Setup tasks can run in parallel (T002-T005)
- Many Foundational tasks can run in parallel (T007-T008, T010-T011, T012, T014, T016-T017)
- Within US1: Component implementations (T018-T030), TextAligner (T031-T032), tests (T037-T039) can be parallelized
- Within US2: Tests (T048) can start early
- Within US3: Cache integration tasks (T052-T054), tests (T059) can be parallelized
- CLI tasks can be partially parallelized (T064-T069)
- Polish tasks are highly parallelizable (T076-T083)

---

## Parallel Example: User Story 1

```bash
# Launch component implementations together (after Foundation complete):
Task: "Implement StructureAnalyzer in src/chunking/structure_analyzer.py"
Task: "Implement BoundaryDetector in src/chunking/boundary_detector.py"
Task: "Implement DocumentSegmenter in src/chunking/document_segmenter.py"
Task: "Implement TextAligner in src/chunking/text_aligner.py"

# Launch tests together (can write alongside implementation):
Task: "Contract tests for StructureAnalyzer, BoundaryDetector, DocumentSegmenter"
Task: "Integration test for end-to-end chunking"
Task: "Unit tests for TextAligner, MetadataValidator, TokenCounter"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005) - ~1 hour
2. Complete Phase 2: Foundational (T006-T017) - ~4-8 hours
3. Complete Phase 3: User Story 1 (T018-T040) - ~8-16 hours
4. **STOP and VALIDATE**: Test with real chapter, verify all acceptance scenarios
5. Deploy/demo single document processing capability

**Total MVP Estimate**: 13-25 hours for fully functional single-document chunking

### Incremental Delivery

1. **Foundation** (Phase 1+2) → All models, interfaces, utilities ready
2. **MVP** (Phase 3: US1) → Single document processing works → Demo!
3. **Batch** (Phase 4: US2) → Folder processing works → Demo batch capability!
4. **Optimization** (Phase 5: US3) → Caching reduces costs → Demo cost savings!
5. **User Interface** (Phase 6: CLI) → User-friendly CLI → Release v1.0!
6. **Polish** (Phase 7) → Production-ready quality → Final release!

### Parallel Team Strategy

With 3 developers after Foundation complete:

1. **Developer A**: User Story 1 (StructureAnalyzer + tests)
2. **Developer B**: User Story 1 (BoundaryDetector + tests)
3. **Developer C**: User Story 1 (DocumentSegmenter + TextAligner + tests)
4. All converge on ChunkingPipeline integration
5. Then split again: A→US2, B→US3, C→CLI

---

## Task Summary

**Total Tasks**: 86 tasks across 7 phases

**Phase Breakdown**:
- Phase 1 (Setup): 5 tasks (~1 hour)
- Phase 2 (Foundational): 12 tasks (~4-8 hours) - CRITICAL BLOCKING PHASE
- Phase 3 (US1 - MVP): 23 tasks (~8-16 hours) - Core chunking functionality
- Phase 4 (US2 - Batch): 11 tasks (~4-6 hours) - Folder processing
- Phase 5 (US3 - Caching): 11 tasks (~3-5 hours) - Cost optimization
- Phase 6 (CLI): 13 tasks (~4-6 hours) - User interface
- Phase 7 (Polish): 11 tasks (~4-6 hours) - Production readiness

**Parallel Opportunities**: 35+ tasks marked [P] can run in parallel within their phase

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 (US1) = 40 tasks = Core single-document processing

**Success Criteria Validation** (from spec.md):
- SC-001: 100% text coverage → Validated by TextAligner (T031-T032)
- SC-002: 100% metadata completeness → Validated by MetadataValidator (T014, T030)
- SC-003: 95% chunks 700-1000 tokens → Enforced by BoundaryDetector and DocumentSegmenter (T022-T025, T026-T030)
- SC-004: 90% semantic coherence → Achieved through LLM-based boundary detection (T022-T025)
- SC-005: 50% token reduction with caching → Validated in US3 (T052-T062)
- SC-006: 30% retrieval improvement → Manual testing with RAG pipeline (post-implementation)

---

## Notes

- **Constitution Compliance**: TDD principle followed - tests written alongside implementation, not as separate blocking tasks
- **Fail-Fast Philosophy**: All phases implement immediate error raising per user requirements
- **TSV Format**: All LLM outputs use TSV (not JSON) for reliability per research.md decisions
- **Model Selection**: Per-phase model configuration via CLI enables cost/quality tradeoffs
- **Caching Strategy**: Hybrid file-based + prompt caching per research.md
- **Independent Testing**: Each user story can be validated independently per spec.md
- **File Paths**: All tasks include exact file paths for clarity
- **[P] Marking**: Only tasks with different files and no dependencies marked [P]
- **[Story] Labels**: All user story tasks labeled [US1], [US2], [US3] for traceability
