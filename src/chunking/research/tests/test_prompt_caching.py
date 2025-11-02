"""
Test prompt caching implementation for V3 experimental extractors.

This test verifies that:
1. Cache metrics are being collected and returned
2. First section shows cache write status
3. Subsequent sections show cache hit status (when using real LLM)
4. All expected cache fields are present in the response
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.chunking.chunk_extractor_v3_experimental import ChunkExtractorV3A, ChunkExtractorV3B
from src.chunking.models import Document, Structure, SectionV2


def create_mock_structure(num_sections=2):
    """Create a mock structure with specified number of sections."""
    sections = [
        SectionV2(
            title="Section 1",
            level=1,
            parent_section="ROOT",
            summary="First section summary",
            start_words="Section 1 starts here",
            end_words="Section 1 ends here"
        ),
        SectionV2(
            title="Section 2",
            level=1,
            parent_section="ROOT",
            summary="Second section summary",
            start_words="Section 2 starts here",
            end_words="Section 2 ends here"
        ),
        SectionV2(
            title="Section 3",
            level=1,
            parent_section="ROOT",
            summary="Third section summary",
            start_words="Section 3 starts here",
            end_words="Section 3 ends here"
        )
    ]

    return Structure(
        document_id="test_doc",
        chapter_title="Test Chapter",
        sections=sections[:num_sections],
        analysis_model="test-model",
        metadata={}
    )


def create_mock_document():
    """Create a mock document with test content."""
    return Document(
        document_id="test_doc",
        file_path="/tmp/test_doc.txt",
        file_hash="test_hash_123",
        content="""
        Section 1 starts here
        This is the content of section 1.
        It has multiple lines of text.
        Section 1 ends here

        Section 2 starts here
        This is the content of section 2.
        It also has multiple lines of text.
        Section 2 ends here

        Section 3 starts here
        This is the content of section 3.
        Final section with content.
        Section 3 ends here
        """
    )


def create_mock_llm_response(section_num: int, cache_status: str = "write", operation: str = "extraction"):
    """Create a mock LLM response with cache metrics."""
    cache_read_tokens = 5000 if cache_status == "hit" else 0
    cache_write_tokens = 5000 if cache_status == "write" else 0

    # Generate appropriate content based on operation type
    if operation == "extraction":
        content = f"Extracted text for section {section_num}"
    else:  # prefix
        content = f"This chunk is from the Test Chapter, Section {section_num}, discussing test content for section {section_num}."

    return {
        "choices": [{
            "message": {
                "content": content
            }
        }],
        "usage": {
            "total_tokens": 6000,
            "cache_read_input_tokens": cache_read_tokens,
            "cache_creation_input_tokens": cache_write_tokens
        },
        "cache_discount": 0.45 if cache_status == "hit" else -0.05
    }


def create_mock_llm_response_v3b(section_num: int, cache_status: str = "write"):
    """Create a mock LLM response for V3B (merged output)."""
    cache_read_tokens = 5000 if cache_status == "hit" else 0
    cache_write_tokens = 5000 if cache_status == "write" else 0

    return {
        "choices": [{
            "message": {
                "content": f"""[CHUNK_TEXT]
Extracted text for section {section_num}.
This is the complete content.
[/CHUNK_TEXT]

[CONTEXTUAL_PREFIX]This chunk is from the Test Chapter, Section {section_num}, discussing test content.[/CONTEXTUAL_PREFIX]"""
            }
        }],
        "usage": {
            "total_tokens": 6000,
            "cache_read_input_tokens": cache_read_tokens,
            "cache_creation_input_tokens": cache_write_tokens
        },
        "cache_discount": 0.45 if cache_status == "hit" else -0.05
    }


class TestV3ACacheMetrics:
    """Test cache metrics collection for V3A extractor."""

    def test_cache_metrics_structure(self):
        """Verify cache metrics are present in response structure."""
        # Setup mocks
        llm_client = Mock()
        token_counter = Mock()
        token_counter.count_tokens.return_value = 500
        metadata_validator = Mock()

        # Mock LLM responses - first section write, subsequent sections hit
        llm_client.chat_completion.side_effect = [
            create_mock_llm_response(1, "write", "extraction"),  # Section 1 extraction
            create_mock_llm_response(1, "write", "prefix"),      # Section 1 prefix
            create_mock_llm_response(2, "hit", "extraction"),    # Section 2 extraction
            create_mock_llm_response(2, "hit", "prefix"),        # Section 2 prefix
        ]

        # Create extractor
        extractor = ChunkExtractorV3A(
            llm_client=llm_client,
            token_counter=token_counter,
            metadata_validator=metadata_validator,
            model="test-model",
            cache_store=None
        )

        # Create test data - only 2 sections for this test
        document = create_mock_document()
        structure = create_mock_structure(num_sections=2)

        # Extract chunks
        result = extractor.extract_chunks(document, structure)

        # Verify cache metrics are present
        assert "llm_responses" in result
        llm_responses = result["llm_responses"]

        # Check Section 1 (cache write)
        assert "Section 1" in llm_responses
        section1 = llm_responses["Section 1"]

        assert "extraction" in section1
        assert "cache_status" in section1["extraction"]
        assert "cache_discount" in section1["extraction"]
        assert "cache_read_tokens" in section1["extraction"]
        assert "cache_write_tokens" in section1["extraction"]
        assert section1["extraction"]["cache_status"] == "write"
        assert section1["extraction"]["cache_write_tokens"] == 5000

        assert "prefix" in section1
        assert "cache_status" in section1["prefix"]
        assert section1["prefix"]["cache_status"] == "write"

        # Check Section 2 (cache hit)
        assert "Section 2" in llm_responses
        section2 = llm_responses["Section 2"]

        assert section2["extraction"]["cache_status"] == "hit"
        assert section2["extraction"]["cache_read_tokens"] == 5000
        assert section2["extraction"]["cache_discount"] == 0.45

        assert section2["prefix"]["cache_status"] == "hit"
        assert section2["prefix"]["cache_read_tokens"] == 5000


class TestV3BCacheMetrics:
    """Test cache metrics collection for V3B extractor."""

    def test_cache_metrics_structure(self):
        """Verify cache metrics are present in response structure."""
        # Setup mocks
        llm_client = Mock()
        token_counter = Mock()
        token_counter.count_tokens.return_value = 500
        metadata_validator = Mock()

        # Mock LLM responses - first section write, subsequent sections hit
        llm_client.chat_completion.side_effect = [
            create_mock_llm_response_v3b(1, "write"),  # Section 1 merged
            create_mock_llm_response_v3b(2, "hit"),    # Section 2 merged
        ]

        # Create extractor
        extractor = ChunkExtractorV3B(
            llm_client=llm_client,
            token_counter=token_counter,
            metadata_validator=metadata_validator,
            model="test-model",
            cache_store=None
        )

        # Create test data - only 2 sections for this test
        document = create_mock_document()
        structure = create_mock_structure(num_sections=2)

        # Extract chunks
        result = extractor.extract_chunks(document, structure)

        # Verify cache metrics are present
        assert "llm_responses" in result
        llm_responses = result["llm_responses"]

        # Check Section 1 (cache write)
        assert "Section 1" in llm_responses
        section1 = llm_responses["Section 1"]

        assert "merged" in section1
        assert "cache_status" in section1["merged"]
        assert "cache_discount" in section1["merged"]
        assert "cache_read_tokens" in section1["merged"]
        assert "cache_write_tokens" in section1["merged"]
        assert section1["merged"]["cache_status"] == "write"
        assert section1["merged"]["cache_write_tokens"] == 5000

        # Check Section 2 (cache hit)
        assert "Section 2" in llm_responses
        section2 = llm_responses["Section 2"]

        assert section2["merged"]["cache_status"] == "hit"
        assert section2["merged"]["cache_read_tokens"] == 5000
        assert section2["merged"]["cache_discount"] == 0.45


class TestCacheMessageFormat:
    """Test that cached messages are built correctly."""

    def test_build_cached_message_format(self):
        """Verify multipart message structure with cache_control."""
        # Setup
        llm_client = Mock()
        token_counter = Mock()
        metadata_validator = Mock()

        extractor = ChunkExtractorV3A(
            llm_client=llm_client,
            token_counter=token_counter,
            metadata_validator=metadata_validator,
            model="test-model"
        )

        # Build cached message
        document_text = "Test document content"
        instructions = "Test instructions"
        messages = extractor._build_cached_message(document_text, instructions)

        # Verify structure
        assert len(messages) == 1
        message = messages[0]

        assert message["role"] == "user"
        assert isinstance(message["content"], list)
        assert len(message["content"]) == 2

        # Verify first part (document with cache_control)
        part1 = message["content"][0]
        assert part1["type"] == "text"
        assert "DOCUMENT TEXT:" in part1["text"]
        assert document_text in part1["text"]
        assert "cache_control" in part1
        assert part1["cache_control"] == {"type": "ephemeral"}

        # Verify second part (instructions without cache_control)
        part2 = message["content"][1]
        assert part2["type"] == "text"
        assert instructions in part2["text"]
        assert "cache_control" not in part2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
