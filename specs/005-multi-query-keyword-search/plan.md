# Implementation Plan: Multi-Query Expansion and Keyword Matching

**Branch**: `005-multi-query-keyword-search` | **Date**: 2025-11-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-multi-query-keyword-search/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

**Primary Requirement**: Enhance AdvancedRetriever to support up to 10 queries (vs fixed 4) and add optional keyword matching using PostgreSQL pg_trgm extension.

**Technical Approach** (Simplified):
1. Modify AdvancedRetriever: configurable `max_queries` parameter (default 10)
2. Simplify prompt: no key prefixes, just newline-separated queries
3. Add `_keyword_search()` method using pg_trgm + GIN index
4. Merge vector + keyword results by chunk_id (simple dict deduplication)
5. Add ONE config flag: `enable_keyword_search` (default: false)

**What we're NOT doing** (over-engineering removed):
- ❌ Query deduplication (waste of time, results already deduped by chunk_id)
- ❌ Complex Pydantic models (internal logic doesn't need exposure)
- ❌ New HybridRetriever class (just modify AdvancedRetriever)
- ❌ Special Chinese handling (already works in existing prompt)
- ❌ Multiple config parameters (YAGNI)

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- FastAPI 0.115+ (existing API layer)
- LangGraph 0.6.0 + LangChain-Core 0.3+ (agent orchestration)
- PostgreSQL 15+ with pgvector 0.8.0+ (vector search) and pg_trgm 1.6+ (trigram matching)
- asyncpg (async database operations)
- Pydantic 2.x (data validation)

**Storage**: PostgreSQL with pgvector + pg_trgm extensions
**Testing**: pytest with contract/integration/unit test hierarchy (TDD required by constitution)
**Target Platform**: Linux server (Docker containerized PostgreSQL)
**Project Type**: Single backend service (Python monorepo)

**Performance Goals**:
- Query expansion: <500ms for up to 10 queries (FR-002, SC-002)
- End-to-end retrieval: <3s total latency for top-5 results (SC-004)
- Parallel query execution for all sub-queries (FR-003)

**Constraints**:
- Backward compatibility: Existing retrieval strategies (simple, rerank, advanced) must continue working
- Zero downtime: Schema migration (pg_trgm extension + indexes) must be non-blocking
- Resource usage: Parallel queries must not overwhelm database connection pool

**Scale/Scope**:
- Modify AdvancedRetriever class (~100 lines added)
- Database migration: 2 SQL statements (enable pg_trgm + create GIN index)
- Config: 1 new parameter (`enable_keyword_search`)
- Test coverage: ~5 test cases (integration/unit, no complex contracts)

## Constitution Check (Simplified)

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Agent-First Architecture ✅
- **Status**: PASS
- **Rationale**: Changes isolated to retrieval layer (AdvancedRetriever). No agent-level changes.

### Principle II: State Management Discipline ✅
- **Status**: PASS
- **Rationale**: No LangGraph state changes. Retriever is stateless utility.

### Principle III: Test-First Development (NON-NEGOTIABLE) ✅
- **Status**: PASS (commitment required)
- **Plan**: TDD workflow:
  1. Integration tests for multi-query + keyword search
  2. Unit tests for result deduplication
  3. Red-green-refactor cycle
- **Simplified**: No complex contract tests needed (no new interface)

### Principle IV: Observability & Debugging ✅
- **Status**: PASS
- **Plan**: Structured logging with query_count, candidates_retrieved, search_time

### Principle V: Abstraction & Dependency Injection ✅
- **Status**: PASS
- **Rationale**: Uses existing RetrieverProtocol interface. No new dependencies.

### Principle VI: Simplicity & Modularity (YAGNI) ✅✅✅
- **Status**: PASS (Ultra-Simplified)
- **Rationale**:
  - Modify existing AdvancedRetriever (~100 lines)
  - No new classes, no new Pydantic models, no new abstractions
  - Simple dict deduplication (no query deduplication logic)
  - ONE config parameter (enable_keyword_search)
  - 2 SQL statements (enable extension + create index)

### Quality Gates (Simplified)
- **Test Coverage**: Integration tests + unit tests for deduplication
- **Performance**: <3s end-to-end (SC-004)
- **Security**: Parameterized SQL queries (existing pattern)

### Pre-Research Gate: ✅ PASS
**Decision**: Proceed to Phase 0 research. Design is simple, no violations.

---

## Post-Phase 1 Constitution Re-Check

*Re-evaluated after Phase 1 design (research.md, data-model.md, quickstart.md)*

**All 6 principles**: ✅ PASS

**Key Validations**:
- No new classes (modify AdvancedRetriever)
- No Pydantic models (not needed)
- Simple dict deduplication (no complex logic)
- ONE config parameter
- ~100 lines of code (not 500)

### Post-Design Gate: ✅✅✅ PASS (Ultra-Simplified)
**Decision**: Design phase complete. Ready for implementation. No over-engineering detected.

## Project Structure (Simplified)

### Documentation (this feature)

```text
specs/005-multi-query-keyword-search/
├── plan.md              # This file (design plan)
├── research.md          # Phase 0 (technical decisions)
├── data-model.md        # Phase 1 (database changes only)
├── quickstart.md        # Phase 1 (usage guide)
└── tasks.md             # Phase 2 (/speckit.tasks - NOT created yet)
```

**No contracts/**: Not needed (no new interface)

### Source Code (repository root)

```text
app/retrieval/advanced.py    # MODIFIED (~100 lines added)
app/db/schema.py             # MODIFIED (add enable_keyword_search() function)
app/config.py                # MODIFIED (add enable_keyword_search: bool)

tests/integration/test_advanced_retriever.py  # MODIFIED (add multi-query + keyword tests)
tests/unit/test_result_deduplication.py       # NEW (test _merge_results())
```

**That's it.** 3 files modified, 1 test file added.

**Structure Decision**: Single project (Python monorepo). Minimal changes to existing code. No new classes, no new abstractions.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**Status**: No complexity violations detected. All changes fit within existing architecture patterns (RetrieverProtocol interface, asyncpg database operations, TDD workflow).
