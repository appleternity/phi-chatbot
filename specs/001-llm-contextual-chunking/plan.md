# Implementation Plan: LLM-Based Contextual Document Chunking for RAG

**Branch**: `001-llm-contextual-chunking` | **Date**: 2025-10-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-llm-contextual-chunking/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Python-based document chunking system that processes book chapters into semantically coherent, contextually-enriched chunks for RAG pipelines. The system uses LLM-driven structure analysis (via OpenRouter API) to identify document hierarchy, determine optimal semantic boundaries, and generate metadata-rich chunks with 100% text coverage verification. Implementation follows a three-phase approach: (1) structure identification with high-capability LLMs, (2) semantic boundary determination, (3) segmentation and text cleaning with cost-effective LLMs, leveraging both prompt caching and file-based caching for efficiency. All LLM outputs use TSV format (not JSON) for reliable parsing, with format examples included in prompts. CLI built with Typer, allowing per-phase model selection.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: OpenRouter API client, tiktoken (token counting), difflib/SequenceMatcher (text alignment), Pydantic (validation), NEEDS CLARIFICATION: specific OpenRouter SDK or requests library
**Storage**: File system (input: plain text/markdown, output: JSONL files), NEEDS CLARIFICATION: caching mechanism (file-based cache vs in-memory vs external service)
**Testing**: pytest, pytest-cov (coverage), NEEDS CLARIFICATION: mocking strategy for LLM API calls
**Target Platform**: Linux/macOS command-line scripts (Python environment)
**Project Type**: Single (command-line tool/library)
**Performance Goals**: Process 5000-word chapter in reasonable time (speed not critical per user feedback), 50%+ token reduction with caching enabled
**Constraints**: 100% text coverage (zero loss/duplication), 100% metadata completeness, fail-fast on errors, chunk size ≤1000 tokens
**Scale/Scope**: Batch processing 10-100 chapters, single-document and folder processing modes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Agent-First Architecture
**Status**: ⚠️ PARTIAL COMPLIANCE - Justification required

This feature is a document processing pipeline, not a multi-agent conversational system. However, the three-phase processing approach (structure → boundaries → segmentation) can be implemented as modular components with clear interfaces:
- Phase 1: StructureAnalyzer component
- Phase 2: BoundaryDetector component
- Phase 3: DocumentSegmenter component

Each component will have clear inputs/outputs and be independently testable with mocked LLM responses.

**Justification**: While not "agents" in the LangGraph sense, this follows the spirit of the principle by creating self-contained, testable components with clear boundaries.

### Principle II: State Management Discipline
**Status**: ✅ COMPLIANT

Processing state flows through typed data models:
- Document (input state)
- Structure (Phase 1 output)
- SegmentBoundary[] (Phase 2 output)
- Chunk[] (Phase 3 output)
- ProcessingReport (final state)

All state transitions use Pydantic models with immutable transformations.

### Principle III: Test-First Development (NON-NEGOTIABLE)
**Status**: ✅ COMPLIANT

TDD approach will be followed:
1. Write contract tests for component interfaces
2. Write integration tests for end-to-end processing
3. Implement components to pass tests
4. Achieve 80%+ unit test coverage, 70%+ integration coverage

### Principle IV: Observability & Debugging
**Status**: ✅ COMPLIANT

Structured logging will include:
- INFO: Phase transitions, document processing start/end, chunk counts
- DEBUG: Structure analysis results, boundary decisions, token counts
- ERROR: LLM failures, validation errors, text coverage mismatches

Each log entry includes document identifier and processing phase context.

### Principle V: Abstraction & Dependency Injection
**Status**: ✅ COMPLIANT

Abstract interfaces will be created for:
- LLMProvider (OpenRouter API abstraction for testing)
- CacheStore (file-based cache abstraction)
- FileReader (document input abstraction)
- ChunkWriter (JSONL output abstraction)

### Principle VI: Simplicity & Modularity (YAGNI)
**Status**: ✅ COMPLIANT

MVP focuses on core chunking functionality:
- Start with single-document processing (P1)
- Add batch processing only after P1 validated (P2)
- Add caching optimization as enhancement (P3)
- No speculative features beyond requirements

**Gate Result**: ✅ PASS (with Phase 1 design re-check required)

## Project Structure

### Documentation (this feature)

```text
specs/001-llm-contextual-chunking/
├── plan.md                        # This file (/speckit.plan command output)
├── research.md                    # Phase 0 output - Technical decisions
├── data-model.md                  # Phase 1 output - Pydantic models
├── quickstart.md                  # Phase 1 output - Developer guide
├── contracts/
│   ├── component_interfaces.md    # Component contracts & interfaces
│   └── prompt_templates.md        # LLM prompts with TSV format examples
└── tasks.md                       # Phase 2 output (/speckit.tasks command - NOT YET created)
```

### Source Code (repository root)

```text
src/
├── chunking/                     # NEW: Document chunking system
│   ├── __init__.py
│   ├── models.py                 # Pydantic models (Document, Structure, Chunk, etc.)
│   ├── structure_analyzer.py    # Phase 1: LLM-driven structure identification
│   ├── boundary_detector.py     # Phase 2: Semantic boundary determination
│   ├── document_segmenter.py    # Phase 3: Segmentation and text cleaning
│   ├── text_aligner.py          # Text coverage verification (difflib)
│   ├── metadata_validator.py    # Metadata completeness validation
│   ├── llm_provider.py          # Abstract LLM interface + OpenRouter impl
│   ├── cache_store.py           # Caching abstraction
│   ├── chunking_pipeline.py     # Main orchestrator (phases 1-3)
│   └── cli.py                   # Command-line interface
│
├── agents/                       # EXISTING: LangGraph agents (unchanged)
├── parenting/                    # EXISTING: Parenting agent (unchanged)
└── ...

tests/
├── chunking/                     # NEW: Tests for chunking system
│   ├── contract/
│   │   ├── test_structure_analyzer_contract.py
│   │   ├── test_boundary_detector_contract.py
│   │   └── test_document_segmenter_contract.py
│   ├── integration/
│   │   ├── test_end_to_end_chunking.py
│   │   ├── test_batch_processing.py
│   │   └── test_caching_workflow.py
│   └── unit/
│       ├── test_text_aligner.py
│       ├── test_metadata_validator.py
│       └── test_models.py
├── agents/                       # EXISTING: Agent tests (unchanged)
└── ...
```

**Structure Decision**: Single project structure with new `src/chunking/` module. The chunking system is independent from existing LangGraph agents and lives in its own namespace. This follows the existing codebase pattern (modular components under `src/`) and supports future integration if needed (e.g., a RAG agent could import from `src.chunking`).

## Constitution Check (Post-Design Re-evaluation)

*Re-evaluated after Phase 1 design completion*

### Principle I: Agent-First Architecture
**Status**: ✅ COMPLIANT (with justification accepted)

**Design Review**:
- Components implemented as modular, self-contained classes with clear interfaces
- StructureAnalyzer, BoundaryDetector, DocumentSegmenter follow single-responsibility principle
- All components independently testable with mock dependencies
- Clear input/output contracts defined in contracts/component_interfaces.md

**Justification Accepted**: While not LangGraph "agents", the component architecture follows the spirit of agent-first design with clear boundaries, interfaces, and testability.

### Principle II: State Management Discipline
**Status**: ✅ COMPLIANT

**Design Review**:
- All state transitions use typed Pydantic models (data-model.md)
- State flow: Document → Structure → SegmentBoundary[] → Chunk[] → ProcessingResult
- All models marked as immutable (frozen=True in Pydantic config)
- No mutable state shared between components

### Principle III: Test-First Development (NON-NEGOTIABLE)
**Status**: ✅ COMPLIANT

**Design Review**:
- Contract tests defined for all 9 component interfaces
- Integration tests planned for end-to-end workflows
- Unit tests planned for utilities and validators
- Test directory structure established in plan.md
- Mock implementations defined (MockLLMProvider, test fixtures)

**Next Steps**: Implement tests BEFORE components (TDD)

### Principle IV: Observability & Debugging
**Status**: ✅ COMPLIANT

**Design Review**:
- Structured logging planned at INFO, DEBUG, ERROR levels
- Each log entry includes document_id and processing phase
- Component interfaces specify error types and messages
- ProcessingReport and BatchReport capture execution metrics

### Principle V: Abstraction & Dependency Injection
**Status**: ✅ COMPLIANT

**Design Review**:
- Abstract interfaces: LLMProvider, CacheStore
- Concrete implementations: OpenRouterProvider, FileCacheStore
- Mock implementations for testing: MockLLMProvider
- All components accept dependencies via constructor injection

### Principle VI: Simplicity & Modularity (YAGNI)
**Status**: ✅ COMPLIANT

**Design Review**:
- MVP focuses on P1 (single document) + P2 (batch) + P3 (caching)
- No speculative features added
- Modular component design allows incremental implementation
- Clear separation between core pipeline and utilities

**Gate Result**: ✅ PASS - All constitution principles satisfied

## Complexity Tracking

> **No violations requiring justification**

The design follows all constitution principles with appropriate adaptations for document processing use case.
