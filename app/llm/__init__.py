"""Centralized LLM instance management.

This module provides a singleton pattern for LLM instances with automatic
test/production mode switching based on the TESTING environment variable.

Public API:
    - response_llm: Pre-configured instance for user-facing responses (temp=0.7)
    - internal_llm: Pre-configured instance for internal operations (temp=1.0, tags=["internal-llm"])
    - create_llm: Factory function for custom configurations (edge cases only)

Usage:
    from app.llm import response_llm, internal_llm

    # User-facing agent
    response = await response_llm.ainvoke(messages)

    # Internal operation (query expansion, classification)
    response = await internal_llm.ainvoke(messages)
"""

from app.llm.factory import create_llm
from app.llm.instances import internal_llm, response_llm

__all__ = ["response_llm", "internal_llm", "create_llm"]
