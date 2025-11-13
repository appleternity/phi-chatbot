"""Text processing utilities for LLM output normalization."""

import re


def normalize_llm_output(text: str) -> str:
    """Normalize LLM output for consistent validation.

    LLMs often add formatting variations to short responses even when
    explicitly instructed to output plain text:
    - Surrounding quotes: "rag_agent" or 'emotional_support'
    - Case variations: RAG_AGENT, Rag_Agent
    - Extra whitespace

    This function normalizes these harmless variations to prevent validation failures.

    Args:
        text: Raw LLM output string

    Returns:
        Normalized string: stripped, unquoted, lowercase

    Examples:
        >>> normalize_llm_output("  'rag_agent'  ")
        'rag_agent'
        >>> normalize_llm_output('"EMOTIONAL_SUPPORT"')
        'emotional_support'
        >>> normalize_llm_output('  "retrieve"  ')
        'retrieve'
        >>> normalize_llm_output("respond")
        'respond'
    """
    # Strip whitespace and remove all surrounding quotes/whitespace in one pass
    # Pattern: '^[\s"\']+' removes leading whitespace and quotes
    #          '[\s"\']+$' removes trailing whitespace and quotes
    normalized = re.sub(r'^[\s"\']+|[\s"\']+$', '', text)

    # Convert to lowercase
    return normalized.lower()
