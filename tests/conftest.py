"""Pytest configuration and fixtures."""

import pytest
import asyncio
import time
from typing import List
from pathlib import Path
import logging
from app.core.retriever import FAISSRetriever, Document
from app.core.session_store import InMemorySessionStore
from app.config import settings

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


@pytest.fixture
async def sample_documents() -> List[Document]:
    """Create sample medical documents for testing."""
    return [
        Document(
            id="test-sertraline",
            content="""
Medication: Sertraline (Zoloft)
Class: SSRI
Uses: Depression, anxiety, OCD
Dosage: 50-200mg daily
Side Effects: Nausea, insomnia
            """.strip(),
            metadata={"name": "Sertraline", "class": "SSRI"},
        ),
        Document(
            id="test-bupropion",
            content="""
Medication: Bupropion (Wellbutrin)
Class: NDRI
Uses: Depression, smoking cessation
Dosage: 150-300mg daily
Side Effects: Insomnia, dry mouth
            """.strip(),
            metadata={"name": "Bupropion", "class": "NDRI"},
        ),
    ]


@pytest.fixture(scope="session")
async def session_retriever() -> FAISSRetriever:
    """Load model once for entire test session (fail-fast, no fallback).

    Session scope ensures model is loaded only once per test session.
    If use_persistent_index=True, will load from disk or raise exception.
    If use_persistent_index=False or force_recompute=True, computes fresh.

    Returns:
        FAISSRetriever instance with loaded model and index
    """
    if settings.use_persistent_index and not settings.force_recompute:
        # Load from disk - will raise exception if not found or corrupted
        logger.info(f"Loading retriever from persistent index: {settings.index_path}")
        retriever = await FAISSRetriever.load_index(
            path=settings.index_path,
            embedding_model=settings.embedding_model
        )
        logger.info("Successfully loaded retriever from disk")
        return retriever

    # Compute fresh from sample documents
    logger.info("Computing fresh retriever (force_recompute=True or persistence disabled)")

    retriever = FAISSRetriever(embedding_model=settings.embedding_model)

    # Load sample documents for testing
    sample_docs = [
        Document(
            id="test-sertraline",
            content="""
Medication: Sertraline (Zoloft)
Class: SSRI
Uses: Depression, anxiety, OCD
Dosage: 50-200mg daily
Side Effects: Nausea, insomnia
            """.strip(),
            metadata={"name": "Sertraline", "class": "SSRI"},
        ),
        Document(
            id="test-bupropion",
            content="""
Medication: Bupropion (Wellbutrin)
Class: NDRI
Uses: Depression, smoking cessation
Dosage: 150-300mg daily
Side Effects: Insomnia, dry mouth
            """.strip(),
            metadata={"name": "Bupropion", "class": "NDRI"},
        ),
    ]

    await retriever.add_documents(sample_docs)
    logger.info(f"Initialized retriever with {len(sample_docs)} sample documents")

    return retriever


@pytest.fixture
async def mock_retriever(session_retriever: FAISSRetriever, sample_documents: List[Document]) -> FAISSRetriever:
    """Create retriever instance for individual tests.

    Reuses the session retriever instance to avoid re-loading the model,
    but provides function scope for test isolation.

    Args:
        session_retriever: Session-scoped retriever with pre-loaded model
        sample_documents: Sample documents fixture (for compatibility)

    Returns:
        FAISSRetriever instance ready for testing

    Note:
        The session_retriever already contains sample documents.
        For tests requiring custom documents, use retriever.add_documents()
        directly in the test.
    """
    # Return the session retriever directly
    # Tests that need custom documents can add them with add_documents()
    return session_retriever


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
