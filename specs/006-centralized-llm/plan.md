# Implementation Plan: Centralized LLM Instance Management

**Branch**: `006-centralized-llm` | **Date**: 2025-11-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-centralized-llm/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Refactor LLM instance creation from distributed `create_llm()` calls across multiple files to a centralized singleton pattern with two pre-configured instances (normal LLM and internal-tagged LLM). This enables automatic test environment detection (FakeChatModel vs ChatOpenAI), eliminates configuration duplication, and simplifies test setup by providing controlled, deterministic LLM behavior through a centralized fake response registry.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LangChain-Core 0.3+, LangChain-OpenAI, Pydantic 2.x, pytest
**Storage**: N/A (configuration only, no data persistence)
**Testing**: pytest with FakeChatModel (existing test infrastructure)
**Target Platform**: Linux/macOS server (FastAPI application)
**Project Type**: Single project (web API backend)
**Performance Goals**: Zero overhead (simple module import, singleton pattern)
**Constraints**: Must maintain existing LLM configuration parameters (temperature, streaming, tags); Must work seamlessly with existing test infrastructure
**Scale/Scope**: 5 files currently using `create_llm()` (supervisor.py, emotional_support.py, rag_agent.py, advanced.py, base.py); ~200 lines of refactoring

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution File Status**: Template only (not project-specific). Using general development principles from CLAUDE.md and SuperClaude framework.

## Project Structure

### Documentation (this feature)

```text
specs/006-centralized-llm/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
app/
├── llm/                        # NEW: Centralized LLM module
│   ├── __init__.py            # Expose get_llm() factory function
│   ├── instances.py           # Singleton LLM instances (response_llm, internal_llm)
│   └── config.py              # LLM configuration models
│
├── agents/                     # MODIFIED: Remove create_llm() calls
│   ├── base.py                # DEPRECATED: create_llm() marked for removal
│   ├── supervisor.py          # REFACTOR: Import from app.llm
│   ├── emotional_support.py   # REFACTOR: Import from app.llm
│   └── rag_agent.py           # REFACTOR: Import from app.llm
│
├── retrieval/                  # MODIFIED: Remove create_llm() calls
│   └── advanced.py            # REFACTOR: Import from app.llm
│
└── config.py                   # UNCHANGED: Settings remain centralized

tests/
├── fakes/                      # MODIFIED: Organize fake response patterns
│   ├── fake_chat_model.py     # REFACTOR: Extract response registry
│   └── response_registry.py   # NEW: Centralized response patterns
│
├── unit/
│   └── llm/                   # NEW: Unit tests for centralized LLM
│       ├── test_instances.py
│       └── test_config.py
│
└── conftest.py                 # MODIFIED: Simplify test setup
```

**Structure Decision**: Single project structure (FastAPI backend). New `app/llm/` module provides centralized LLM instance management. Existing agents and retrievers refactored to import from centralized module instead of calling `create_llm()` locally. Test infrastructure enhanced with structured response registry for FakeChatModel.

## Complexity Tracking

**No constitution violations identified.** This refactoring simplifies the codebase by:
- Eliminating code duplication (5 `create_llm()` calls → 1 centralized factory)
- Improving testability (automatic test/prod mode switching)
- Reducing cognitive load (single source of truth for LLM configuration)

---

## Phase 0: Research (COMPLETE)

**Deliverable**: [research.md](./research.md)

**Research Questions Resolved**:
1. ✅ LLM instance lifecycle management → Singleton pattern with module-level initialization
2. ✅ Automatic test/prod switching → Environment-based factory function
3. ✅ Fake response organization → Response registry pattern
4. ✅ Custom configuration handling → Two instances + factory for edge cases
5. ✅ Migration approach → Phased migration with deprecation period

**Key Decisions**:
- Use singleton pattern (zero overhead, thread-safe)
- Maintain existing TESTING environment variable pattern
- Create response registry for maintainable fake responses
- Provide two pre-configured instances (response_llm, internal_llm)
- Fail-fast migration strategy (immediate breaking changes)

---

## Phase 1: Design & Contracts (COMPLETE)

**Deliverables**:
- ✅ [data-model.md](./data-model.md) - Entity relationships and state transitions
- ✅ [contracts/llm_api.py](./contracts/llm_api.py) - Public API contract definition
- ✅ [quickstart.md](./quickstart.md) - User-facing quick start guide
- ✅ [CLAUDE.md](../../CLAUDE.md) - Updated agent context

**Data Model**:
- `LLMConfig`: Pydantic model for LLM configuration (temperature, streaming, tags)
- `response_llm`: Singleton instance for user-facing responses (temp=0.7)
- `internal_llm`: Singleton instance for internal operations (temp=1.0, tags=["internal-llm"])
- `ResponseRegistry`: Structured fake response patterns for testing

**API Contract**:
- `create_llm_instance(config: LLMConfig) -> BaseChatModel`: Factory function
- Pre-configured instances: `response_llm`, `internal_llm`
- Migration guide and test contracts

**Agent Context Update**:
- Added Python 3.11+ with LangChain-Core 0.3+, LangChain-OpenAI, Pydantic 2.x
- Updated project structure documentation
- Added to "Recent Changes" section in CLAUDE.md

---

## Phase 2: Implementation Planning (NOT CREATED BY THIS COMMAND)

**Next Step**: Run `/speckit.tasks` command to generate implementation tasks.

**Expected Output**: `tasks.md` with dependency-ordered implementation tasks

**Implementation Scope**:
1. Create `app/llm/` module (config.py, instances.py, __init__.py)
2. Refactor agents to use centralized instances (supervisor.py, emotional_support.py, rag_agent.py)
3. Refactor retrievers (advanced.py)
4. Create response registry (tests/fakes/response_registry.py)
5. Deprecate `app/agents/base.py:create_llm()`
6. Write unit tests for centralized LLM module
7. Update integration tests to verify singleton behavior
8. Validate all existing tests pass

---

## Command Completion Summary

**Branch**: `006-centralized-llm`
**Implementation Plan**: `/Users/appleternity/workspace/phi-mental-development/langgraph-001-api-bearer-auth/specs/006-centralized-llm/plan.md`

**Artifacts Generated**:
- ✅ `plan.md` - This file (implementation plan)
- ✅ `research.md` - Phase 0 research decisions
- ✅ `data-model.md` - Entity relationships and data flow
- ✅ `contracts/llm_api.py` - Public API contract
- ✅ `quickstart.md` - User-facing quick start guide
- ✅ Updated `CLAUDE.md` - Agent context with new technology

**Next Steps**:
1. Review generated artifacts for completeness
2. Run `/speckit.tasks` to generate implementation tasks
3. Begin implementation following task order
4. Verify tests pass after each major refactoring step
5. Create PR for review
