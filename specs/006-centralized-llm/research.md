# Research: Centralized LLM Instance Management

**Feature**: 006-centralized-llm
**Date**: 2025-11-13
**Status**: Complete

## Research Questions

### 1. How should we handle LLM instance lifecycle management?

**Decision**: Singleton pattern with module-level initialization

**Rationale**:
- **Import-time initialization**: LLM instances created when `app.llm` module is imported
- **Thread-safe**: Python's module import mechanism provides built-in thread safety
- **Zero overhead**: No locks, no complex lazy loading logic
- **Predictable**: Instance state is established at application startup

**Alternatives considered**:
- Lazy initialization: Rejected - adds complexity with locks and race conditions
- Dependency injection: Rejected - overkill for this use case, adds boilerplate
- Factory with caching: Rejected - unnecessary complexity when singleton suffices

**Implementation approach**:
```python
# app/llm/instances.py
from app.llm.config import LLMConfig, create_llm_instance

# Module-level singleton instances (created at import time)
response_llm = create_llm_instance(LLMConfig(temperature=0.7, tags=[]))
internal_llm = create_llm_instance(LLMConfig(temperature=1.0, tags=["internal-llm"], disable_streaming=True))
```

### 2. How should we automatically switch between test and production LLMs?

**Decision**: Environment-based factory function in centralized config

**Rationale**:
- **Existing pattern**: Current `create_llm()` already uses `TESTING` environment variable
- **Zero changes needed**: Test infrastructure (conftest.py) already sets `TESTING=true`
- **Explicit**: Clear separation between test and production behavior
- **Type-safe**: Returns `BaseChatModel` - works for both FakeChatModel and ChatOpenAI

**Alternatives considered**:
- Pytest fixtures for injection: Rejected - requires changing all agent signatures
- Monkey patching: Rejected - error-prone, breaks type safety
- Separate test/prod modules: Rejected - code duplication, harder to maintain

**Implementation approach**:
```python
# app/llm/config.py
import os
from langchain_core.language_models import BaseChatModel

def create_llm_instance(config: LLMConfig) -> BaseChatModel:
    """Create LLM instance based on environment."""
    if os.getenv("TESTING", "false").lower() == "true":
        from tests.fakes.fake_chat_model import FakeChatModel
        return FakeChatModel()

    from langchain_openai import ChatOpenAI
    from app.config import settings

    return ChatOpenAI(
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key,
        model=settings.model_name,
        temperature=config.temperature,
        disable_streaming=config.disable_streaming,
        tags=config.tags
    )
```

### 3. How should we organize fake response patterns for better maintainability?

**Decision**: Response registry pattern with context-based lookup

**Rationale**:
- **Current problem**: FakeChatModel has 300+ lines of embedded conditionals (hard to maintain)
- **Registry approach**: Separate response patterns into structured dictionary
- **Context-aware**: Response patterns organized by agent context (supervisor, rag, emotional_support)
- **Extensible**: Adding new patterns requires single dictionary entry

**Alternatives considered**:
- External JSON file: Rejected - adds file I/O, harder to debug, loses type safety
- Separate FakeChatModel per agent: Rejected - code duplication, harder to share patterns
- LLM response mocking library: Rejected - introduces dependency, overkill for our needs

**Implementation approach**:
```python
# tests/fakes/response_registry.py
RESPONSE_PATTERNS = {
    "supervisor_classification": {
        "emotional_keywords": ["anxious", "depressed", "sad", ...],
        "medical_keywords": ["medication", "drug", "treatment", ...],
        "default_agent": "rag_agent"
    },
    "rag_classification": {
        "greeting_keywords": ["thank", "hello", "hi", ...],
        "medical_keywords": ["medication", "aripiprazole", ...],
        "default": "retrieve"
    },
    "medical_responses": {
        "sertraline": "Based on the medical information: Sertraline (Zoloft)...",
        "bupropion": "Based on the medical information: Bupropion (Wellbutrin)...",
        ...
    },
    "emotional_responses": {
        "anxiety": "I understand that you're feeling anxious...",
        "depression": "I hear that you're feeling down...",
        ...
    }
}
```

### 4. How should we handle modules that need custom LLM configuration?

**Decision**: Provide two pre-configured instances + factory for edge cases

**Rationale**:
- **80/20 rule**: 95% of use cases covered by two instances (normal + internal)
- **Current usage analysis**:
  - `supervisor.py`: temperature=0.1 (closest to response_llm)
  - `emotional_support.py`: temperature=1.0 (use response_llm with default)
  - `rag_agent.py`: temperature=0.1 (classify), temperature=1.0 (generate) - use both instances
  - `advanced.py`: temperature=1.0, tags=["internal-llm"] - exact match for internal_llm
- **Edge cases**: Expose `create_llm_instance(config)` factory for rare custom needs

**Alternatives considered**:
- Multiple pre-configured instances (3+): Rejected - over-engineering, adds confusion
- Only factory function (no pre-configured): Rejected - defeats purpose of centralization
- Temperature as parameter to get_llm(): Rejected - breaks singleton pattern, adds state management

**Implementation approach**:
```python
# app/llm/__init__.py
from app.llm.instances import response_llm, internal_llm
from app.llm.config import LLMConfig, create_llm_instance

# Primary API: pre-configured instances
__all__ = ["response_llm", "internal_llm", "create_llm_instance"]

# Usage in agents:
from app.llm import response_llm  # For most agents
from app.llm import internal_llm  # For internal operations (query expansion)
from app.llm import create_llm_instance, LLMConfig  # For rare edge cases
```

### 5. How should we migrate existing code to use centralized instances?

**Decision**: Phased migration with deprecation period

**Rationale**:
- **Fail fast**: Break changes immediately to force migration
- **Clear migration path**: Import from `app.llm` instead of calling `create_llm()`
- **Backward compatibility**: Keep `create_llm()` with deprecation warning for 1-2 commits
- **Type safety**: Both old and new patterns return `BaseChatModel`

**Migration strategy**:
1. **Phase 1** (this feature): Create `app/llm/` module with centralized instances
2. **Phase 2** (this feature): Refactor agents to use centralized instances
3. **Phase 3** (this feature): Mark `create_llm()` as deprecated with warning
4. **Phase 4** (next commit): Remove `create_llm()` and `app/agents/base.py`

**Alternatives considered**:
- Big bang migration: Rejected - too risky, hard to review
- Gradual migration per agent: Rejected - inconsistent state, confusing for developers
- Keep both approaches: Rejected - defeats purpose of centralization

## Summary of Decisions

| Question | Decision | Key Benefit |
|----------|----------|-------------|
| Lifecycle management | Singleton pattern (module-level init) | Zero overhead, thread-safe |
| Test/prod switching | Environment-based factory | No changes to test infrastructure |
| Fake response organization | Response registry pattern | Maintainable, extensible |
| Custom configuration | Two instances + factory | Covers 95% of cases, edge cases supported |
| Migration approach | Phased with deprecation | Safe, clear migration path |

## References

- Existing implementation: `app/agents/base.py:create_llm()`
- Test infrastructure: `tests/conftest.py:set_test_environment()`
- Fake responses: `tests/fakes/fake_chat_model.py:FakeChatModel._generate()`
- Current usage:
  - `app/agents/supervisor.py:25` (temperature=0.1)
  - `app/agents/emotional_support.py:16` (temperature=1.0)
  - `app/agents/rag_agent.py:107-108` (temperature=0.1, temperature=1.0)
  - `app/retrieval/advanced.py:56` (temperature=1.0, tags=["internal-llm"])
