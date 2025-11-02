"""
Pytest configuration and fixtures for chunking tests.

This module provides common test fixtures for mock providers and test documents.
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from src.chunking.models import Document
from src.chunking.llm_provider import MockLLMProvider
from src.chunking.research.cache_store import FileCacheStore
from tests.chunking.fixtures.llm_responses import (
    MOCK_STRUCTURE_RESPONSE,
    MOCK_BOUNDARIES_RESPONSE,
    MOCK_METADATA_RESPONSE,
    MOCK_PREFIX_RESPONSE,
    SAMPLE_DOCUMENT_TEXT,
    MOCK_RESPONSES_BY_MODEL
)


@pytest.fixture
def sample_document_text() -> str:
    """Sample document text for testing"""
    return SAMPLE_DOCUMENT_TEXT


@pytest.fixture
def sample_document(tmp_path: Path) -> Document:
    """
    Create a sample document for testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Document instance
    """
    # Create temporary file
    doc_file = tmp_path / "sample_chapter.txt"
    doc_file.write_text(SAMPLE_DOCUMENT_TEXT)

    # Return Document instance
    return Document.from_file(doc_file)


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """
    Create mock LLM provider with predefined responses.

    Returns:
        MockLLMProvider instance with mock responses
    """
    return MockLLMProvider(responses=MOCK_RESPONSES_BY_MODEL)


@pytest.fixture
def mock_cache_store(tmp_path: Path) -> FileCacheStore:
    """
    Create temporary file cache store.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        FileCacheStore instance using temporary directory
    """
    cache_dir = tmp_path / ".cache"
    return FileCacheStore(cache_dir=cache_dir)


@pytest.fixture
def mock_structure_response() -> Dict[str, Any]:
    """Mock structure analysis response"""
    return MOCK_STRUCTURE_RESPONSE


@pytest.fixture
def mock_boundaries_response() -> Dict[str, Any]:
    """Mock boundary detection response"""
    return MOCK_BOUNDARIES_RESPONSE


@pytest.fixture
def mock_metadata_response() -> Dict[str, Any]:
    """Mock metadata generation response"""
    return MOCK_METADATA_RESPONSE


@pytest.fixture
def mock_prefix_response() -> Dict[str, Any]:
    """Mock contextual prefix response"""
    return MOCK_PREFIX_RESPONSE
