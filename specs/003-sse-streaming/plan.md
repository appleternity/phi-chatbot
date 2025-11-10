# Implementation Plan: SSE Streaming for Real-Time Chat Responses

**Branch**: `003-sse-streaming` | **Date**: 2025-11-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-sse-streaming/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement Server-Sent Events (SSE) streaming to deliver real-time token-by-token responses from LLM provider to frontend, replacing the current blocking HTTP request/response pattern. The system will stream processing stages (retrieval, reranking, generation) and tokens as they arrive, providing immediate user feedback and eliminating perceived wait times.

**Technical approach**: Leverage LangGraph 0.6.0's native event streaming API (`astream_events()`) to capture LLM tokens and processing stages, convert to SSE format via FastAPI's `StreamingResponse`, and consume via browser EventSource API on frontend.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.115+, LangGraph 0.6.0, LangChain-Core 0.3+, uvicorn 0.32+ with httpx 0.27+ for async streaming
**Storage**: PostgreSQL 15+ with pgvector (existing - no changes needed)
**Testing**: pytest 8.3+, pytest-asyncio 0.24+, httpx for SSE client testing
**Target Platform**: Linux/macOS server with Docker Compose for PostgreSQL
**Project Type**: Web application (FastAPI backend + React frontend)
**Performance Goals**:
- First token within 1 second of query submission
- Token delivery latency <100ms from LLM provider receipt
- Support 10+ concurrent streaming sessions without degradation
- Stage transition indicators within 200ms
**Constraints**:
- Must maintain conversation context across streaming requests
- Must handle connection interruptions gracefully (30s timeout)
- Must integrate with existing LangGraph multi-agent architecture
- Must preserve session-aware routing and checkpointing
**Scale/Scope**:
- Single-feature MVP for existing medical chatbot
- 2 new backend endpoints (SSE streaming + cancellation)
- 1 modified frontend component (chat interface)
- ~500-800 LOC backend + ~300-500 LOC frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: N/A - No constitution file found (placeholder template only)

**Analysis**: The project constitution file (`.specify/memory/constitution.md`) contains only placeholder content with no actual principles defined. This indicates either:
1. The project is new and constitution has not been established yet
2. The constitution is documented elsewhere
3. Constitutional checks are not enforced for this project

**Recommendation**: Proceed with Phase 0 research and Phase 1 design. Apply standard software engineering principles:
- **Fail-fast**: SSE connection errors should surface immediately
- **Simplicity**: Use LangGraph's native streaming APIs without custom wrappers
- **Testing**: Integration tests for SSE streaming lifecycle
- **Separation of Concerns**: Backend streaming logic separate from frontend rendering

**Re-check trigger**: After Phase 1 design artifacts are generated, verify if any architecture decisions violate common patterns (e.g., unnecessary abstraction layers, tight coupling between streaming and business logic).

## Project Structure

### Documentation (this feature)

```text
specs/003-sse-streaming/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── sse_events.py    # SSE event type definitions and schemas
│   └── streaming_api.py # FastAPI streaming endpoint contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Web application structure (FastAPI backend + React frontend)
backend/ (app/)
├── api/                           # NEW: API layer for HTTP endpoints
│   ├── __init__.py
│   ├── chat.py                    # MODIFIED: Extract non-streaming chat from main.py
│   └── streaming.py               # NEW: SSE streaming endpoint (/chat/stream)
├── agents/                        # EXISTING: Agent implementations
│   ├── rag_agent.py               # MODIFIED: Support streaming token emission
│   ├── supervisor.py              # EXISTING: No changes (non-streaming node)
│   └── emotional_support.py       # EXISTING: No changes (non-streaming node)
├── core/                          # EXISTING: Core utilities
│   ├── session_store.py           # EXISTING: No changes
│   ├── postgres_retriever.py      # EXISTING: No changes
│   └── qwen3_reranker.py          # EXISTING: No changes
├── graph/                         # EXISTING: LangGraph definitions
│   ├── builder.py                 # MODIFIED: Add streaming mode support
│   └── state.py                   # EXISTING: No changes
├── models.py                      # MODIFIED: Add StreamEvent schema
├── main.py                        # MODIFIED: Move /chat logic to api/chat.py
└── config.py                      # EXISTING: No changes (may add stream timeout config)

frontend/
├── src/
│   ├── components/
│   │   └── ChatInterface.tsx      # MODIFIED: Add SSE EventSource, stop button, stage indicators
│   ├── hooks/
│   │   └── useStreamingChat.ts    # NEW: Custom hook for SSE connection management
│   └── types/
│       └── streaming.ts           # NEW: TypeScript types for SSE events
└── package.json                   # EXISTING: No new dependencies (EventSource is native)

tests/
├── integration/
│   ├── test_streaming_api.py      # NEW: End-to-end SSE streaming tests
│   └── test_streaming_lifecycle.py # NEW: Connection lifecycle tests (cancel, timeout)
└── unit/
    └── test_sse_events.py         # NEW: Event serialization/parsing tests
```

**Structure Decision**: The existing web application structure (FastAPI backend in `app/` + React frontend in `frontend/`) is preserved. New streaming functionality is added via:

1. **Backend**:
   - `app/api/streaming.py`: New SSE endpoint (`POST /chat/stream`) using FastAPI's `StreamingResponse`
   - `app/api/chat.py`: Extracted non-streaming endpoint from `main.py` for separation of concerns
   - `app/models.py`: Extended with `StreamEvent` Pydantic model for SSE event schema
   - `app/graph/builder.py`: Modified to support streaming mode via LangGraph's `astream_events()` API

2. **Frontend**:
   - `frontend/src/hooks/useStreamingChat.ts`: Encapsulates EventSource lifecycle, reconnection logic, and state management
   - `frontend/src/components/ChatInterface.tsx`: Modified to use streaming hook, render progressive tokens, and show stage indicators
   - `frontend/src/types/streaming.ts`: TypeScript definitions for SSE event types

3. **Testing**:
   - `tests/integration/test_streaming_api.py`: Full SSE streaming workflow tests using httpx streaming client
   - `tests/unit/test_sse_events.py`: Unit tests for event serialization and schema validation

This structure minimizes changes to the existing multi-agent system while adding streaming as a parallel capability alongside the original blocking `/chat` endpoint (preserved for backward compatibility and testing).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Not applicable - no constitution violations detected. Standard web streaming patterns are being applied.

---

## Phase 0: Research & Technical Investigation

**Status**: Pending

**Research Tasks**:

1. **LangGraph 0.6.0 Streaming API Investigation**
   - Task: "Research LangGraph `astream_events()` API for token-level streaming and event types"
   - Focus: Event types (on_chat_model_stream, on_llm_start), filtering by node name, handling non-streaming nodes
   - Deliverable: Code examples showing how to capture tokens from RAG agent while skipping supervisor/emotional_support

2. **FastAPI SSE Implementation Patterns**
   - Task: "Research FastAPI StreamingResponse best practices for SSE with proper content-type headers"
   - Focus: Async generator patterns, SSE format (`data:` prefix, `\n\n` delimiter), error handling in streams
   - Deliverable: Minimal working example of SSE endpoint with event types (token, stage, done, error)

3. **Frontend EventSource API Patterns**
   - Task: "Research browser EventSource API usage, reconnection handling, and React integration patterns"
   - Focus: Manual connection closure, error recovery, AbortController integration, React hooks for streaming state
   - Deliverable: React hook design for managing EventSource lifecycle with TypeScript

4. **Session State Management During Streaming**
   - Task: "Research how to preserve LangGraph checkpointing and session state with streaming responses"
   - Focus: Difference between `ainvoke()` and `astream_events()`, when to save session state, handling cancellation
   - Deliverable: Sequence diagram showing state persistence points in streaming flow

5. **Error Handling and Cancellation Patterns**
   - Task: "Research SSE connection cancellation patterns and backend detection mechanisms"
   - Focus: Client-side AbortController, server-side connection close detection, LangGraph task cancellation
   - Deliverable: Error handling taxonomy (network errors, LLM timeouts, user cancellation, backend errors)

**Research Output**: Will be consolidated into `research.md` with architectural decisions and code examples.

---

## Phase 1: Design & Contracts

**Status**: Pending (blocked by Phase 0)

**Prerequisites**: Research tasks from Phase 0 must be complete, particularly LangGraph streaming API patterns and FastAPI SSE implementation.

### Artifacts to Generate

1. **data-model.md**
   - Entity: `StreamEvent` (type: retrieval_start|retrieval_complete|reranking_start|reranking_complete|token|done|error, content: string|dict, timestamp: ISO8601)
   - Entity: `StreamingSession` (session_id: UUID, status: active|cancelled|completed|error, accumulated_tokens: list[str], current_stage: string|None)
   - Entity: `CancellationRequest` (session_id: UUID, reason: user_initiated|timeout|error)

2. **contracts/ Directory**
   - `contracts/sse_events.py`: Pydantic schemas for all SSE event types with validation rules
   - `contracts/streaming_api.py`: FastAPI endpoint signatures, request/response models, SSE format specification

3. **quickstart.md**
   - Developer guide for testing SSE streaming locally
   - Example curl/httpx commands for SSE endpoint
   - Frontend development workflow (npm scripts, hot reload with SSE)
   - Troubleshooting section (connection refused, token delays, cancellation not working)

4. **Agent Context Update**
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
   - Add technologies: "SSE (Server-Sent Events)", "FastAPI StreamingResponse", "EventSource API"
   - Preserve existing technologies from pyproject.toml

**Design Validation Checkpoints**:
- [ ] SSE event schema covers all functional requirements (FR-008: retrieval, reranking, token, completion, error events)
- [ ] Streaming endpoint supports both progressive tokens and stage indicators (FR-004, FR-005)
- [ ] Session state persistence mechanism defined for streaming mode (FR-012)
- [ ] Cancellation workflow includes both frontend and backend detection (FR-018, FR-019)
- [ ] Error handling covers network failures, timeouts, and LLM errors (FR-010, FR-014)

---

## Phase 2: Task Breakdown

**Status**: Not started (handled by `/speckit.tasks` command - NOT part of `/speckit.plan`)

**Note**: This section is informational only. Task generation is performed by the `/speckit.tasks` command which reads this plan and generates executable, dependency-ordered tasks in `tasks.md`.

**Expected Task Categories**:
1. Backend streaming infrastructure (FastAPI SSE endpoint, event formatters)
2. LangGraph integration (astream_events() wrappers, token capture, stage emission)
3. Frontend streaming UI (EventSource hook, progressive rendering, stop button)
4. Session management (state persistence during streaming, cancellation handling)
5. Testing (integration tests for streaming lifecycle, unit tests for event parsing)
6. Documentation (API docs, developer guide, troubleshooting)

---

## Success Criteria Mapping

**How this plan addresses spec success criteria**:

- **SC-001** (first token <1s): Achieved via LangGraph's `astream_events()` immediate token emission after retrieval stage
- **SC-002** (token latency <100ms): FastAPI async generators ensure near-real-time delivery from LangGraph events
- **SC-003** (stage indicators <200ms): Stage events emitted at each LangGraph node transition (retrieval_start, retrieval_complete, etc.)
- **SC-004** (95% success rate): Comprehensive error handling for network failures, LLM timeouts, and connection drops
- **SC-005** (perceived real-time): Progressive token rendering via React state updates on each SSE event
- **SC-006** (10 concurrent sessions): FastAPI async architecture + LangGraph checkpointing supports concurrent streams
- **SC-007** (error feedback <2s): SSE error events trigger immediate UI error messages with retry options
- **SC-008** (70% wait time reduction): Measured by first visible content (stage indicator) vs. original blocking response time

---

## Implementation Notes

### Key Architectural Decisions (Post-Research)

**To be filled after Phase 0 research completion**:
- LangGraph streaming mode: `astream_events()` vs. `astream()` choice
- SSE event ID strategy: Sequential integers, UUIDs, or timestamp-based
- Session state persistence timing: After token accumulation or after stream completion
- Cancellation detection mechanism: Polling, connection state checks, or AsyncIO task cancellation
- Frontend state management: React useState vs. useReducer for token accumulation

### Known Risks and Mitigations

1. **Risk**: LangGraph `astream_events()` may emit events from all nodes, not just LLM token chunks
   - **Mitigation**: Event filtering by node name and event type in backend before SSE emission

2. **Risk**: EventSource API has limited error information (only `error` event, no details)
   - **Mitigation**: Backend emits structured error events via SSE before closing connection

3. **Risk**: Session state may be incomplete if stream is cancelled mid-generation
   - **Mitigation**: Accumulate tokens in backend buffer, save partial response on cancellation

4. **Risk**: Frontend may not detect backend disconnection immediately (30s browser timeout)
   - **Mitigation**: Backend sends periodic heartbeat events (every 5s) during long processing stages

### Performance Targets

**Backend**:
- Token emission latency: <50ms from LangGraph event to SSE output
- Retrieval stage duration: <1.5s (existing PostgreSQL + reranking pipeline)
- Memory overhead per stream: <10MB (token buffer + event queue)

**Frontend**:
- Token rendering latency: <50ms from EventSource message to DOM update
- UI responsiveness: No frame drops during token streaming (60 FPS maintained)
- Memory cleanup: EventSource connection closed and garbage collected within 1s of completion

**End-to-End**:
- Total latency (query → first token): <2s (retrieval 1.5s + LLM first token 0.5s)
- Total latency (token received → displayed): <100ms (backend 50ms + frontend 50ms)
