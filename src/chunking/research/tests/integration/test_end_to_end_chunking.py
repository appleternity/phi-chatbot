"""
End-to-end integration tests for document chunking pipeline.

Tests the complete workflow from Document → ProcessingResult, verifying:
- 100% text coverage
- Metadata completeness
- Token limits
- Component integration
"""

import pytest
from pathlib import Path

from src.chunking.models import (
    Document,
    ProcessingResult,
    TextCoverageError,
    MetadataValidationError,
)
from src.chunking.chunking_pipeline import ChunkingPipeline
from src.chunking.structure_analyzer import StructureAnalyzer
from src.chunking.boundary_detector import BoundaryDetector
from src.chunking.document_segmenter import DocumentSegmenter
from src.chunking.models import TokenCounter
from src.chunking.metadata_validator import MetadataValidator
from src.chunking.text_aligner import TextAligner


# ============================================================================
# End-to-End Pipeline Tests
# ============================================================================


class TestEndToEndChunking:
    """Test complete document chunking pipeline"""

    def test_full_pipeline_with_sample_document(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test complete pipeline from Document to ProcessingResult"""
        # Arrange - Set up pipeline with all components
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        # Inject components with proper dependencies
        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act - Process document through full pipeline
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Verify ProcessingResult structure
        assert isinstance(result, ProcessingResult)
        assert result.document_id == sample_document.document_id
        assert len(result.chunks) > 0
        assert result.structure is not None
        assert result.total_chunks == len(result.chunks)
        assert result.processing_report is not None

    def test_pipeline_text_coverage_verification(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline verifies 100% text coverage"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Verify text coverage is near 100%
        assert result.text_coverage_ratio >= 0.99, \
            f"Text coverage is {result.text_coverage_ratio:.2%}, expected ≥99%"

        # Manually verify coverage using TextAligner
        coverage_ratio, missing_segments = TextAligner.verify_coverage(
            original_text=sample_document.content,
            chunks=result.chunks,
            min_coverage=0.99
        )

        assert coverage_ratio >= 0.99
        assert len(missing_segments) == 0 or sum(len(s) for s in missing_segments) < 10

    def test_pipeline_metadata_completeness(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline ensures metadata completeness for all chunks"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Verify metadata completeness for all chunks
        for chunk in result.chunks:
            # Required fields must be present
            assert chunk.metadata.chapter_title, \
                f"Chunk {chunk.chunk_id} missing chapter_title"
            assert chunk.metadata.section_title, \
                f"Chunk {chunk.chunk_id} missing section_title"
            assert chunk.metadata.summary, \
                f"Chunk {chunk.chunk_id} missing summary"

            # Summary must be meaningful (10-500 chars)
            assert len(chunk.metadata.summary) >= 10, \
                f"Chunk {chunk.chunk_id} summary too short: {len(chunk.metadata.summary)} chars"
            assert len(chunk.metadata.summary) <= 500, \
                f"Chunk {chunk.chunk_id} summary too long: {len(chunk.metadata.summary)} chars"

            # No placeholder values
            placeholders = {'todo', 'n/a', 'none', 'tbd', '...', 'summary'}
            assert chunk.metadata.chapter_title.lower() not in placeholders
            assert chunk.metadata.section_title.lower() not in placeholders
            assert chunk.metadata.summary.lower() not in placeholders

    def test_pipeline_token_limit_enforcement(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline enforces token limits for all chunks"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        max_tokens = 1000

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=max_tokens
        )

        # Assert - All chunks must be within token limit
        for chunk in result.chunks:
            assert chunk.token_count <= max_tokens, \
                f"Chunk {chunk.chunk_id} exceeds token limit: " \
                f"{chunk.token_count} > {max_tokens}"

            # Also verify token count is reasonable (not zero)
            assert chunk.token_count > 0, \
                f"Chunk {chunk.chunk_id} has invalid token count: {chunk.token_count}"

    def test_pipeline_chunk_text_structure(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline generates chunks with proper text structure"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Verify chunk text structure
        for chunk in result.chunks:
            # Chunk text should include contextual prefix
            assert chunk.chunk_text.startswith("This chunk is from"), \
                f"Chunk {chunk.chunk_id} missing contextual prefix"

            # Original text should be preserved
            assert chunk.original_text, \
                f"Chunk {chunk.chunk_id} missing original_text"

            # Contextual prefix should be present
            assert chunk.contextual_prefix, \
                f"Chunk {chunk.chunk_id} missing contextual_prefix"

            # Chunk text should be: prefix + "\n\n" + cleaned original text
            assert "\n\n" in chunk.chunk_text, \
                f"Chunk {chunk.chunk_id} missing separator between prefix and text"

    def test_pipeline_processing_report(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline generates comprehensive processing report"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Verify processing report structure
        report = result.processing_report

        assert report.start_time is not None
        assert report.end_time is not None
        assert report.duration_seconds >= 0

        # Token consumption should be tracked
        assert report.phase_1_tokens >= 0
        assert report.phase_2_tokens >= 0
        assert report.phase_3_tokens >= 0
        assert report.total_tokens_consumed >= 0

        # Cache hits should be tracked
        assert report.cache_hits >= 0

        # Errors should be empty (successful processing)
        assert len(report.errors) == 0

    def test_pipeline_with_multiple_documents(
        self,
        mock_llm_provider,
        mock_cache_store,
        tmp_path
    ):
        """Test pipeline can process multiple different documents"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Create multiple test documents
        doc1_path = tmp_path / "doc1.txt"
        doc1_path.write_text("# Document 1\n\nThis is the first test document with some content.")

        doc2_path = tmp_path / "doc2.txt"
        doc2_path.write_text("# Document 2\n\nThis is the second test document with different content.")

        doc1 = Document.from_file(doc1_path)
        doc2 = Document.from_file(doc2_path)

        # Act - Process both documents
        result1 = pipeline.process_document(doc1, max_chunk_tokens=1000)
        result2 = pipeline.process_document(doc2, max_chunk_tokens=1000)

        # Assert - Both should succeed with different document IDs
        assert result1.document_id != result2.document_id
        assert len(result1.chunks) > 0
        assert len(result2.chunks) > 0

        # Chunks should have correct source document
        for chunk in result1.chunks:
            assert chunk.source_document == doc1.document_id

        for chunk in result2.chunks:
            assert chunk.source_document == doc2.document_id

    def test_pipeline_error_handling(
        self,
        mock_cache_store,
        tmp_path
    ):
        """Test pipeline error handling with invalid inputs"""
        # Arrange - Create mock LLM that always fails
        from src.chunking.llm_provider import MockLLMProvider

        failing_llm = MockLLMProvider(responses={})  # Empty responses will cause failure

        pipeline = ChunkingPipeline(
            llm_provider=failing_llm,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=failing_llm,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        # Create test document
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("# Test Document\n\nSome content here.")
        document = Document.from_file(doc_path)

        # Act & Assert - Should raise error with context
        with pytest.raises(Exception):  # Could be StructureAnalysisError or other
            pipeline.process_document(document, max_chunk_tokens=1000)

    def test_pipeline_chunk_ordering(
        self,
        mock_llm_provider,
        mock_cache_store,
        sample_document
    ):
        """Test pipeline produces chunks in correct order"""
        # Arrange
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        pipeline._structure_analyzer = StructureAnalyzer(
            llm_client=mock_llm_provider,
            cache_store=mock_cache_store,
            model="openai/gpt-4o"
        )

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=mock_llm_provider,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act
        result = pipeline.process_document(
            document=sample_document,
            max_chunk_tokens=1000
        )

        # Assert - Chunks should be ordered by position
        for i in range(len(result.chunks) - 1):
            current_chunk = result.chunks[i]
            next_chunk = result.chunks[i + 1]

            # Character spans should be non-overlapping and in order
            assert current_chunk.character_span[0] < next_chunk.character_span[0], \
                f"Chunks not in order: {current_chunk.chunk_id} and {next_chunk.chunk_id}"
