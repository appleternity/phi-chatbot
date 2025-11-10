"""Tests for retrieval utility functions.

Comprehensive tests for message extraction and formatting utilities
used across different retriever strategies.
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.retrieval.utils import extract_retrieval_query, format_conversation_context


class TestExtractRetrievalQuery:
    """Test extract_retrieval_query() function."""

    def test_empty_message_list(self):
        """Test that empty message lists return empty string."""
        result = extract_retrieval_query([])
        assert result == ""

    def test_single_human_message(self):
        """Test extraction from a single human message."""
        messages = [HumanMessage(content="What are the side effects?")]
        result = extract_retrieval_query(messages)
        assert result == "What are the side effects?"

    def test_single_ai_message_returns_empty(self):
        """Test extraction from a single AI message returns empty (human-only filtering)."""
        messages = [AIMessage(content="The main side effects are...")]
        result = extract_retrieval_query(messages)
        # Human-only filtering: AI messages excluded
        assert result == ""

    def test_last_message_only_default(self):
        """Test that default behavior (max_history=1) extracts only last human message."""
        messages = [
            HumanMessage(content="Tell me about aripiprazole"),
            AIMessage(content="Aripiprazole is an antipsychotic medication"),
            HumanMessage(content="What about side effects?")
        ]
        result = extract_retrieval_query(messages)
        assert result == "What about side effects?"

    def test_multi_turn_conversation_with_history_human_only(self):
        """Test extraction with max_history=3 includes only human messages."""
        messages = [
            HumanMessage(content="Tell me about aripiprazole"),
            AIMessage(content="Aripiprazole is an antipsychotic medication"),
            HumanMessage(content="What about side effects?"),
            AIMessage(content="The main side effects are..."),
            HumanMessage(content="What about children?")
        ]
        result = extract_retrieval_query(messages, max_history=3)
        # Only last 3 human messages (AI excluded!)
        expected = (
            "Tell me about aripiprazole\n"
            "What about side effects?\n"
            "What about children?"
        )
        assert result == expected

    def test_max_history_larger_than_message_count(self):
        """Test that max_history larger than human message count uses all human messages."""
        messages = [
            HumanMessage(content="First question"),
            AIMessage(content="First answer"),
            HumanMessage(content="Second question")
        ]
        result = extract_retrieval_query(messages, max_history=10)
        # Only human messages, joined by newlines
        assert result == "First question\nSecond question"

    def test_max_history_zero_uses_all_human_messages(self):
        """Test that max_history=0 uses all available human messages."""
        messages = [
            HumanMessage(content="First"),
            AIMessage(content="Second"),
            HumanMessage(content="Third")
        ]
        result = extract_retrieval_query(messages, max_history=0)
        # Only human messages
        assert result == "First\nThird"

    def test_system_messages_filtered_by_default(self):
        """Test that system messages are excluded by default."""
        messages = [
            SystemMessage(content="You are a medical assistant"),
            HumanMessage(content="What are the side effects?")
        ]
        result = extract_retrieval_query(messages)
        assert result == "What are the side effects?"
        assert "You are a medical assistant" not in result

    def test_system_messages_included_when_requested(self):
        """Test that system messages can be included with include_system=True."""
        messages = [
            SystemMessage(content="System message"),
            HumanMessage(content="User message")
        ]
        result = extract_retrieval_query(messages, include_system=True)
        # Human-only filtering still applies (system is separate flag)
        assert result == "System message\nUser message"

    def test_only_system_messages_returns_empty(self):
        """Test that list with only system messages returns empty string (default)."""
        messages = [
            SystemMessage(content="System 1"),
            SystemMessage(content="System 2")
        ]
        result = extract_retrieval_query(messages)
        assert result == ""

    def test_only_system_messages_with_include_system(self):
        """Test system-only messages with include_system=True."""
        messages = [
            SystemMessage(content="System 1"),
            SystemMessage(content="System 2")
        ]
        result = extract_retrieval_query(messages, include_system=True)
        assert result == "System 1\nSystem 2"

    def test_only_ai_messages_returns_empty(self):
        """Test that list with only AI messages returns empty (human-only filtering)."""
        messages = [
            AIMessage(content="AI response 1"),
            AIMessage(content="AI response 2")
        ]
        result = extract_retrieval_query(messages)
        # Human-only filtering
        assert result == ""

    def test_messages_with_empty_content(self):
        """Test handling of messages with empty content."""
        messages = [
            HumanMessage(content=""),
            HumanMessage(content="Valid message"),
            HumanMessage(content="")
        ]
        result = extract_retrieval_query(messages, max_history=5)
        # Empty content should not contribute to the result
        assert result == "Valid message"

    def test_mixed_message_types_filters_human_only(self):
        """Test extraction from mixed message types filters to human only."""
        messages = [
            SystemMessage(content="System setup"),
            HumanMessage(content="User question 1"),
            AIMessage(content="AI response"),
            HumanMessage(content="User question 2"),
            AIMessage(content="Another AI response"),
            HumanMessage(content="Final question")
        ]
        result = extract_retrieval_query(messages, max_history=3)
        # Should exclude system and AI, include last 3 human messages
        expected = "User question 1\nUser question 2\nFinal question"
        assert result == expected

    def test_strategy_specific_defaults(self):
        """Test typical usage patterns for different retriever strategies."""
        messages = [
            HumanMessage(content="Tell me about medication A"),
            AIMessage(content="Medication A is..."),
            HumanMessage(content="What about side effects?")
        ]

        # Simple/Rerank strategy: last human message only
        simple_result = extract_retrieval_query(messages, max_history=1)
        assert simple_result == "What about side effects?"

        # Advanced strategy: last 5 human messages
        advanced_result = extract_retrieval_query(messages, max_history=5)
        # Only human messages
        assert advanced_result == "Tell me about medication A\nWhat about side effects?"


class TestFormatConversationContext:
    """Test format_conversation_context() function."""

    def test_empty_message_list(self):
        """Test that empty lists return empty string."""
        result = format_conversation_context([])
        assert result == ""

    def test_single_human_message_formatting(self):
        """Test formatting of a single human message."""
        messages = [HumanMessage(content="Hello")]
        result = format_conversation_context(messages)
        assert result == "User: Hello"

    def test_single_ai_message_formatting(self):
        """Test formatting of a single AI message."""
        messages = [AIMessage(content="Hi there")]
        result = format_conversation_context(messages)
        assert result == "Assistant: Hi there"

    def test_conversation_formatting(self):
        """Test formatting of multi-turn conversation."""
        messages = [
            HumanMessage(content="What are the side effects?"),
            AIMessage(content="The main side effects are..."),
            HumanMessage(content="Are they severe?")
        ]
        result = format_conversation_context(messages)
        expected = (
            "User: What are the side effects?\n"
            "Assistant: The main side effects are...\n"
            "User: Are they severe?"
        )
        assert result == expected

    def test_max_messages_limit(self):
        """Test that max_messages parameter limits output."""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Message 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Message 4")
        ]
        result = format_conversation_context(messages, max_messages=2)
        # Should only include last 2 messages
        assert "Message 1" not in result
        assert "Message 2" not in result
        assert "Message 3" in result
        assert "Message 4" in result

    def test_system_message_filtering(self):
        """Test that system messages are filtered by default."""
        messages = [
            SystemMessage(content="System setup"),
            HumanMessage(content="User query")
        ]
        result = format_conversation_context(messages)
        assert "System setup" not in result
        assert "User: User query" in result

    def test_system_message_included_when_requested(self):
        """Test system messages included with include_system=True."""
        messages = [
            SystemMessage(content="System message"),
            HumanMessage(content="User message")
        ]
        result = format_conversation_context(messages, include_system=True)
        assert "System: System message" in result
        assert "User: User message" in result

    def test_zero_max_messages_uses_all(self):
        """Test that max_messages=0 includes all messages."""
        messages = [
            HumanMessage(content="First"),
            AIMessage(content="Second"),
            HumanMessage(content="Third")
        ]
        result = format_conversation_context(messages, max_messages=0)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_exclude_last_n_parameter(self):
        """Test exclude_last_n parameter to avoid duplication with extracted query."""
        messages = [
            HumanMessage(content="Question 1"),
            AIMessage(content="Answer 1"),
            HumanMessage(content="Question 2"),
            AIMessage(content="Answer 2"),
            HumanMessage(content="Question 3")
        ]

        # Exclude last 1 message (the query we already extracted)
        result = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=1
        )

        # Should not include "Question 3" (last message)
        assert "Question 3" not in result
        assert "Question 2" in result
        assert "Answer 2" in result
        assert "Question 1" in result
        assert "Answer 1" in result

    def test_exclude_last_n_with_multiple_exclusions(self):
        """Test excluding multiple messages from the end."""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Message 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Message 4"),
            HumanMessage(content="Message 5")
        ]

        # Exclude last 2 messages
        result = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=2
        )

        # Should only include first 3 messages
        assert "Message 1" in result
        assert "Message 2" in result
        assert "Message 3" in result
        assert "Message 4" not in result
        assert "Message 5" not in result

    def test_exclude_last_n_equals_message_count_returns_empty(self):
        """Test that excluding all messages returns empty string."""
        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Message 2")
        ]

        result = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=2
        )

        assert result == ""

    def test_exclude_last_n_greater_than_message_count_returns_empty(self):
        """Test that excluding more than available returns empty string."""
        messages = [
            HumanMessage(content="Message 1")
        ]

        result = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=10
        )

        assert result == ""

    def test_exclude_last_n_with_system_filtering(self):
        """Test exclude_last_n works correctly after system message filtering."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Question 1"),
            AIMessage(content="Answer 1"),
            HumanMessage(content="Question 2")
        ]

        # Filter system first, then exclude last 1
        result = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=1
        )

        # System filtered out, then last message (Question 2) excluded
        assert "System" not in result
        assert "Question 1" in result
        assert "Answer 1" in result
        assert "Question 2" not in result

    def test_typical_usage_pattern_for_query_expansion(self):
        """Test typical usage in AdvancedRetriever query expansion."""
        messages = [
            HumanMessage(content="Tell me about aripiprazole"),
            AIMessage(content="It's an antipsychotic medication"),
            HumanMessage(content="What about side effects?")
        ]

        # Extract last message as query
        query = extract_retrieval_query(messages, max_history=1)

        # Format context excluding the extracted query
        context = format_conversation_context(
            messages,
            max_messages=5,
            exclude_last_n=1
        )

        assert query == "What about side effects?"
        assert "What about side effects?" not in context  # Excluded!
        assert "Tell me about aripiprazole" in context
        assert "It's an antipsychotic medication" in context


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_none_content_in_messages(self):
        """Test handling of messages with None content."""
        # This shouldn't happen in practice, but test defensively
        messages = [HumanMessage(content="Valid")]
        result = extract_retrieval_query(messages)
        assert result == "Valid"

    def test_whitespace_only_content(self):
        """Test handling of whitespace-only content."""
        messages = [
            HumanMessage(content="   "),
            HumanMessage(content="Valid message")
        ]
        result = extract_retrieval_query(messages, max_history=2)
        # Whitespace should be preserved (might be intentional)
        assert "Valid message" in result

    def test_very_long_conversation(self):
        """Test performance with long conversation history."""
        messages = [HumanMessage(content=f"Message {i}") for i in range(100)]
        result = extract_retrieval_query(messages, max_history=5)
        # Should only include last 5
        assert "Message 99" in result
        assert "Message 95" in result
        assert "Message 94" not in result

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        messages = [
            HumanMessage(content="¿Qué son los efectos secundarios?"),
            AIMessage(content="日本語のテスト"),
            HumanMessage(content="Emoji test 🏥💊")
        ]
        result = extract_retrieval_query(messages, max_history=3)
        # Only human messages
        assert "¿Qué son los efectos secundarios?" in result
        assert "日本語のテスト" not in result  # AI message excluded
        assert "Emoji test 🏥💊" in result

    def test_newline_join_behavior(self):
        """Test that messages are joined with newlines, not spaces."""
        messages = [
            HumanMessage(content="First question"),
            HumanMessage(content="Second question")
        ]
        result = extract_retrieval_query(messages, max_history=2)
        # Should be newline-joined
        assert result == "First question\nSecond question"
        assert "First question Second question" != result
