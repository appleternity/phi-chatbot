# Data Model: Centralized LLM Instance Management

**Feature**: 006-centralized-llm
**Date**: 2025-11-13

## Core Entities

### 1. LLMConfig

**Purpose**: Configuration model for LLM instance creation

**Attributes**:
- `temperature: float` - Response randomness (0.0-1.0), default 0.7
- `disable_streaming: bool` - Disable streaming responses, default False
- `tags: List[str]` - Metadata tags for LLM operations, default []

**Validation Rules**:
- `temperature` must be between 0.0 and 1.0 (inclusive)
- `tags` must be a list of strings (can be empty)
- `disable_streaming` must be boolean

**Relationships**:
- Used by `create_llm_instance()` factory function
- Consumed by both FakeChatModel (tests) and ChatOpenAI (production)

**Example**:
```python
# Normal LLM for user-facing responses
normal_config = LLMConfig(temperature=0.7, tags=[])

# Internal LLM for query expansion
internal_config = LLMConfig(
    temperature=1.0,
    tags=["internal-llm"],
    disable_streaming=True
)
```

### 2. LLM Instance (response_llm)

**Purpose**: Primary LLM instance for user-facing agent responses

**Type**: `BaseChatModel` (FakeChatModel in tests, ChatOpenAI in production)

**Configuration**:
- `temperature: 0.7` - Balanced creativity and consistency
- `disable_streaming: False` - Streaming enabled for better UX
- `tags: []` - No special tags

**Used by**:
- `supervisor.py`: Intent classification (could use temperature=0.1 for consistency)
- `emotional_support.py`: Empathetic responses
- `rag_agent.py`: RAG response generation (llm_generate instance)

**State**: Singleton (shared across entire application)

**Lifecycle**: Created at module import time, persists for application lifetime

### 3. LLM Instance (internal_llm)

**Purpose**: Internal LLM instance for background operations not visible to users

**Type**: `BaseChatModel` (FakeChatModel in tests, ChatOpenAI in production)

**Configuration**:
- `temperature: 1.0` - High creativity for diverse query variations
- `disable_streaming: True` - Streaming unnecessary for internal operations
- `tags: ["internal-llm"]` - Metadata for tracking/debugging internal calls

**Used by**:
- `advanced.py`: Query expansion (expand_query method)
- `rag_agent.py`: Intent classification (llm_classify instance)

**State**: Singleton (shared across entire application)

**Lifecycle**: Created at module import time, persists for application lifetime

### 4. ResponseRegistry

**Purpose**: Structured fake response patterns for FakeChatModel in test environment

**Structure**:
```python
{
    "supervisor_classification": {
        "emotional_keywords": List[str],
        "medical_keywords": List[str],
        "default_agent": str
    },
    "rag_classification": {
        "greeting_keywords": List[str],
        "medical_keywords": List[str],
        "default": str
    },
    "medical_responses": {
        str: str,  # medication_name -> response_text
        ...
    },
    "emotional_responses": {
        str: str,  # emotion_type -> response_text
        ...
    }
}
```

**Relationships**:
- Used exclusively by `FakeChatModel._generate()` method
- Enables deterministic test responses without embedded conditionals

**State**: Static configuration (read-only)

**Lifecycle**: Loaded at test initialization, used for all test LLM calls

## Data Flow

### Production Flow

```
Application Startup
    ↓
app/llm/instances.py imported
    ↓
create_llm_instance(config) called
    ↓
TESTING=false detected
    ↓
ChatOpenAI instance created
    ↓
Singleton instances exposed:
  - response_llm
  - internal_llm
    ↓
Agents import from app.llm
    ↓
LLM calls made via singleton instances
```

### Test Flow

```
Pytest Initialization
    ↓
conftest.py sets TESTING=true
    ↓
app/llm/instances.py imported
    ↓
create_llm_instance(config) called
    ↓
TESTING=true detected
    ↓
FakeChatModel instance created
    ↓
Singleton instances exposed:
  - response_llm (FakeChatModel)
  - internal_llm (FakeChatModel)
    ↓
Agents import from app.llm
    ↓
LLM calls made via FakeChatModel
    ↓
ResponseRegistry consulted
    ↓
Deterministic responses returned
```

## State Transitions

### LLM Instance Lifecycle

```
NOT_INITIALIZED → INITIALIZING → READY → TERMINATED
```

**NOT_INITIALIZED**: Before module import
- No instances exist
- Module not loaded

**INITIALIZING**: During module import (app/llm/instances.py)
- `create_llm_instance()` factory called
- Environment variable checked
- Instance creation in progress

**READY**: After module import
- Singleton instances available
- Agents can import and use instances
- Remains in this state for application lifetime

**TERMINATED**: Application shutdown
- Instances garbage collected
- No cleanup needed (stateless)

### Configuration Immutability

**LLMConfig instances are immutable** - once created, configuration cannot change.

Rationale:
- Prevents accidental configuration drift
- Ensures consistent LLM behavior across application
- Simplifies reasoning about LLM state

If different configuration needed:
- Use the other pre-configured instance (response_llm vs internal_llm)
- Create custom instance via `create_llm_instance(custom_config)` (edge case)

## Type Contracts

### Public API

```python
# app/llm/__init__.py
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

class LLMConfig(BaseModel):
    temperature: float = 0.7
    disable_streaming: bool = False
    tags: List[str] = []

def create_llm_instance(config: LLMConfig) -> BaseChatModel:
    """Create LLM instance based on environment and configuration."""
    ...

# Pre-configured singleton instances
response_llm: BaseChatModel
internal_llm: BaseChatModel
```

### Internal Contracts

```python
# tests/fakes/response_registry.py
ResponsePattern = Dict[str, Any]
ResponseRegistry = Dict[str, ResponsePattern]

RESPONSE_PATTERNS: ResponseRegistry
```

## Migration Impact

### Before (Distributed)

```python
# In each agent file
from app.agents.base import create_llm

llm = create_llm(temperature=0.7)
```

**Problems**:
- Configuration duplication (5 files)
- Test setup complexity
- No single source of truth

### After (Centralized)

```python
# In each agent file
from app.llm import response_llm

# Use singleton instance directly (no configuration needed)
response = response_llm.invoke(messages)
```

**Benefits**:
- Zero configuration duplication
- Automatic test/prod switching
- Single source of truth
- Type-safe imports

## Validation Checklist

- [ ] LLMConfig validates temperature range (0.0-1.0)
- [ ] LLMConfig validates tags is list of strings
- [ ] create_llm_instance() respects TESTING environment variable
- [ ] Singleton instances are truly singletons (same object reference across imports)
- [ ] FakeChatModel integrates with ResponseRegistry
- [ ] Production LLM instances connect to ChatOpenAI with correct settings
- [ ] All existing tests pass with centralized instances
- [ ] Type hints verified with mypy
