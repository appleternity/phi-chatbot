"""Unit tests for text utility functions."""

import pytest

from app.utils.text_utils import normalize_llm_output


class TestNormalizeLLMOutput:
    """Test cases for normalize_llm_output function."""

    def test_basic_normalization(self):
        """Test basic whitespace stripping and lowercasing."""
        assert normalize_llm_output("rag_agent") == "rag_agent"
        assert normalize_llm_output("  rag_agent  ") == "rag_agent"
        assert normalize_llm_output("RAG_AGENT") == "rag_agent"
        assert normalize_llm_output("Rag_Agent") == "rag_agent"

    def test_double_quotes_removal(self):
        """Test removal of surrounding double quotes."""
        assert normalize_llm_output('"rag_agent"') == "rag_agent"
        assert normalize_llm_output('  "rag_agent"  ') == "rag_agent"
        assert normalize_llm_output('"RAG_AGENT"') == "rag_agent"
        assert normalize_llm_output('"emotional_support"') == "emotional_support"

    def test_single_quotes_removal(self):
        """Test removal of surrounding single quotes."""
        assert normalize_llm_output("'rag_agent'") == "rag_agent"
        assert normalize_llm_output("  'rag_agent'  ") == "rag_agent"
        assert normalize_llm_output("'EMOTIONAL_SUPPORT'") == "emotional_support"

    def test_multiple_quote_layers(self):
        """Test removal of multiple layers of quotes."""
        assert normalize_llm_output("\"'rag_agent'\"") == "rag_agent"
        assert normalize_llm_output("'\"rag_agent\"'") == "rag_agent"
        assert normalize_llm_output("'''rag_agent'''") == "rag_agent"

    def test_retrieve_respond_classification(self):
        """Test normalization for RAG intent classification."""
        assert normalize_llm_output("retrieve") == "retrieve"
        assert normalize_llm_output("RETRIEVE") == "retrieve"
        assert normalize_llm_output('"retrieve"') == "retrieve"
        assert normalize_llm_output("  'RETRIEVE'  ") == "retrieve"

        assert normalize_llm_output("respond") == "respond"
        assert normalize_llm_output("RESPOND") == "respond"
        assert normalize_llm_output('"respond"') == "respond"
        assert normalize_llm_output("  'RESPOND'  ") == "respond"

    def test_supervisor_agent_names(self):
        """Test normalization for supervisor classification."""
        # rag_agent variations
        assert normalize_llm_output("rag_agent") == "rag_agent"
        assert normalize_llm_output("RAG_AGENT") == "rag_agent"
        assert normalize_llm_output('"rag_agent"') == "rag_agent"
        assert normalize_llm_output("'RAG_AGENT'") == "rag_agent"

        # emotional_support variations
        assert normalize_llm_output("emotional_support") == "emotional_support"
        assert normalize_llm_output("EMOTIONAL_SUPPORT") == "emotional_support"
        assert normalize_llm_output('"emotional_support"') == "emotional_support"
        assert normalize_llm_output("'EMOTIONAL_SUPPORT'") == "emotional_support"

    def test_empty_string(self):
        """Test handling of empty strings."""
        assert normalize_llm_output("") == ""
        assert normalize_llm_output("  ") == ""
        assert normalize_llm_output('""') == ""
        assert normalize_llm_output("''") == ""

    def test_quotes_only(self):
        """Test handling of strings with only quotes."""
        assert normalize_llm_output('"') == ""
        assert normalize_llm_output("'") == ""
        assert normalize_llm_output('""') == ""
        assert normalize_llm_output("''") == ""

    def test_strips_any_trailing_quotes(self):
        """Test that any trailing quotes/whitespace are stripped.

        The regex pattern strips all leading and trailing quotes/whitespace,
        not just matching pairs. This is fine for our use case since LLMs
        won't return malformed strings like 'rag_'agent'' in classification tasks.
        """
        # Regex strips trailing quotes even if not symmetrical
        assert normalize_llm_output("rag_agent'") == "rag_agent"
        assert normalize_llm_output("'rag_agent") == "rag_agent"
        assert normalize_llm_output('"rag_agent"') == "rag_agent"

    def test_mixed_whitespace_and_quotes(self):
        """Test complex combinations of whitespace and quotes."""
        assert normalize_llm_output('  "  rag_agent  "  ') == "rag_agent"
        assert normalize_llm_output("  '  RETRIEVE  '  ") == "retrieve"
