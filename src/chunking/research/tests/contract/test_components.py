"""
Contract tests for chunking system components.

Tests the public interfaces (contracts) of StructureAnalyzer, BoundaryDetector,
and DocumentSegmenter to ensure they adhere to expected behavior patterns.
"""

import pytest
from pathlib import Path

from src.chunking.models import (
    Document,
    Structure,
    Section,
    SegmentBoundary,
    BoundaryType,
    StructureAnalysisError,
    BoundaryDetectionError,
    SegmentationError,
)
from src.chunking.structure_analyzer import StructureAnalyzer
from src.chunking.boundary_detector import BoundaryDetector
from src.chunking.document_segmenter import DocumentSegmenter


# ============================================================================
# StructureAnalyzer Contract Tests
# ============================================================================


class TestStructureAnalyzerContract:
    """Test StructureAnalyzer component contract"""

    def test_analyze_with_valid_document(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test StructureAnalyzer.analyze() with valid document"""
        # Arrange
        analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # Act
        structure = analyzer.analyze(sample_document)

        # Assert
        assert isinstance(structure, Structure)
        assert structure.document_id == sample_document.document_id
        assert len(structure.sections) > 0
        assert structure.chapter_title is not None
        assert structure.analysis_model == "openai/gpt-4o"

        # Verify sections are properly ordered
        for i in range(len(structure.sections) - 1):
            assert structure.sections[i].start_char <= structure.sections[i+1].start_char

    def test_analyze_cache_hit_behavior(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test StructureAnalyzer caching behavior"""
        # Arrange
        analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # First call should populate cache
        first_result = analyzer.analyze(sample_document)

        # Act - Second call should use cache
        second_result = analyzer.analyze(sample_document)

        # Assert - Results should be consistent
        assert first_result.document_id == second_result.document_id
        assert first_result.chapter_title == second_result.chapter_title
        assert len(first_result.sections) == len(second_result.sections)

        # Second result should indicate cache hit
        assert second_result.metadata.get("cache_hit") is True

    def test_analyze_with_empty_document(
        self,
        mock_llm_provider,
        mock_cache_store,
        tmp_path
    ):
        """Test StructureAnalyzer error handling with empty document"""
        # Arrange
        analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # Create empty document file
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        # Act & Assert
        with pytest.raises(ValueError, match="content cannot be empty"):
            Document.from_file(empty_file)

    def test_analyze_with_malformed_llm_response(
        self,
        mock_cache_store,
        sample_document
    ):
        """Test StructureAnalyzer handles malformed LLM responses"""
        # Arrange - Create mock LLM that returns malformed response
        from src.chunking.llm_provider import MockLLMProvider

        bad_response = {
            "openai/gpt-4o": {
                "id": "test",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "```tsv\nMalformed output\n```"  # Wrong format
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            }
        }

        bad_llm_provider = MockLLMProvider(responses=bad_response)

        analyzer = StructureAnalyzer(
            llm_client=bad_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # Act & Assert
        with pytest.raises(StructureAnalysisError, match="markdown code block"):
            analyzer.analyze(sample_document)

    def test_analyze_sections_non_overlapping(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test StructureAnalyzer ensures sections don't overlap"""
        # Arrange
        analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # Act
        structure = analyzer.analyze(sample_document)

        # Assert - Check no overlaps at same level
        sections_by_level = {}
        for section in structure.sections:
            if section.level not in sections_by_level:
                sections_by_level[section.level] = []
            sections_by_level[section.level].append(section)

        for level, sections in sections_by_level.items():
            sorted_sections = sorted(sections, key=lambda s: s.start_char)
            for i in range(len(sorted_sections) - 1):
                current = sorted_sections[i]
                next_section = sorted_sections[i + 1]
                # Sections at same level should not overlap
                assert current.end_char <= next_section.start_char, \
                    f"Sections at level {level} overlap: {current.title} and {next_section.title}"


# ============================================================================
# BoundaryDetector Contract Tests
# ============================================================================


class TestBoundaryDetectorContract:
    """Test BoundaryDetector component contract"""

    def test_detect_boundaries_with_valid_inputs(
        self,
        mock_llm_provider,
        sample_document,
        mock_structure_response
    ):
        """Test BoundaryDetector.detect_boundaries() with valid inputs"""
        # Arrange
        from src.chunking.models import TokenCounter

        detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        # Create a simple structure
        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=100,
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        # Act
        boundaries = detector.detect_boundaries(
            document=sample_document,
            structure=structure,
            max_chunk_tokens=1000
        )

        # Assert
        assert len(boundaries) >= 2  # At least DOCUMENT_START and DOCUMENT_END
        assert boundaries[0].boundary_type == BoundaryType.DOCUMENT_START
        assert boundaries[0].position == 0
        assert boundaries[-1].boundary_type == BoundaryType.DOCUMENT_END
        assert boundaries[-1].position == len(sample_document.content)

    def test_detect_boundaries_ordering(
        self,
        mock_llm_provider,
        sample_document,
        mock_structure_response
    ):
        """Test BoundaryDetector ensures boundaries are ordered"""
        # Arrange
        from src.chunking.models import TokenCounter

        detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=len(sample_document.content),
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        # Act
        boundaries = detector.detect_boundaries(
            document=sample_document,
            structure=structure,
            max_chunk_tokens=1000
        )

        # Assert - Boundaries must be in ascending order
        for i in range(len(boundaries) - 1):
            assert boundaries[i].position < boundaries[i + 1].position, \
                f"Boundary {i} at position {boundaries[i].position} " \
                f"is not before boundary {i+1} at position {boundaries[i + 1].position}"

    def test_detect_boundaries_completeness(
        self,
        mock_llm_provider,
        sample_document,
        mock_structure_response
    ):
        """Test BoundaryDetector provides complete coverage"""
        # Arrange
        from src.chunking.models import TokenCounter

        detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=len(sample_document.content),
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        # Act
        boundaries = detector.detect_boundaries(
            document=sample_document,
            structure=structure,
            max_chunk_tokens=1000
        )

        # Assert - Boundaries should cover entire document
        assert boundaries[0].position == 0
        assert boundaries[-1].position == len(sample_document.content)

        # Check no gaps between consecutive boundaries
        for i in range(len(boundaries) - 1):
            # Note: Boundaries can have the same position, but shouldn't skip positions
            assert boundaries[i].position <= boundaries[i + 1].position

    def test_detect_boundaries_with_invalid_structure(
        self,
        mock_llm_provider,
        sample_document
    ):
        """Test BoundaryDetector error handling with invalid structure"""
        # Arrange
        from src.chunking.models import TokenCounter

        detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        # Create structure with no sections (invalid)
        with pytest.raises(ValueError):
            Structure(
                document_id=sample_document.document_id,
                chapter_title="Test Chapter",
                sections=[],  # Invalid: no sections
                metadata={},
                analysis_model="openai/gpt-4o"
            )


# ============================================================================
# DocumentSegmenter Contract Tests
# ============================================================================


class TestDocumentSegmenterContract:
    """Test DocumentSegmenter component contract"""

    def test_segment_with_valid_inputs(
        self,
        mock_llm_provider,
        sample_document
    ):
        """Test DocumentSegmenter.segment() with valid inputs"""
        # Arrange
        from src.chunking.models import TokenCounter
        from src.chunking.metadata_validator import MetadataValidator

        segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=100,
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        boundaries = [
            SegmentBoundary(
                boundary_id="boundary_000000",
                position=0,
                boundary_type=BoundaryType.DOCUMENT_START,
                justification="Beginning of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            ),
            SegmentBoundary(
                boundary_id="boundary_000100",
                position=100,
                boundary_type=BoundaryType.DOCUMENT_END,
                justification="End of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            )
        ]

        # Act
        chunks = segmenter.segment(
            document=sample_document,
            structure=structure,
            boundaries=boundaries
        )

        # Assert
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.chunk_id is not None
            assert chunk.source_document == sample_document.document_id
            assert chunk.chunk_text is not None
            assert chunk.original_text is not None
            assert chunk.contextual_prefix is not None
            assert chunk.metadata is not None
            assert chunk.token_count > 0
            assert chunk.token_count <= 1000  # Must respect token limit

    def test_segment_metadata_validation(
        self,
        mock_llm_provider,
        sample_document
    ):
        """Test DocumentSegmenter validates metadata completeness"""
        # Arrange
        from src.chunking.models import TokenCounter
        from src.chunking.metadata_validator import MetadataValidator

        segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=200,
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        boundaries = [
            SegmentBoundary(
                boundary_id="boundary_000000",
                position=0,
                boundary_type=BoundaryType.DOCUMENT_START,
                justification="Beginning of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            ),
            SegmentBoundary(
                boundary_id="boundary_000200",
                position=200,
                boundary_type=BoundaryType.DOCUMENT_END,
                justification="End of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            )
        ]

        # Act
        chunks = segmenter.segment(
            document=sample_document,
            structure=structure,
            boundaries=boundaries
        )

        # Assert - All chunks must have valid metadata
        for chunk in chunks:
            # Check required metadata fields
            assert chunk.metadata.chapter_title
            assert chunk.metadata.section_title
            assert chunk.metadata.summary
            assert len(chunk.metadata.summary) >= 10

    def test_segment_token_limit_enforcement(
        self,
        mock_llm_provider,
        sample_document
    ):
        """Test DocumentSegmenter enforces token limits"""
        # Arrange
        from src.chunking.models import TokenCounter
        from src.chunking.metadata_validator import MetadataValidator

        segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=100,
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        boundaries = [
            SegmentBoundary(
                boundary_id="boundary_000000",
                position=0,
                boundary_type=BoundaryType.DOCUMENT_START,
                justification="Beginning of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            ),
            SegmentBoundary(
                boundary_id="boundary_000100",
                position=100,
                boundary_type=BoundaryType.DOCUMENT_END,
                justification="End of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            )
        ]

        # Act
        chunks = segmenter.segment(
            document=sample_document,
            structure=structure,
            boundaries=boundaries
        )

        # Assert - All chunks must be within token limit
        for chunk in chunks:
            assert chunk.token_count <= 1000, \
                f"Chunk {chunk.chunk_id} exceeds token limit: {chunk.token_count} > 1000"

    def test_segment_with_invalid_boundaries(
        self,
        mock_llm_provider,
        sample_document
    ):
        """Test DocumentSegmenter error handling with invalid boundaries"""
        # Arrange
        from src.chunking.models import TokenCounter
        from src.chunking.metadata_validator import MetadataValidator

        segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        structure = Structure(
            document_id=sample_document.document_id,
            chapter_title="Test Chapter",
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    start_char=0,
                    end_char=100,
                    parent_section=None
                )
            ],
            metadata={},
            analysis_model="openai/gpt-4o"
        )

        # Act & Assert - Empty boundaries list
        with pytest.raises(SegmentationError, match="No boundaries provided"):
            segmenter.segment(
                document=sample_document,
                structure=structure,
                boundaries=[]
            )

        # Act & Assert - Only one boundary (need at least 2)
        single_boundary = [
            SegmentBoundary(
                boundary_id="boundary_000000",
                position=0,
                boundary_type=BoundaryType.DOCUMENT_START,
                justification="Beginning of document",
                section_context="Test Chapter",
                estimated_chunk_size=0
            )
        ]

        with pytest.raises(SegmentationError, match="Need at least 2 boundaries"):
            segmenter.segment(
                document=sample_document,
                structure=structure,
                boundaries=single_boundary
            )
