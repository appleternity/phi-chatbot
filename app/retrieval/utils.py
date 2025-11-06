"""Utility functions for retrieval operations.

This module provides helper functions for normalizing retrieval inputs
and handling conversation history across different retriever strategies.
"""

from typing import List
from langchain_core.messages import BaseMessage


def _filter_and_slice_messages(
    messages: List[BaseMessage],
    max_messages: int,
    include_system: bool = False,
    message_types: tuple = ("human", "ai"),
) -> List[BaseMessage]:
    """Common logic for filtering and slicing messages.

    This is an internal helper function used by both extract_retrieval_query
    and format_conversation_context to avoid code duplication.

    Args:
        messages: List of conversation messages
        max_messages: Maximum number of recent messages to include
        include_system: Whether to include system messages
        message_types: Tuple of message types to include (e.g., ("human",) or ("human", "ai"))

    Returns:
        Filtered and sliced list of messages
    """
    # Filter by message type
    if include_system:
        # Include system messages in addition to specified types
        filtered = [msg for msg in messages if msg.type in message_types + ("system",)]
    else:
        # Only include specified message types (exclude system)
        filtered = [msg for msg in messages if msg.type in message_types]

    # Take last max_messages
    return filtered[-max_messages:] if max_messages > 0 else filtered


def extract_retrieval_query(
    query: List[BaseMessage],
    max_history: int = 1,
    include_system: bool = False,
) -> str:
    """Extract query string from conversation messages for retrieval operations.

    IMPORTANT: Only uses human messages to maintain search intent focus.
    AI responses are excluded to avoid diluting the retrieval query.
    System messages are excluded by default (set include_system=True to override).

    Args:
        query: List of conversation messages.
               Extracts content from last max_history human messages only.
        max_history: Number of recent messages to consider (default: 1)
                    - 1: Last message only (Simple/Rerank strategy)
                    - 3-5: Multi-turn context (Advanced strategy)
        include_system: Whether to include system messages (default: False)
                       System messages are typically not useful for retrieval.
                       Most retrieval use cases should keep this False.

    Returns:
        Query string suitable for retrieval operations, with messages joined by newlines

    Examples:
        >>> # Single message
        >>> messages = [HumanMessage(content="What are the side effects?")]
        >>> extract_retrieval_query(messages)
        "What are the side effects?"

        >>> # Multi-turn conversation - last human message only
        >>> messages = [
        ...     HumanMessage(content="Tell me about aripiprazole"),
        ...     AIMessage(content="Aripiprazole is an antipsychotic..."),
        ...     HumanMessage(content="What about side effects?")
        ... ]
        >>> extract_retrieval_query(messages, max_history=1)
        "What about side effects?"

        >>> # Multi-turn conversation - last 3 human messages only (AI excluded!)
        >>> messages = [
        ...     HumanMessage(content="Tell me about aripiprazole"),
        ...     AIMessage(content="Aripiprazole is an antipsychotic..."),
        ...     HumanMessage(content="What about side effects?"),
        ...     AIMessage(content="The main side effects are..."),
        ...     HumanMessage(content="What about children?")
        ... ]
        >>> extract_retrieval_query(messages, max_history=3)
        "Tell me about aripiprazole\\nWhat about side effects?\\nWhat about children?"

        >>> # Filter out system messages (default behavior)
        >>> messages = [
        ...     SystemMessage(content="You are a medical assistant"),
        ...     HumanMessage(content="What are the side effects?")
        ... ]
        >>> extract_retrieval_query(messages)
        "What are the side effects?"

    Edge Cases:
        - Empty list: returns empty string
        - All system messages: returns empty string (unless include_system=True)
        - All AI messages: returns empty string (only human messages are used)
        - max_history > len(messages): uses all available human messages
    """
    # Handle empty message list
    if not query:
        return ""

    # Use helper to filter and slice messages (human messages only!)
    filtered = _filter_and_slice_messages(
        query,
        max_messages=max_history,
        include_system=include_system,
        message_types=("human",)  # Human only for retrieval focus!
    )

    # Handle case where all messages were filtered out
    if not filtered:
        return ""

    # Extract content and join with newlines
    query_parts = [msg.content for msg in filtered if msg.content]
    return "\n".join(query_parts)


def format_conversation_context(
    messages: List[BaseMessage],
    max_messages: int = 5,
    include_system: bool = False,
    exclude_last_n: int = 0,
) -> str:
    """Format conversation messages into a readable context string.

    This is useful for debugging or creating human-readable representations
    of conversation history for logging or LLM prompts.

    Includes both human and AI messages to provide full conversation flow.
    System messages are excluded by default.

    Args:
        messages: List of conversation messages
        max_messages: Maximum number of recent messages to include (default: 5)
        include_system: Whether to include system messages (default: False)
        exclude_last_n: Exclude last N messages to avoid duplication (default: 0)
                       Useful when you've already extracted the last message as query.
                       This parameter makes the exclusion explicit and configurable.

    Returns:
        Formatted string with role labels, e.g.:
        "User: What are the side effects?\\nAssistant: The main side effects are..."

    Example:
        >>> messages = [
        ...     HumanMessage(content="Tell me about aripiprazole"),
        ...     AIMessage(content="It's an antipsychotic medication"),
        ...     HumanMessage(content="What about side effects?")
        ... ]
        >>> print(format_conversation_context(messages))
        User: Tell me about aripiprazole
        Assistant: It's an antipsychotic medication
        User: What about side effects?

        >>> # Extract last message as query, format previous messages as context
        >>> query = extract_retrieval_query(messages, max_history=1)
        >>> context = format_conversation_context(
        ...     messages,
        ...     max_messages=5,
        ...     exclude_last_n=1  # Don't duplicate the query message!
        ... )
        >>> print(context)
        User: Tell me about aripiprazole
        Assistant: It's an antipsychotic medication
    """
    if not messages:
        return ""

    # Filter and slice messages (both human and AI for full context!)
    filtered = _filter_and_slice_messages(
        messages,
        max_messages=max_messages,
        include_system=include_system,
        message_types=("human", "ai")  # Both for LLM context!
    )

    # Exclude last N messages if requested (to avoid duplication)
    if exclude_last_n > 0:
        filtered = filtered[:-exclude_last_n]

    # Handle case where all messages were filtered out
    if not filtered:
        return ""

    # Format with role labels
    formatted_parts = []
    for msg in filtered:
        role = {
            "human": "User",
            "ai": "Assistant",
            "system": "System"
        }.get(msg.type, "Unknown")

        formatted_parts.append(f"{role}: {msg.content}")

    return "\n".join(formatted_parts)
