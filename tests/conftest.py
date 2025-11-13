"""Pytest configuration and fixtures."""

# CRITICAL: Set environment variables BEFORE any app imports
import os
os.environ["TESTING"] = "true"
# Set dummy API token to allow settings module to load
# Individual tests will override this with their own token
os.environ["API_BEARER_TOKEN"] = "0" * 64  # Valid format, will be overridden by test fixtures

import pytest
import asyncio
import time
from typing import List
from pathlib import Path
import logging
# Removed broken imports: Document, FAISSRetriever, HybridRetriever, CrossEncoderReranker
# These are not needed for auth or streaming tests
from app.core.session_store import InMemorySessionStore
# Do NOT import settings here - let each test control when settings loads
# import numpy as np  # Not needed for streaming tests
# from scipy.sparse import csr_matrix  # Not needed for streaming tests

logger = logging.getLogger(__name__)


# Pytest hook to show test duration after each test completes
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add test duration to terminal output after each test."""
    outcome = yield
    report = outcome.get_result()

    # Only show timing for test call phase (not setup/teardown)
    if report.when == "call":
        duration = getattr(report, "duration", 0)
        if duration > 0:
            # Add duration to the test output
            report.sections.append(("Test Duration", f"{duration:.2f}s"))

    return report


@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add summary of all test durations at the end."""
    if hasattr(terminalreporter, 'stats'):
        passed = terminalreporter.stats.get('passed', [])

        if passed:
            terminalreporter.write_sep("=", "Individual Test Durations")

            # Collect and sort tests by duration
            test_durations = []
            for report in passed:
                if hasattr(report, 'duration') and report.when == 'call':
                    test_durations.append((report.nodeid, report.duration))

            # Sort by duration (slowest first)
            test_durations.sort(key=lambda x: x[1], reverse=True)

            # Display all test durations
            for nodeid, duration in test_durations:
                terminalreporter.write_line(f"{duration:>7.2f}s {nodeid}")

            # Calculate total
            total_duration = sum(d for _, d in test_durations)
            terminalreporter.write_line(f"\n{'Total test time:':<50} {total_duration:.2f}s")


@pytest.fixture(scope="session")
def event_loop():
    """Create session-scoped event loop for async tests.

    This session-scoped loop is required for session-scoped async fixtures
    like test_checkpointer to work properly across multiple tests.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set TESTING=true environment variable for all tests.

    This enables FakeChatModel in create_llm() for:
    - Deterministic responses (no randomness)
    - 50-100x faster execution (no API calls)
    - Zero API costs
    - Offline testing capability

    The fake LLM eliminates the need for LLM response caching entirely.
    """
    import os

    original = os.environ.get("TESTING")
    os.environ["TESTING"] = "true"
    logger.info("✅ Test environment enabled: FakeChatModel active (no API calls)")

    yield

    # Restore original value
    if original is not None:
        os.environ["TESTING"] = original
    else:
        os.environ.pop("TESTING", None)


# DISABLED: Document class moved/deleted, not needed for auth or streaming tests
# @pytest.fixture
# async def sample_documents() -> List[Document]:
#     """Create sample medical documents for testing."""
#     pass


# DISABLED: FAISSRetriever no longer exists - replaced by PostgreSQLRetriever
# This fixture is not needed for streaming tests which use the real app via lifespan
# @pytest.fixture(scope="session")
# async def session_retriever() -> FAISSRetriever:
#     """Create session-scoped retriever for tests."""
#     pass


# DISABLED: FAISSRetriever no longer exists - replaced by PostgreSQLRetriever
# @pytest.fixture(scope="session")
# async def production_retriever() -> FAISSRetriever:
#     """Load production retriever from pre-computed embeddings."""
#     pass


# DISABLED: Depends on session_retriever which uses FAISSRetriever
# @pytest.fixture
# async def mock_retriever(session_retriever, sample_documents: List[Document]):
#     """Create retriever instance for individual tests."""
#     pass


@pytest.fixture
def mock_session_store() -> InMemorySessionStore:
    """Create in-memory session store for testing."""
    return InMemorySessionStore(ttl_seconds=3600)


# clear_checkpoint_db fixture removed - no longer needed with MemorySaver
# MemorySaver uses in-memory storage only, no disk persistence required


@pytest.fixture(scope="session")
def session_checkpointer():
    """Provide session-scoped MemorySaver for all tests.

    Session scope is safe because:
    - Tests use unique thread_ids for isolation (e.g., "test-1", "api-session-123")
    - MemorySaver stores checkpoints per thread_id
    - No cross-test contamination possible
    - Instant initialization (~0ms)

    This replaces AsyncSqliteSaver which took ~18s per initialization.
    """
    from langgraph.checkpoint.memory import MemorySaver

    logger.info("✅ Creating session-scoped MemorySaver checkpointer")
    return MemorySaver()


@pytest.fixture
def test_checkpointer(session_checkpointer):
    """Provide checkpointer for tests (delegates to session_checkpointer).

    Function-scoped for backward compatibility, but internally uses
    session-scoped MemorySaver for performance.
    """
    return session_checkpointer


# DISABLED: Document class moved/deleted, not needed for auth or streaming tests
# @pytest.fixture(scope="session")
# async def parenting_sample_documents() -> List[Document]:
#     """Create sample parenting documents for testing."""
#     pass


# DISABLED: Depends on FAISSRetriever and HybridRetriever
# @pytest.fixture(scope="session")
# async def session_parenting_retriever(parenting_sample_documents: List[Document]) -> HybridRetriever:
#     """Create session-scoped parenting retriever for tests."""
#     pass


# DISABLED: Depends on session_parenting_retriever
# @pytest.fixture
# async def parenting_retriever(session_parenting_retriever: HybridRetriever) -> HybridRetriever:
#     pass


# DISABLED: CrossEncoderReranker exists but not used in streaming tests
# @pytest.fixture(scope="session")
# def session_parenting_reranker() -> CrossEncoderReranker:
#     pass


# DISABLED: Depends on session_parenting_reranker
# @pytest.fixture
# def parenting_reranker(session_parenting_reranker: CrossEncoderReranker) -> CrossEncoderReranker:
#     pass
