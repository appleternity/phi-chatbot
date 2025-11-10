# Tasks: SSE Streaming for Real-Time Chat Responses

**Input**: Design documents from `/specs/003-sse-streaming/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in the feature specification. Test tasks are included only for critical integration testing of the streaming lifecycle.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Web app structure: `app/` (backend), `frontend/` (React frontend)
- Tests: `tests/integration/`, `tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure (no new dependencies needed)

- [X] T001 Verify FastAPI 0.115+, LangGraph 0.6.0, uvicorn 0.32+ are installed per pyproject.toml
- [X] T002 [P] Create app/api/ directory structure for HTTP endpoints
- [X] T003 [P] Verify PostgreSQL + pgvector is running (docker-compose up -d)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core SSE infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Copy StreamEvent, StreamingSession, ChatStreamRequest models from specs/003-sse-streaming/contracts/sse_events.py to app/models.py
- [X] T005 [P] Copy stream_chat_events() generator from specs/003-sse-streaming/contracts/streaming_api.py to app/api/streaming.py
- [X] T006 [P] Create app/api/chat.py and extract existing /chat endpoint logic from app/main.py (preserve backward compatibility)
- [X] T007 Implement get_graph() dependency injection in app/api/streaming.py (return compiled LangGraph instance)
- [X] T008 Register streaming router in app/main.py: app.include_router(streaming.router)
- [X] T009 Add logging configuration for streaming operations (LOG_LEVEL=DEBUG support)

**Checkpoint**: Foundation ready - streaming endpoint exists, user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - See Partial Responses as They Generate (Priority: P1) 🎯 MVP

**Goal**: Users see response text appearing word-by-word in real-time as the AI generates it, with functional stop button to cancel streaming.

**Independent Test**: Send a single chat message via POST /chat/stream, observe token-by-token rendering in logs/httpx client. Click stop during streaming to verify cancellation works.

### Backend Implementation for User Story 1

- [X] T010 [P] [US1] Verify LangGraph astream_events() integration captures on_chat_model_stream events in app/api/streaming.py
- [X] T011 [P] [US1] Implement event filtering by langgraph_node in stream_chat_events() (only emit tokens from rag_agent, skip supervisor)
- [X] T012 [US1] Add client disconnect detection using request.is_disconnected() checks in stream_chat_events() loop
- [X] T013 [US1] Implement asyncio.timeout(30) wrapper around astream_events() for timeout handling (FR-014)
- [X] T014 [US1] Add asyncio.CancelledError handling to detect stop button clicks and emit cancelled event (FR-018, FR-019)
- [X] T015 [US1] Verify StreamingResponse headers include Cache-Control: no-cache, Connection: keep-alive, X-Accel-Buffering: no

### Frontend Implementation for User Story 1

- [X] T016 [P] [US1] Create frontend/src/types/streaming.ts with TypeScript types for StreamEvent (token, done, error, cancelled)
- [X] T017 [US1] Create frontend/src/hooks/useStreamingChat.ts hook with fetch() + ReadableStream pattern (not EventSource due to POST requirement)
- [X] T018 [US1] Implement AbortController integration in useStreamingChat.ts for stop button support (FR-018)
- [X] T019 [US1] Add token accumulation state management in useStreamingChat.ts (tokens: string[], isStreaming: boolean, error: string | null)
- [X] T020 [US1] Implement SSE parsing logic in useStreamingChat.ts (parse "data: " prefix, handle incomplete chunks with buffer)
- [X] T021 [US1] Modify frontend/src/components/ChatInterface.tsx to use useStreamingChat hook
- [X] T022 [US1] Transform send button to stop button when isStreaming=true in ChatInterface.tsx (FR-017)
- [X] T023 [US1] Disable text input field when isStreaming=true in ChatInterface.tsx (FR-016)
- [X] T024 [US1] Implement progressive token rendering in ChatInterface.tsx (append tokens to temporary message bubble)
- [X] T025 [US1] Re-enable text input and revert stop button to send button after stream completes/cancels (FR-020)
- [X] T026 [US1] Add conversation context preservation check after cancellation (verify session_id maintained) (FR-021)

### Integration Testing for User Story 1

- [X] T027 [US1] Create tests/integration/test_streaming_lifecycle.py with httpx streaming client test
- [X] T028 [US1] Add test case: verify tokens arrive progressively (assert len(tokens) > 0, assert token latency)
- [X] T029 [US1] Add test case: verify done event closes stream cleanly
- [X] T030 [US1] Add test case: verify client disconnect triggers cancellation (simulate abort during streaming)
- [X] T031 [US1] Add test case: verify session state preserved after cancellation (send new message after cancel)

**Checkpoint**: At this point, User Story 1 should be fully functional - users can see streaming responses and cancel them with the stop button

---

## Phase 4: User Story 2 - Visual Progress Indicators During Processing (Priority: P2)

**Goal**: Users see clear indicators of what stage the system is in (searching knowledge base, reranking results, generating response).

**Independent Test**: Send a query and observe stage transitions in UI: "Searching knowledge base..." → "Reranking results..." → "Generating response..." with smooth transitions.

### Backend Implementation for User Story 2

- [ ] T032 [P] [US2] Emit retrieval_start event when rag_agent node starts (on_chain_start event with node=rag_agent) in app/api/streaming.py
- [ ] T033 [P] [US2] Emit retrieval_complete event when reranking begins (detect reranking node start, infer retrieval completion) in app/api/streaming.py
- [ ] T034 [P] [US2] Emit reranking_start event when reranking node starts in app/api/streaming.py
- [ ] T035 [P] [US2] Emit reranking_complete event before first LLM token (on_chat_model_stream triggers generation stage) in app/api/streaming.py
- [ ] T036 [US2] Update StreamingSession.current_stage field to track classifying, retrieval, reranking, generation in app/api/streaming.py

### Frontend Implementation for User Story 2

- [ ] T037 [P] [US2] Add stage state to useStreamingChat.ts hook (stage: string, default: "")
- [ ] T038 [US2] Implement stage event handling in useStreamingChat.ts (parse retrieval_start, retrieval_complete, reranking_start, reranking_complete)
- [ ] T039 [US2] Add stage indicator UI component in ChatInterface.tsx (e.g., "Status: Searching knowledge base...")
- [ ] T040 [US2] Map stage event types to user-friendly messages: retrieval → "Searching knowledge base...", reranking → "Reranking results...", generation → "Generating response..."
- [ ] T041 [US2] Add smooth stage transition animations in ChatInterface.tsx (fade in/out or slide transitions)

### Integration Testing for User Story 2

- [ ] T042 [US2] Add test case in tests/integration/test_streaming_lifecycle.py: verify stage events emitted in correct order (retrieval_start → retrieval_complete → reranking_start → reranking_complete → tokens)
- [ ] T043 [US2] Add test case: verify stage transition timing <200ms between events (SC-003)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - users see both streaming tokens and processing stage indicators

---

## Phase 5: User Story 3 - Graceful Handling of Connection Issues (Priority: P3)

**Goal**: When network connectivity is interrupted or the streaming connection fails, users receive clear error messages and can retry without losing conversation context.

**Independent Test**: Simulate network interruption during streaming (disable network in browser DevTools), verify error message appears with retry option, verify conversation context preserved after retry.

### Backend Implementation for User Story 3

- [ ] T044 [P] [US3] Implement asyncio.TimeoutError handling in stream_chat_events() (emit timeout error event after 30s) in app/api/streaming.py
- [ ] T045 [P] [US3] Implement generic Exception handling in stream_chat_events() (emit internal error event without exposing details) in app/api/streaming.py
- [ ] T046 [US3] Add error logging for all error paths (timeout, cancellation, unexpected errors) in app/api/streaming.py
- [ ] T047 [US3] Verify StreamingSession.error_message field is set when errors occur in app/api/streaming.py

### Frontend Implementation for User Story 3

- [ ] T048 [P] [US3] Add error state handling in useStreamingChat.ts (error: string | null)
- [ ] T049 [US3] Implement error event parsing in useStreamingChat.ts (detect error event, extract message, update error state)
- [ ] T050 [US3] Implement network error handling in useStreamingChat.ts (catch fetch() exceptions, distinguish AbortError from network errors)
- [ ] T051 [US3] Add error display UI in ChatInterface.tsx (show error message below chat input)
- [ ] T052 [US3] Add retry button in ChatInterface.tsx (appears when error state is set, resends last message)
- [ ] T053 [US3] Implement automatic retry with exponential backoff in useStreamingChat.ts (optional enhancement: retry 3 times with 1s, 2s, 4s delays)

### Integration Testing for User Story 3

- [ ] T054 [US3] Add test case in tests/integration/test_streaming_lifecycle.py: simulate timeout by mocking slow LLM (verify timeout error event after 30s)
- [ ] T055 [US3] Add test case: verify error event handling (inject error during graph execution, verify error event emitted)
- [ ] T056 [US3] Add test case: verify session context preserved after error (send new message after error, verify session_id maintained)

**Checkpoint**: All user stories should now be independently functional - streaming works, stages visible, errors handled gracefully

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T057 [P] Add performance logging to track first token latency (log time from request start to first token) in app/api/streaming.py
- [ ] T058 [P] Add token count and stream duration logging to stream completion in app/api/streaming.py
- [ ] T059 [P] Update specs/003-sse-streaming/quickstart.md with actual curl test commands and expected outputs (validate all examples work)
- [ ] T060 Create developer test script test_streaming.py with httpx client example from quickstart.md
- [ ] T061 [P] Verify StreamingResponse buffering is disabled (test token latency <100ms with real LLM calls)
- [ ] T062 Add frontend console logging toggle (localStorage.setItem('DEBUG_STREAMING', 'true') enables verbose logs)
- [ ] T063 [P] Run full end-to-end test: backend + frontend + PostgreSQL with real query
- [ ] T064 [P] Verify concurrent session support (test 10+ simultaneous streams without degradation - SC-006)
- [ ] T065 Cleanup: Remove any debug console.log statements from frontend code
- [ ] T066 Update CLAUDE.md with new technologies: "SSE (Server-Sent Events)", "FastAPI StreamingResponse", "EventSource API"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 streaming infrastructure but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Builds on US1 error handling but independently testable

### Within Each User Story

- Backend tasks can run in parallel with frontend tasks (different codebases)
- Within backend: Models → services → endpoints
- Within frontend: Types → hooks → components
- Integration tests run after implementation tasks complete
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Backend and frontend tasks within a story can run in parallel
- All tasks marked [P] within a story can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Backend and frontend can work in parallel:
Backend Developer:
  Task T010: Verify astream_events() integration
  Task T011: Implement event filtering
  Task T012: Add disconnect detection

Frontend Developer:
  Task T016: Create streaming.ts types
  Task T017: Create useStreamingChat.ts hook
  Task T021: Modify ChatInterface.tsx

# Within backend - these can run in parallel:
Task T010: Verify astream_events()
Task T011: Implement event filtering
Task T012: Add disconnect detection
Task T013: Add timeout wrapper
Task T014: Add cancellation handling
Task T015: Verify response headers

# Within frontend - these can run in parallel:
Task T016: Create streaming.ts types
Task T019: Add state management
Task T020: Implement SSE parsing
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T009) - CRITICAL
3. Complete Phase 3: User Story 1 (T010-T031)
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Backend test: `curl -N -X POST http://localhost:8000/chat/stream -d '{"message":"test","session_id":"test-123"}'`
   - Frontend test: Open browser, send message, see streaming, click stop
   - Integration test: `pytest tests/integration/test_streaming_lifecycle.py`
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! - streaming works)
3. Add User Story 2 → Test independently → Deploy/Demo (stage indicators added)
4. Add User Story 3 → Test independently → Deploy/Demo (error handling robust)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T009)
2. Once Foundational is done:
   - **Developer A (Backend)**: User Story 1 backend (T010-T015), User Story 2 backend (T032-T036), User Story 3 backend (T044-T047)
   - **Developer B (Frontend)**: User Story 1 frontend (T016-T026), User Story 2 frontend (T037-T041), User Story 3 frontend (T048-T053)
   - **Developer C (Testing)**: Integration tests for all stories (T027-T031, T042-T043, T054-T056)
3. Stories complete and integrate independently
4. Polish phase (T057-T066) done together after all stories complete

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story (US1, US2, US3) for traceability
- Each user story should be independently completable and testable
- Integration tests verify the streaming lifecycle end-to-end
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: blocking dependencies between stories, same file conflicts

---

## Success Criteria Validation

After completing all phases, verify:

- **SC-001**: First token within 1 second (test with performance.now() timing in T057)
- **SC-002**: Token latency <100ms (verify in T061)
- **SC-003**: Stage transitions <200ms (test in T043)
- **SC-004**: 95% success rate (monitor in production after deployment)
- **SC-005**: Real-time perception (user testing feedback)
- **SC-006**: 10+ concurrent sessions (test in T064)
- **SC-007**: Error feedback <2s (test in T054-T056)
- **SC-008**: 70% wait time reduction (compare vs. original blocking /chat endpoint)

---

## Total Task Count

- **Phase 1 (Setup)**: 3 tasks
- **Phase 2 (Foundational)**: 6 tasks
- **Phase 3 (User Story 1)**: 22 tasks (15 implementation + 5 integration tests)
- **Phase 4 (User Story 2)**: 12 tasks (10 implementation + 2 integration tests)
- **Phase 5 (User Story 3)**: 13 tasks (10 implementation + 3 integration tests)
- **Phase 6 (Polish)**: 10 tasks
- **Total**: 66 tasks

### Tasks per User Story

- **User Story 1 (P1 - MVP)**: 22 tasks (backend: 6, frontend: 11, testing: 5)
- **User Story 2 (P2)**: 12 tasks (backend: 5, frontend: 5, testing: 2)
- **User Story 3 (P3)**: 13 tasks (backend: 4, frontend: 6, testing: 3)

### Parallel Opportunities

- **Setup**: 2 parallel opportunities (T002, T003)
- **Foundational**: 2 parallel opportunities (T005, T006)
- **User Story 1**: 11 parallel opportunities (T010-T015 backend, T016 frontend, T019-T020 frontend)
- **User Story 2**: 5 parallel opportunities (T032-T035 backend, T037 frontend)
- **User Story 3**: 3 parallel opportunities (T044-T045 backend, T048-T049 frontend)
- **Polish**: 5 parallel opportunities (T057-T058, T059, T061-T062, T064)

### Suggested MVP Scope

**Recommended MVP**: User Story 1 only (Phase 1 + Phase 2 + Phase 3)
- **Total MVP tasks**: 31 tasks (3 setup + 6 foundational + 22 user story 1)
- **Core value**: Users see real-time streaming responses with functional stop button
- **Validation**: Integration tests verify streaming lifecycle works correctly
- **Deliverable**: Working SSE streaming endpoint + React frontend consuming it

**After MVP**: Add User Story 2 (stage indicators) → then User Story 3 (error handling) → then Polish
