# Tasks: API Bearer Token Authentication

**Input**: Design documents from `/specs/001-api-bearer-auth/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included as this feature requires security validation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `app/`, `tests/` at repository root
- Paths follow existing FastAPI application structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and authentication module structure

- [X] T001 Create authentication module directory structure at app/core/auth/
- [X] T002 [P] Create __init__.py in app/core/auth/ to expose public API
- [X] T003 [P] Update .env.example with API_BEARER_TOKEN placeholder and documentation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core authentication infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Add API_BEARER_TOKEN field to Settings class in app/core/config.py with Pydantic validation (required, min_length=64, hexadecimal validation)
- [X] T005 [P] Create error models (ErrorCode enum, AuthError Pydantic model) in app/core/auth/models.py
- [X] T006 [P] Implement token validation function using secrets.compare_digest() in app/core/auth/bearer_token.py
- [X] T007 [P] Create authentication logging utilities in app/core/auth/logging.py (log success/failure, never log token values)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Protected API Access with Bearer Token (Priority: P1) 🎯 MVP

**Goal**: Protect the /chat endpoint with Bearer token authentication so unauthorized clients cannot access chat functionality

**Independent Test**: Make requests to /chat with and without valid Bearer token, verify only authenticated requests are processed (200 OK with valid token, 401 Unauthorized without token or with invalid token)

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US1] Contract test for authentication error response format in tests/contract/test_auth_contract.py (verify AuthError schema: detail string, error_code enum)
- [X] T009 [P] [US1] Unit tests for token validation logic in tests/unit/test_bearer_token.py (valid token, invalid token, empty token, whitespace, constant-time comparison)
- [X] T010 [P] [US1] Integration test for /chat authentication flow in tests/integration/test_auth_integration.py (valid token → 200, missing token → 401 MISSING_TOKEN, invalid token → 401 INVALID_TOKEN, malformed header → 401 MALFORMED_HEADER)

### Implementation for User Story 1

- [X] T011 [US1] Implement FastAPI dependency verify_bearer_token() using HTTPBearer in app/core/auth/dependencies.py (extract token, validate, return token if valid, raise HTTPException 401 if invalid)
- [X] T012 [US1] Add Depends(verify_bearer_token) to /chat endpoint in app/main.py to enable authentication
- [X] T013 [US1] Add authentication logging calls (success/failure) in verify_bearer_token() dependency
- [X] T014 [US1] Update main.py startup sequence to validate API_BEARER_TOKEN at application startup (fail-fast if token missing or invalid)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently - /chat requires valid Bearer token, returns 401 with clear error codes for auth failures

---

## Phase 4: User Story 2 - Token Configuration (Priority: P1)

**Goal**: Enable administrators to configure the API token via environment variable for secure deployment and token rotation without code changes

**Independent Test**: Set API_BEARER_TOKEN environment variable, start service, verify only requests with that specific token are accepted. Change token and restart, verify old tokens rejected and new token accepted. Test startup failures with missing/invalid tokens.

### Tests for User Story 2

- [X] T015 [P] [US2] Unit tests for Settings validation in tests/unit/test_config.py (valid token ≥64 hex chars, too short → ValueError, non-hex → ValueError, empty → ValueError, whitespace trimming)
- [X] T016 [P] [US2] Integration test for token rotation in tests/integration/test_token_rotation.py (start with token A, verify works, restart with token B, verify A rejected and B accepted)
- [X] T017 [P] [US2] Integration test for concurrent authenticated requests in tests/integration/test_concurrent_auth.py (send 100 simultaneous requests with valid token, verify all succeed with <5ms p99 latency)

### Implementation for User Story 2

- [X] T018 [US2] Add Pydantic validator to API_BEARER_TOKEN field in app/core/config.py to enforce hexadecimal format validation (case-insensitive, 0-9 a-f A-F only)
- [X] T019 [US2] Add startup validation check in main.py to verify token meets security requirements before service starts (fail with clear error message if validation fails)
- [X] T020 [US2] Update quickstart.md with administrator token generation and configuration instructions (verify examples match validation rules)
- [X] T021 [US2] Update .env.example with detailed comments explaining token requirements (64+ hex chars, generation commands, security notes)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - administrators can configure tokens securely, service validates configuration at startup, token rotation requires only restart

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T022 [P] Update OpenAPI documentation in auth-api.yaml to reflect final implementation (verify security scheme, error codes, examples)
- [X] T023 [P] Add detailed docstrings to all authentication functions in app/core/auth/ (include security considerations, timing attack prevention, logging behavior)
- [X] T024 Add comprehensive error messages to Settings validators in app/core/config.py (specify exact requirements: 64+ hex chars, show example)
- [X] T025 [P] Update main CLAUDE.md with authentication setup instructions and configuration guidelines
- [X] T026 Run quickstart.md validation (test all administrator and client examples, verify token generation commands work, test authentication scenarios)
- [X] T027 [P] Security review of authentication implementation (verify no token logging, constant-time comparison, fail-fast validation, clear error messages)
- [X] T028 Performance validation of token validation latency (verify <5ms p99 authentication overhead, test with 1000+ concurrent requests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User Story 1 and User Story 2 can proceed in parallel (both are P1 priority)
  - User Story 2 enhances User Story 1 but both are independently testable
- **Polish (Phase 5)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on User Story 2
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on User Story 1 (validates same config that US1 uses)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundation (config, models, utilities) before dependencies
- Dependencies before endpoint integration
- Core implementation before logging/validation enhancements
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T002 and T003 can run in parallel (different files)
- **Foundational (Phase 2)**: T005, T006, T007 can run in parallel after T004 completes (T004 creates config that others depend on)
- **User Story 1 Tests**: T008, T009, T010 can all run in parallel (different test files)
- **User Story 2 Tests**: T015, T016, T017 can all run in parallel (different test files)
- **Polish**: T022, T023, T025, T027 can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for authentication error response format in tests/contract/test_auth_contract.py"
Task: "Unit tests for token validation logic in tests/unit/test_bearer_token.py"
Task: "Integration test for /chat authentication flow in tests/integration/test_auth_integration.py"

# After tests are written and failing, launch parallel foundational tasks:
Task: "Create error models in app/core/auth/models.py"
Task: "Implement token validation in app/core/auth/bearer_token.py"
Task: "Create authentication logging in app/core/auth/logging.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task: "Unit tests for Settings validation in tests/unit/test_config.py"
Task: "Integration test for token rotation in tests/integration/test_token_rotation.py"
Task: "Integration test for concurrent requests in tests/integration/test_concurrent_auth.py"

# After tests are written and failing, launch parallel implementation tasks:
Task: "Add hexadecimal validator to API_BEARER_TOKEN in app/core/config.py"
Task: "Update quickstart.md with administrator instructions"
Task: "Update .env.example with detailed token requirements"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T008-T014)
4. **STOP and VALIDATE**: Test /chat authentication independently
5. Deploy/demo if ready - basic Bearer token authentication working

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! - /chat protected with Bearer token)
3. Add User Story 2 → Test independently → Deploy/Demo (Enhanced! - strict token validation, clear startup errors)
4. Add Polish → Final validation → Production ready
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (critical shared infrastructure)
2. Once Foundational is done:
   - Developer A: User Story 1 (endpoint protection)
   - Developer B: User Story 2 (configuration validation)
3. Stories complete and integrate independently
4. Both developers collaborate on Polish phase

---

## Summary Statistics

- **Total Tasks**: 28 tasks
- **Setup Phase**: 3 tasks
- **Foundational Phase**: 4 tasks (BLOCKING)
- **User Story 1 (P1)**: 7 tasks (3 tests + 4 implementation)
- **User Story 2 (P1)**: 7 tasks (3 tests + 4 implementation)
- **Polish Phase**: 7 tasks

### Parallel Opportunities Identified

- **Setup**: 2 tasks can run in parallel
- **Foundational**: 3 tasks can run in parallel (after T004)
- **US1 Tests**: 3 tasks can run in parallel
- **US2 Tests**: 3 tasks can run in parallel
- **Polish**: 4 tasks can run in parallel

### Independent Test Criteria

**User Story 1**: Can be fully tested by making authenticated and unauthenticated requests to /chat:
- Valid token → 200 OK with chat response
- Missing token → 401 MISSING_TOKEN
- Invalid token → 401 INVALID_TOKEN
- Malformed header → 401 MALFORMED_HEADER

**User Story 2**: Can be fully tested by configuration validation:
- Valid token (≥64 hex chars) → service starts successfully
- Invalid token (too short, non-hex, empty) → service fails with clear error
- Token rotation → old tokens rejected, new token accepted
- Concurrent requests → all succeed with <5ms p99 latency

### Suggested MVP Scope

**Minimum Viable Product**: Complete User Story 1 only
- Delivers core security value: /chat endpoint protected with Bearer token authentication
- Clear error messages for authentication failures
- Stateless validation using constant-time comparison
- Authentication event logging (success/failure, never log tokens)

**Enhanced MVP**: Complete User Stories 1 + 2
- Adds strict token validation at startup (64+ hex chars)
- Fail-fast configuration errors with clear messages
- Supports secure token rotation workflow
- Production-ready security configuration

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Security is critical: verify no token logging, constant-time comparison, fail-fast validation
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
