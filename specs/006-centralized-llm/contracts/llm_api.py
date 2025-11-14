"""API Contract: Centralized LLM Instance Management

This contract defines the public API for centralized LLM instance management.
All modules should use this API to access LLM instances instead of creating their own.

Contract Version: 1.0.0
"""

from typing import List
from pydantic import BaseModel, Field, field_validator
from langchain_core.language_models import BaseChatModel


# ============================================================================
# Configuration Models
# ============================================================================

class LLMConfig(BaseModel):
    """Configuration for LLM instance creation.

    Attributes:
        temperature: Response randomness (0.0-1.0)
            - 0.0: Deterministic, focused responses
            - 0.7: Balanced creativity and consistency (default)
            - 1.0: Maximum creativity and diversity
        disable_streaming: Disable streaming responses for internal operations
        tags: Metadata tags for LLM operations (debugging, tracking)

    Examples:
        >>> # Normal LLM for user-facing responses
        >>> normal_config = LLMConfig(temperature=0.7, tags=[])
        >>>
        >>> # Internal LLM for query expansion
        >>> internal_config = LLMConfig(
        ...     temperature=1.0,
        ...     tags=["internal-llm"],
        ...     disable_streaming=True
        ... )
    """

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Response randomness (0.0-1.0)"
    )
    disable_streaming: bool = Field(
        default=False,
        description="Disable streaming responses"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Metadata tags for LLM operations"
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate tags are strings and non-empty."""
        if not isinstance(v, list):
            raise ValueError("tags must be a list")

        for tag in v:
            if not isinstance(tag, str):
                raise ValueError(f"All tags must be strings, got {type(tag)}")
            if not tag.strip():
                raise ValueError("Tags cannot be empty strings")

        return v

    model_config = {
        "frozen": True,  # Immutable configuration
        "str_strip_whitespace": True,
    }


# ============================================================================
# Public API Contract
# ============================================================================

def create_llm_instance(config: LLMConfig) -> BaseChatModel:
    """Create LLM instance based on environment and configuration.

    Environment Detection:
        - TESTING=true: Returns FakeChatModel (deterministic, fast, free)
        - TESTING=false or unset: Returns ChatOpenAI (production LLM)

    Args:
        config: LLM configuration (temperature, streaming, tags)

    Returns:
        BaseChatModel instance (FakeChatModel or ChatOpenAI)

    Examples:
        >>> # Production usage (TESTING=false)
        >>> config = LLMConfig(temperature=0.7)
        >>> llm = create_llm_instance(config)
        >>> # Returns: ChatOpenAI instance

        >>> # Test usage (TESTING=true)
        >>> config = LLMConfig(temperature=0.7)
        >>> llm = create_llm_instance(config)
        >>> # Returns: FakeChatModel instance

    Contract Guarantees:
        - Returns BaseChatModel type (compatible with LangChain)
        - Respects TESTING environment variable
        - Applies all configuration parameters
        - Thread-safe singleton pattern
    """
    raise NotImplementedError("Contract definition - see implementation in app/llm/config.py")


# ============================================================================
# Singleton Instance Contract
# ============================================================================

# Pre-configured singleton instances (created at module import time)
# These are module-level variables in app/llm/instances.py

response_llm: BaseChatModel = None  # type: ignore
"""Normal LLM instance for user-facing responses.

Configuration:
    - temperature: 0.7 (balanced creativity)
    - disable_streaming: False (streaming enabled)
    - tags: [] (no special tags)

Used by:
    - app/agents/supervisor.py: Intent classification
    - app/agents/emotional_support.py: Empathetic responses
    - app/agents/rag_agent.py: RAG response generation

Usage:
    >>> from app.llm import response_llm
    >>> response = response_llm.invoke(messages)
"""

internal_llm: BaseChatModel = None  # type: ignore
"""Internal LLM instance for background operations.

Configuration:
    - temperature: 1.0 (high creativity for diversity)
    - disable_streaming: True (streaming unnecessary)
    - tags: ["internal-llm"] (metadata for tracking)

Used by:
    - app/retrieval/advanced.py: Query expansion
    - app/agents/rag_agent.py: Intent classification

Usage:
    >>> from app.llm import internal_llm
    >>> response = internal_llm.invoke(messages)
"""


# ============================================================================
# Migration Contract
# ============================================================================

class MigrationGuide:
    """Migration guide for transitioning to centralized LLM instances.

    BEFORE (Distributed):
        ```python
        from app.agents.base import create_llm

        # Each agent creates its own instance
        llm = create_llm(temperature=0.7)
        response = llm.invoke(messages)
        ```

    AFTER (Centralized):
        ```python
        from app.llm import response_llm

        # Use pre-configured singleton instance
        response = response_llm.invoke(messages)
        ```

    Breaking Changes:
        - app.agents.base.create_llm() is DEPRECATED (will be removed)
        - All modules must import from app.llm instead

    Edge Cases (Custom Configuration):
        ```python
        # If you need custom configuration (rare)
        from app.llm import create_llm_instance, LLMConfig

        custom_config = LLMConfig(temperature=0.5, tags=["custom"])
        custom_llm = create_llm_instance(custom_config)
        ```

    Test Impact:
        - No changes needed to test infrastructure
        - conftest.py already sets TESTING=true
        - FakeChatModel automatically activated
    """
    pass


# ============================================================================
# Test Contract
# ============================================================================

class TestResponseRegistry:
    """Contract for test response registry structure.

    The response registry provides deterministic fake responses for testing.
    Structure:
        {
            "supervisor_classification": {
                "emotional_keywords": ["anxious", "depressed", ...],
                "medical_keywords": ["medication", "drug", ...],
                "default_agent": "rag_agent"
            },
            "rag_classification": {
                "greeting_keywords": ["thank", "hello", ...],
                "medical_keywords": ["medication", "aripiprazole", ...],
                "default": "retrieve"
            },
            "medical_responses": {
                "sertraline": "Based on the medical information...",
                ...
            },
            "emotional_responses": {
                "anxiety": "I understand that you're feeling anxious...",
                ...
            }
        }

    Usage:
        >>> # In FakeChatModel._generate()
        >>> from tests.fakes.response_registry import RESPONSE_PATTERNS
        >>>
        >>> context = determine_context(messages)
        >>> pattern = RESPONSE_PATTERNS[context]
        >>> response = match_response(pattern, user_message)
    """
    pass


# ============================================================================
# Contract Validation
# ============================================================================

def validate_contract_compliance():
    """Validation checklist for contract compliance.

    Module Structure:
        - [ ] app/llm/__init__.py exports: response_llm, internal_llm, create_llm_instance
        - [ ] app/llm/instances.py defines singleton instances
        - [ ] app/llm/config.py implements create_llm_instance()
        - [ ] tests/fakes/response_registry.py defines RESPONSE_PATTERNS

    Type Safety:
        - [ ] All functions return BaseChatModel
        - [ ] LLMConfig is immutable (frozen=True)
        - [ ] Temperature validated (0.0-1.0 range)
        - [ ] Tags validated (list of non-empty strings)

    Behavior:
        - [ ] TESTING=true returns FakeChatModel
        - [ ] TESTING=false returns ChatOpenAI
        - [ ] Singleton instances are same object across imports
        - [ ] Configuration applied correctly to both test and prod instances

    Migration:
        - [ ] app/agents/supervisor.py imports from app.llm
        - [ ] app/agents/emotional_support.py imports from app.llm
        - [ ] app/agents/rag_agent.py imports from app.llm
        - [ ] app/retrieval/advanced.py imports from app.llm
        - [ ] app/agents/base.py marked as deprecated
    """
    pass
