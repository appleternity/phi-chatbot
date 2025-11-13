"""LLM factory function for centralized instance creation.

This module provides the core factory function that creates LLM instances
with automatic test/production mode switching based on the TESTING environment variable.
"""

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import settings


def create_llm(
    temperature: float = 0.7,
    disable_streaming: bool = False,
    tags: list[str] | None = None,
) -> BaseChatModel:
    """Create LLM instance with configured settings.

    In test environment (TESTING=true), returns FakeChatModel for:
    - Deterministic responses (no randomness)
    - 50-100x faster execution (no API calls)
    - Zero API costs
    - Offline testing capability

    In production environment, returns real ChatOpenAI for actual LLM calls.

    Args:
        temperature: Temperature for response generation (0.0-1.0)
                    Note: Ignored in test mode (FakeChatModel is deterministic)
        disable_streaming: Whether to disable streaming responses
        tags: Metadata tags for LLM operations (e.g., ["internal-llm"])

    Returns:
        BaseChatModel: FakeChatModel for tests, ChatOpenAI for production

    Examples:
        >>> # Simple usage (tests)
        >>> llm = create_llm()  # Returns FakeChatModel when TESTING=true
        >>>
        >>> # Custom configuration (production)
        >>> llm = create_llm(temperature=1.0, tags=["internal-llm"])
    """
    # Use fake LLM for tests (deterministic, fast, free)
    if os.getenv("TESTING", "false").lower() == "true":
        from tests.fakes.fake_chat_model import FakeChatModel

        print("🚀 Using FakeChatModel for testing environment")
        return FakeChatModel()

    # Production: real LLM with API calls
    print("🚀 Using ChatOpenAI for production environment")
    return ChatOpenAI(
        base_url=settings.openai_api_base,
        api_key=SecretStr(settings.openai_api_key) if isinstance(settings.openai_api_key, str) else settings.openai_api_key,
        model=settings.model_name,
        temperature=temperature,
        disable_streaming=disable_streaming,
        tags=tags or [],
    )
