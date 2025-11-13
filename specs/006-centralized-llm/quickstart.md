# Quickstart: Centralized LLM Instance Management

**Feature**: 006-centralized-llm
**Date**: 2025-11-13
**Estimated Reading Time**: 5 minutes

## Overview

This feature centralizes LLM instance management from distributed `create_llm()` calls to a singleton pattern with two pre-configured instances. It automatically switches between FakeChatModel (tests) and ChatOpenAI (production) based on the `TESTING` environment variable.

**Benefits**:
- ✅ Zero configuration duplication (5 `create_llm()` calls → 1 centralized factory)
- ✅ Automatic test/prod mode switching (no test infrastructure changes needed)
- ✅ Deterministic test responses via centralized response registry
- ✅ Single source of truth for LLM configuration
- ✅ Type-safe imports with `BaseChatModel` protocol

## Quick Start

### For New Code (Recommended)

```python
# Import pre-configured singleton instances
from app.llm import response_llm, internal_llm

# Use response_llm for user-facing responses
response = response_llm.invoke(messages)

# Use internal_llm for internal operations (query expansion, classification)
response = internal_llm.invoke(messages)
```

### For Migration (Existing Code)

**Before** (distributed):
```python
from app.agents.base import create_llm

llm = create_llm(temperature=0.7)
response = llm.invoke(messages)
```

**After** (centralized):
```python
from app.llm import response_llm

# Use singleton instance directly (no configuration needed)
response = response_llm.invoke(messages)
```

### For Edge Cases (Custom Configuration)

```python
# Rare: custom configuration not covered by pre-configured instances
from app.llm import create_llm_instance, LLMConfig

custom_config = LLMConfig(temperature=0.5, tags=["custom-agent"])
custom_llm = create_llm_instance(custom_config)
response = custom_llm.invoke(messages)
```

## Instance Configuration

### response_llm (User-Facing)

**Configuration**:
- `temperature: 0.7` - Balanced creativity and consistency
- `disable_streaming: False` - Streaming enabled for better UX
- `tags: []` - No special tags

**Used by**:
- `app/agents/supervisor.py` - Intent classification
- `app/agents/emotional_support.py` - Empathetic responses
- `app/agents/rag_agent.py` - RAG response generation

**Example**:
```python
from app.llm import response_llm

# Supervisor classification
response = response_llm.invoke(SUPERVISOR_PROMPT.format(message=user_message))

# Emotional support response
response = await response_llm.ainvoke(messages)
```

### internal_llm (Background Operations)

**Configuration**:
- `temperature: 1.0` - High creativity for diverse outputs
- `disable_streaming: True` - Streaming unnecessary for internal operations
- `tags: ["internal-llm"]` - Metadata for tracking/debugging

**Used by**:
- `app/retrieval/advanced.py` - Query expansion (generate diverse variations)
- `app/agents/rag_agent.py` - Intent classification (retrieve vs respond)

**Example**:
```python
from app.llm import internal_llm

# Query expansion
response = internal_llm.invoke(expansion_prompt)

# Intent classification
response = await internal_llm.ainvoke([HumanMessage(content=classification_prompt)])
```

## Test Environment

### Automatic Test Mode Switching

**No changes needed to test infrastructure!** Tests automatically use `FakeChatModel` when `TESTING=true` is set (already configured in `conftest.py`).

```python
# In conftest.py (already exists)
@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    os.environ["TESTING"] = "true"  # Automatically activates FakeChatModel
    yield
```

### Writing Tests with Centralized Instances

```python
# tests/integration/test_agent.py
from app.llm import response_llm  # Returns FakeChatModel in test environment

async def test_agent_response():
    """Test agent generates response using centralized LLM."""
    # No setup needed - FakeChatModel automatically activated

    response = await response_llm.ainvoke([
        HumanMessage(content="I'm feeling anxious")
    ])

    # FakeChatModel returns deterministic response from registry
    assert "anxious" in response.content.lower()
```

### Extending Fake Responses

```python
# tests/fakes/response_registry.py
RESPONSE_PATTERNS = {
    "medical_responses": {
        # Add new medication response
        "new_medication": "Based on the medical information: New medication info...",
    },
    "emotional_responses": {
        # Add new emotional support response
        "frustration": "I hear your frustration. Let's work through this together.",
    }
}
```

## Migration Guide

### Step-by-Step Migration

1. **Identify usage** - Find all `create_llm()` calls:
   ```bash
   grep -r "create_llm" app/
   ```

2. **Choose instance** - Determine which instance to use:
   - User-facing? → `response_llm`
   - Internal operation? → `internal_llm`
   - Custom config? → `create_llm_instance(custom_config)`

3. **Update imports**:
   ```python
   # Remove
   from app.agents.base import create_llm

   # Add
   from app.llm import response_llm  # or internal_llm
   ```

4. **Remove instantiation**:
   ```python
   # Remove
   llm = create_llm(temperature=0.7)

   # Use singleton directly
   response = response_llm.invoke(messages)
   ```

5. **Run tests** - Verify all tests pass:
   ```bash
   pytest tests/
   ```

### Migration Checklist

- [ ] `app/agents/supervisor.py` - Change `create_llm(temperature=0.1)` to `response_llm`
- [ ] `app/agents/emotional_support.py` - Change `create_llm(temperature=1.0)` to `response_llm`
- [ ] `app/agents/rag_agent.py` - Change both instances:
  - `create_llm(temperature=0.1, tags=["internal-llm"])` → `internal_llm`
  - `create_llm(temperature=1.0)` → `response_llm`
- [ ] `app/retrieval/advanced.py` - Change `create_llm(temperature=1.0, tags=["internal-llm"])` to `internal_llm`
- [ ] `app/agents/base.py` - Mark `create_llm()` as deprecated

## Common Issues

### Issue: Import Error - Module Not Found

**Symptom**:
```python
ImportError: cannot import name 'response_llm' from 'app.llm'
```

**Solution**:
Ensure `app/llm/` module is created with proper `__init__.py`:
```python
# app/llm/__init__.py
from app.llm.instances import response_llm, internal_llm
from app.llm.config import create_llm_instance, LLMConfig

__all__ = ["response_llm", "internal_llm", "create_llm_instance", "LLMConfig"]
```

### Issue: Type Checker Errors

**Symptom**:
```
error: Module has no attribute "response_llm"
```

**Solution**:
Add type annotations to `app/llm/instances.py`:
```python
from langchain_core.language_models import BaseChatModel

response_llm: BaseChatModel = create_llm_instance(LLMConfig(temperature=0.7))
internal_llm: BaseChatModel = create_llm_instance(LLMConfig(temperature=1.0, tags=["internal-llm"]))
```

### Issue: Tests Using Real LLM Instead of FakeChatModel

**Symptom**:
Tests make actual API calls and fail with authentication errors.

**Solution**:
Verify `TESTING` environment variable is set in test environment:
```python
# tests/conftest.py
import os
os.environ["TESTING"] = "true"  # Must be set BEFORE app imports
```

### Issue: FakeChatModel Returns Unexpected Responses

**Symptom**:
Tests fail because FakeChatModel returns generic response instead of expected pattern.

**Solution**:
Add new response patterns to `tests/fakes/response_registry.py`:
```python
RESPONSE_PATTERNS = {
    "medical_responses": {
        "your_medication": "Your expected response here...",
    }
}
```

## Performance Considerations

### Singleton Pattern Benefits

- **Zero overhead**: Instances created once at module import time
- **No locks**: Python's module import mechanism provides thread safety
- **Predictable**: Instance state established at application startup
- **Memory efficient**: Single instance shared across entire application

### Test Performance

- **Before**: Each test creates new LLM instance (~10ms overhead per test)
- **After**: Tests reuse singleton FakeChatModel (~0ms overhead)
- **Speedup**: Negligible per test, but cleaner architecture

## Next Steps

1. **Verify setup**: Import centralized instances in a test file
2. **Run tests**: Ensure all tests pass with centralized instances
3. **Migrate agents**: Update agents one by one following migration guide
4. **Review PR**: Check for any missed `create_llm()` calls
5. **Remove deprecated code**: After verification, remove `app/agents/base.py:create_llm()`

## Reference

- **Spec**: [spec.md](./spec.md)
- **Research**: [research.md](./research.md)
- **Data Model**: [data-model.md](./data-model.md)
- **API Contract**: [contracts/llm_api.py](./contracts/llm_api.py)
- **Implementation Plan**: [plan.md](./plan.md)

## Support

For questions or issues:
1. Check this quickstart guide
2. Review [data-model.md](./data-model.md) for entity relationships
3. Consult [contracts/llm_api.py](./contracts/llm_api.py) for API details
4. Review existing agent implementations for usage examples
