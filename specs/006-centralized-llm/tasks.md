# Tasks: Centralized LLM Instance Management

**Input**: Design documents from `/specs/006-centralized-llm/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: NOT requested in feature specification - tests not included

**Organization**: Tasks grouped by user story to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Project uses single structure: `app/` for source, `tests/` for tests

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create centralized LLM module structure

- [X] T001 Create `app/llm/` directory for centralized LLM management
- [X] T002 Create `app/llm/__init__.py` to export public API (create_llm, response_llm, internal_llm)
- [X] T003 Create `tests/fakes/` directory if not exists for response registry

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Move `create_llm()` function to centralized location - BLOCKS all user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Move `create_llm()` function from `app/agents/base.py` to `app/llm/factory.py` (keep signature: temperature, disable_streaming, tags parameters)
- [X] T005 Update `create_llm()` implementation in `app/llm/factory.py` to use environment-based switching (TESTING=true → FakeChatModel, TESTING=false → ChatOpenAI)
- [X] T006 Create singleton instances in `app/llm/instances.py`: `response_llm = create_llm(temperature=0.7)` and `internal_llm = create_llm(temperature=1.0, disable_streaming=True, tags=["internal-llm"])`
- [X] T007 Update `app/llm/__init__.py` to export: `from app.llm.factory import create_llm` and `from app.llm.instances import response_llm, internal_llm`

**Checkpoint**: Foundation ready - centralized LLM module exists, user story refactoring can now begin

---

## Phase 3: User Story 1 - Centralized LLM Instance Access (Priority: P1) 🎯 MVP

**Goal**: Refactor all existing `create_llm()` calls to use centralized instances

**Independent Test**: Import centralized instances from any module and verify singleton behavior (same object reference across imports)

### Implementation for User Story 1

- [X] T008 [P] [US1] Refactor `app/agents/supervisor.py`: Replace `from app.agents.base import create_llm` + `llm = create_llm(temperature=0.1)` with `from app.llm import response_llm`
- [X] T009 [P] [US1] Refactor `app/agents/emotional_support.py`: Replace `from app.agents.base import create_llm` + `llm = create_llm(temperature=1.0)` with `from app.llm import response_llm`
- [X] T010 [US1] Refactor `app/agents/rag_agent.py`: Replace both `create_llm()` calls - use `from app.llm import internal_llm, response_llm` (internal_llm for classification at temperature=0.1, response_llm for generation at temperature=1.0)
- [X] T011 [P] [US1] Refactor `app/retrieval/advanced.py`: Replace `from app.agents.base import create_llm` + `self.llm = create_llm(temperature=1.0, disable_streaming=True, tags=["internal-llm"])` with `from app.llm import internal_llm` and `self.llm = internal_llm`
- [X] T012 [US1] Delete `app/agents/base.py` entirely (fail-fast - force all imports to break immediately)
- [X] T013 [US1] Run all existing tests to verify centralized instances work correctly with both test (FakeChatModel) and production (ChatOpenAI) environments

**Checkpoint**: All agents now use centralized instances - zero `create_llm()` calls outside `app/llm/`

---

## Phase 4: User Story 2 - Simplified Test Environment Configuration (Priority: P2)

**Goal**: Verify automatic test/prod switching works seamlessly

**Independent Test**: Run test suite with TESTING=true and verify FakeChatModel is used; run with TESTING=false and verify ChatOpenAI is used

### Implementation for User Story 2

- [X] T014 [US2] Add explicit test in `tests/unit/llm/test_instances.py` to verify TESTING=true returns FakeChatModel instances
- [X] T015 [US2] Add explicit test in `tests/unit/llm/test_instances.py` to verify TESTING=false returns ChatOpenAI instances
- [X] T016 [US2] Add test in `tests/unit/llm/test_instances.py` to verify singleton behavior (same object reference across multiple imports)
- [X] T017 [US2] Verify `conftest.py` still sets `TESTING=true` automatically (no changes needed - just verification)
- [X] T018 [US2] Run full test suite and verify all agent tests pass with FakeChatModel responses

**Checkpoint**: Automatic environment switching verified - tests use FakeChatModel, production uses ChatOpenAI

---

## Phase 5: User Story 3 - Organized Mock Response Management (Priority: P3)

**Goal**: Extract fake response patterns from FakeChatModel into centralized registry

**Independent Test**: Add new response pattern to registry and verify FakeChatModel uses it without code changes

### Implementation for User Story 3

- [X] T019 [US3] Create `tests/fakes/response_registry.py` with structured dictionary for response patterns (supervisor_classification, rag_classification, medical_responses, emotional_responses)
- [X] T020 [US3] Extract supervisor classification keywords from `tests/fakes/fake_chat_model.py` to response_registry.py RESPONSE_PATTERNS["supervisor_classification"]
- [X] T021 [US3] Extract RAG classification keywords from `tests/fakes/fake_chat_model.py` to response_registry.py RESPONSE_PATTERNS["rag_classification"]
- [X] T022 [US3] Extract medical responses from `tests/fakes/fake_chat_model.py` to response_registry.py RESPONSE_PATTERNS["medical_responses"]
- [X] T023 [US3] Extract emotional responses from `tests/fakes/fake_chat_model.py` to response_registry.py RESPONSE_PATTERNS["emotional_responses"]
- [X] T024 [US3] Refactor `tests/fakes/fake_chat_model.py` _generate() method to import and use RESPONSE_PATTERNS instead of embedded conditionals
- [X] T025 [US3] Run all tests to verify FakeChatModel still returns correct responses after registry extraction
- [X] T026 [US3] Add docstring to response_registry.py explaining how to add new response patterns

**Checkpoint**: Fake response patterns centralized - adding new patterns requires only updating response_registry.py

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final validation

- [X] T027 [P] Update quickstart.md examples to reflect simplified design (no LLMConfig Pydantic model, just function parameters)
- [X] T028 [P] Update data-model.md to remove LLMConfig entity (simplified to function parameters only)
- [X] T029 [P] Update contracts/llm_api.py to remove LLMConfig class definition (show function signature instead)
- [X] T030 Add type hints to `app/llm/instances.py`: `response_llm: BaseChatModel` and `internal_llm: BaseChatModel`
- [X] T031 Run `mypy app/llm/` to verify type checking passes
- [X] T032 Run full test suite one final time to ensure all existing tests pass
- [X] T033 Update CLAUDE.md "Recent Changes" section with centralized LLM implementation summary

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational - No dependencies on other stories
  - User Story 2 (P2): Can start after US1 completion (needs centralized instances to test)
  - User Story 3 (P3): Can start after US2 completion (needs working tests to extract patterns from)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational (Phase 2) - Refactors all existing code
- **User Story 2 (P2)**: Depends on US1 - Tests the centralized instances created in US1
- **User Story 3 (P3)**: Depends on US2 - Extracts patterns from FakeChatModel after testing is verified

### Within Each User Story

- **US1**: Tasks T008, T009, T011 can run in parallel (different files), T010 depends on T008/T009 completion (same rag_agent.py file), T012 must be LAST (deletes base.py), T013 validates everything
- **US2**: Tasks T014-T016 can run in parallel (different test scenarios in same file), T017-T018 are validation
- **US3**: Tasks T019-T023 can run in parallel (extracting different sections), T024 refactors FakeChatModel to use registry, T025-T026 validate and document

### Parallel Opportunities

- **Phase 1**: All tasks are quick setup (T001-T003) - can run in sequence
- **Phase 2**: Tasks must run sequentially (T004→T005→T006→T007) - each depends on previous
- **Phase 3 (US1)**: T008, T009, T011 can run in parallel
- **Phase 4 (US2)**: T014, T015, T016 can run in parallel
- **Phase 5 (US3)**: T019, T020, T021, T022, T023 can run in parallel
- **Phase 6**: T027, T028, T029 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch parallel refactoring tasks for US1:
Task T008: "Refactor app/agents/supervisor.py"
Task T009: "Refactor app/agents/emotional_support.py"
Task T011: "Refactor app/retrieval/advanced.py"

# Then sequentially:
Task T010: "Refactor app/agents/rag_agent.py" (waits for T008/T009)
Task T012: "Delete app/agents/base.py" (waits for all refactoring)
Task T013: "Run all tests" (validation)
```

---

## Parallel Example: User Story 3

```bash
# Launch parallel extraction tasks for US3:
Task T020: "Extract supervisor classification keywords to response_registry.py"
Task T021: "Extract RAG classification keywords to response_registry.py"
Task T022: "Extract medical responses to response_registry.py"
Task T023: "Extract emotional responses to response_registry.py"

# Then sequentially:
Task T024: "Refactor FakeChatModel to use RESPONSE_PATTERNS" (waits for T020-T023)
Task T025: "Run tests to verify" (validation)
Task T026: "Add documentation" (final touch)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007) - CRITICAL blocks all stories
3. Complete Phase 3: User Story 1 (T008-T013) - All code refactored to centralized instances
4. **STOP and VALIDATE**: Run full test suite - verify all tests pass
5. Merge to main - centralized LLM instances now available

### Incremental Delivery

1. Complete Setup + Foundational → Centralized module ready (T001-T007)
2. Add User Story 1 → All code uses centralized instances (T008-T013) → **MVP DONE**
3. Add User Story 2 → Test environment validated (T014-T018) → **Enhanced testing**
4. Add User Story 3 → Response patterns organized (T019-T026) → **Maintainability improved**
5. Polish → Documentation updated (T027-T033) → **Production ready**

### Parallel Team Strategy

With 2-3 developers:

1. **Team completes Setup + Foundational together** (T001-T007)
2. Once Foundational done:
   - **Developer A**: US1 tasks T008, T009 (parallel refactoring)
   - **Developer B**: US1 tasks T011 (parallel refactoring)
   - **Then A or B**: T010, T012, T013 (sequential cleanup)
3. **Developer A**: US2 tasks T014-T018 (test validation)
4. **Developer B**: US3 tasks T019-T026 (response registry extraction)
5. **Team**: Polish tasks T027-T033 (parallel documentation updates)

---

## Notes

- **Simplified Design**: No LLMConfig Pydantic model - just function parameters (temperature, disable_streaming, tags)
- **Fail-Fast Migration**: Delete `app/agents/base.py` completely - no backward compatibility
- **Zero Test Changes**: Existing tests work automatically with centralized instances
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently testable
- Commit after each task or logical group
- Verify singleton behavior: same object reference across imports
- Total: 33 tasks (Setup: 3, Foundational: 4, US1: 6, US2: 5, US3: 8, Polish: 7)

---

## Task Summary

**Total Tasks**: 33
- **Setup (Phase 1)**: 3 tasks
- **Foundational (Phase 2)**: 4 tasks (BLOCKING)
- **User Story 1 (Phase 3)**: 6 tasks - **MVP SCOPE**
- **User Story 2 (Phase 4)**: 5 tasks
- **User Story 3 (Phase 5)**: 8 tasks
- **Polish (Phase 6)**: 7 tasks

**Parallel Opportunities**: 11 tasks marked [P] can run in parallel within their phases

**Independent Test Criteria**:
- **US1**: Import centralized instances and verify singleton behavior
- **US2**: Toggle TESTING variable and verify correct LLM type (FakeChatModel vs ChatOpenAI)
- **US3**: Add new pattern to registry and verify FakeChatModel uses it

**Suggested MVP Scope**: Phases 1-3 only (Setup + Foundational + US1) = 13 tasks
