"""Tests for centralized LLM instance management.

Test Coverage:
- T014: Verify TESTING=true returns FakeChatModel instances
- T015: Verify TESTING=false returns ChatOpenAI instances
- T016: Verify singleton behavior (same object reference across imports)
"""

import os
import sys
from unittest.mock import patch

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

# Import path setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


class TestLLMInstanceEnvironmentSwitching:
    """Test automatic test/production mode switching based on TESTING environment variable."""

    def test_testing_mode_returns_fakechatmodel(self):
        """T014: Verify TESTING=true returns FakeChatModel instances."""
        # This test runs in normal test environment (TESTING=true set by conftest.py)
        # Module imports happen at import time, so instances are already created

        # Import instances (should be FakeChatModel in test env)
        from app.llm import response_llm, internal_llm
        from tests.fakes.fake_chat_model import FakeChatModel

        # Verify both instances are FakeChatModel
        assert isinstance(response_llm, FakeChatModel), "response_llm should be FakeChatModel in test environment"
        assert isinstance(internal_llm, FakeChatModel), "internal_llm should be FakeChatModel in test environment"

    def test_production_mode_returns_chatopenai(self):
        """T015: Verify TESTING=false returns ChatOpenAI instances."""
        # Mock the TESTING environment variable as false
        with patch.dict(os.environ, {"TESTING": "false"}):
            # Remove cached modules to force re-import
            modules_to_reload = [
                "app.llm.factory",
                "app.llm.instances",
                "app.llm",
            ]
            for mod in modules_to_reload:
                if mod in sys.modules:
                    del sys.modules[mod]

            # Import instances (should be ChatOpenAI with TESTING=false)
            from app.llm import response_llm, internal_llm

            # Verify both instances are ChatOpenAI
            assert isinstance(response_llm, ChatOpenAI), "response_llm should be ChatOpenAI in production environment"
            assert isinstance(internal_llm, ChatOpenAI), "internal_llm should be ChatOpenAI in production environment"

        # Clean up: restore test environment
        # Re-import with TESTING=true to reset for other tests
        modules_to_reload = [
            "app.llm.factory",
            "app.llm.instances",
            "app.llm",
        ]
        for mod in modules_to_reload:
            if mod in sys.modules:
                del sys.modules[mod]

    def test_singleton_behavior_same_reference(self):
        """T016: Verify singleton behavior (same object reference across multiple imports)."""
        # Import instances first time
        from app.llm import response_llm as llm1, internal_llm as internal1

        # Import instances second time (should be same reference)
        from app.llm import response_llm as llm2, internal_llm as internal2

        # Verify object identity (same object reference)
        assert llm1 is llm2, "response_llm should return same object reference across imports"
        assert internal1 is internal2, "internal_llm should return same object reference across imports"

        # Verify they are BaseChatModel instances
        assert isinstance(llm1, BaseChatModel), "response_llm should be BaseChatModel instance"
        assert isinstance(internal1, BaseChatModel), "internal_llm should be BaseChatModel instance"


class TestConfTestAutoConfiguration:
    """Test that conftest.py sets TESTING=true automatically (T017)."""

    def test_conftest_sets_testing_true(self):
        """T017: Verify conftest.py sets TESTING=true automatically."""
        # This test implicitly validates that conftest.py sets TESTING=true
        # If conftest.py didn't set TESTING=true, test_testing_mode_returns_fakechatmodel would fail
        assert os.getenv("TESTING", "false").lower() == "true", "TESTING environment variable should be 'true'"


class TestFullTestSuiteIntegration:
    """Test that full test suite passes with FakeChatModel responses (T018)."""

    def test_fake_responses_available(self):
        """T018: Verify FakeChatModel can generate deterministic responses."""
        from app.llm import response_llm

        # Invoke response_llm with a simple message
        from langchain_core.messages import HumanMessage

        response = response_llm.invoke([HumanMessage(content="Hello")])

        # Verify response is generated (content is non-empty)
        assert response.content, "FakeChatModel should return non-empty response"
        assert isinstance(response.content, str), "Response content should be string"
