"""
Batch processing integration tests for chunking pipeline.

Tests Phase 4: Batch Processing functionality including:
- T048: Basic batch processing with multiple documents
- T049: Fail-fast behavior on errors
- T050: Document identifier preservation
- T051: Consolidated output format
"""

import pytest
from pathlib import Path

from src.chunking.models import (
    Document,
    BatchProcessingResult,
    SegmentationError,
)
from src.chunking.chunking_pipeline import ChunkingPipeline
from src.chunking.structure_analyzer import StructureAnalyzer
from src.chunking.boundary_detector import BoundaryDetector
from src.chunking.document_segmenter import DocumentSegmenter
from src.chunking.models import TokenCounter
from src.chunking.metadata_validator import MetadataValidator


# ============================================================================
# Batch Processing Tests (T048-T051)
# ============================================================================


class TestBatchProcessing:
    """Test batch processing functionality (Phase 4)"""

    @pytest.fixture
    def batch_test_folder(self, tmp_path):
        """Create folder with 5 test documents"""
        docs_folder = tmp_path / "test_documents"
        docs_folder.mkdir()

        # Create 5 test documents with different content
        doc_contents = [
            "# Document 1\n\nThis is the first test document with introduction content.",
            "# Document 2\n\nThis is the second test document discussing methods.",
            "# Document 3\n\nThis is the third test document covering results.",
            "# Document 4\n\nThis is the fourth test document analyzing findings.",
            "# Document 5\n\nThis is the fifth test document with conclusions.",
        ]

        for i, content in enumerate(doc_contents, 1):
            doc_file = docs_folder / f"document_{i}.txt"
            doc_file.write_text(content)

        return docs_folder

    @pytest.fixture
    def configured_pipeline(self, mock_llm_provider, mock_cache_store):
        """Create fully configured pipeline for batch tests"""
        pipeline = ChunkingPipeline(
            llm_provider=mock_llm_provider,
            cache_store=mock_cache_store,
            structure_model="openai/gpt-4o",
            boundary_model="openai/gpt-4o",
            segmentation_model="google/gemini-2.0-flash-exp"
        )

        # Inject components
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

        return pipeline

    def test_batch_processing_basic_functionality(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """T048: Test basic batch processing with 5 documents"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify BatchProcessingResult structure
        assert isinstance(batch_result, BatchProcessingResult)
        assert batch_result.batch_id is not None
        assert batch_result.total_documents == 5
        assert batch_result.successful_documents == 5
        assert len(batch_result.failed_documents) == 0

        # Verify all documents were processed
        assert len(batch_result.results) == 5

        # Verify batch report
        assert batch_result.batch_report is not None
        assert batch_result.batch_report.start_time is not None
        assert batch_result.batch_report.end_time is not None
        assert batch_result.batch_report.total_duration_seconds >= 0

    def test_batch_processing_consolidated_output_format(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """T051: Test consolidated output format"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify consolidated output structure
        assert batch_result.total_chunks > 0

        # Verify average chunks per document
        assert batch_result.batch_report.average_chunks_per_document > 0
        expected_avg = batch_result.total_chunks / batch_result.successful_documents
        assert abs(batch_result.batch_report.average_chunks_per_document - expected_avg) < 0.01

        # Verify token consumption is aggregated
        assert batch_result.batch_report.total_tokens_consumed >= 0

        # Verify cache hits are aggregated
        assert batch_result.batch_report.total_cache_hits >= 0

        # Verify errors are consolidated
        assert isinstance(batch_result.batch_report.errors_by_document, dict)

    def test_batch_processing_document_identifier_preservation(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """T050: Test document identifiers are preserved throughout processing"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify document identifiers are preserved
        expected_doc_ids = {f"document_{i}" for i in range(1, 6)}
        actual_doc_ids = {result.document_id for result in batch_result.results}

        assert expected_doc_ids == actual_doc_ids, \
            f"Document IDs mismatch. Expected: {expected_doc_ids}, Got: {actual_doc_ids}"

        # Verify each chunk has correct source document
        for result in batch_result.results:
            for chunk in result.chunks:
                assert chunk.source_document == result.document_id, \
                    f"Chunk {chunk.chunk_id} source mismatch: " \
                    f"expected {result.document_id}, got {chunk.source_document}"

                # Verify chunk IDs include document identifier
                assert result.document_id in chunk.chunk_id, \
                    f"Chunk ID {chunk.chunk_id} doesn't include document ID {result.document_id}"

    def test_batch_processing_fail_fast_behavior(
        self,
        mock_cache_store,
        tmp_path
    ):
        """T049: Test fail-fast behavior when document processing fails"""
        # Arrange - Create folder with 3 documents
        docs_folder = tmp_path / "test_documents"
        docs_folder.mkdir()

        # Create valid documents
        (docs_folder / "doc1.txt").write_text("# Doc 1\n\nValid content.")
        (docs_folder / "doc2.txt").write_text("# Doc 2\n\nValid content.")
        (docs_folder / "doc3.txt").write_text("# Doc 3\n\nValid content.")

        # Create mock LLM that fails after first document
        from src.chunking.llm_provider import MockLLMProvider

        call_count = {"count": 0}

        class FailingLLMProvider(MockLLMProvider):
            def chat_completion(self, **kwargs):
                call_count["count"] += 1
                if call_count["count"] > 3:  # Fail after first document (3 phases)
                    raise Exception("Simulated LLM failure")
                return super().chat_completion(**kwargs)

        failing_llm = FailingLLMProvider(responses={
            "openai/gpt-4o": {
                "id": "test",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Title\t1\t0\t100\tROOT"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            }
        })

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

        pipeline._boundary_detector = BoundaryDetector(
            llm_client=failing_llm,
            token_counter=TokenCounter(),
            model="openai/gpt-4o"
        )

        pipeline._document_segmenter = DocumentSegmenter(
            llm_client=failing_llm,
            token_counter=TokenCounter(),
            metadata_validator=MetadataValidator(),
            model="google/gemini-2.0-flash-exp"
        )

        # Act & Assert - Should fail fast with context
        with pytest.raises(SegmentationError) as exc_info:
            pipeline.process_folder(
                folder_path=docs_folder,
                max_chunk_tokens=1000
            )

        # Verify error message includes batch context
        error_message = str(exc_info.value)
        assert "Batch processing failed" in error_message
        assert "Processed:" in error_message

    def test_batch_processing_empty_folder(
        self,
        configured_pipeline,
        tmp_path
    ):
        """Test batch processing with empty folder"""
        # Arrange - Create empty folder
        empty_folder = tmp_path / "empty_folder"
        empty_folder.mkdir()

        # Act & Assert - Should raise error
        with pytest.raises(ValueError, match="No .txt or .md files found"):
            configured_pipeline.process_folder(
                folder_path=empty_folder,
                max_chunk_tokens=1000
            )

    def test_batch_processing_nonexistent_folder(
        self,
        configured_pipeline,
        tmp_path
    ):
        """Test batch processing with nonexistent folder"""
        # Arrange - Reference nonexistent folder
        nonexistent = tmp_path / "nonexistent_folder"

        # Act & Assert - Should raise error
        with pytest.raises(FileNotFoundError, match="Folder not found"):
            configured_pipeline.process_folder(
                folder_path=nonexistent,
                max_chunk_tokens=1000
            )

    def test_batch_processing_metrics_aggregation(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """Test batch processing aggregates metrics correctly"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify metrics aggregation
        total_chunks = sum(result.total_chunks for result in batch_result.results)
        assert batch_result.total_chunks == total_chunks

        # Verify average calculation
        expected_average = total_chunks / batch_result.successful_documents
        assert abs(batch_result.batch_report.average_chunks_per_document - expected_average) < 0.01

        # Verify token consumption aggregation
        total_tokens = sum(
            result.processing_report.total_tokens_consumed
            for result in batch_result.results
        )
        assert batch_result.batch_report.total_tokens_consumed == total_tokens

    def test_batch_processing_with_markdown_files(
        self,
        configured_pipeline,
        tmp_path
    ):
        """Test batch processing works with .md files"""
        # Arrange - Create folder with markdown files
        docs_folder = tmp_path / "markdown_docs"
        docs_folder.mkdir()

        for i in range(1, 4):
            doc_file = docs_folder / f"document_{i}.md"
            doc_file.write_text(f"# Document {i}\n\nMarkdown content for document {i}.")

        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=docs_folder,
            max_chunk_tokens=1000
        )

        # Assert
        assert batch_result.total_documents == 3
        assert batch_result.successful_documents == 3
        assert len(batch_result.failed_documents) == 0

    def test_batch_processing_mixed_file_types(
        self,
        configured_pipeline,
        tmp_path
    ):
        """Test batch processing with mixed .txt and .md files"""
        # Arrange
        docs_folder = tmp_path / "mixed_docs"
        docs_folder.mkdir()

        # Create .txt files
        (docs_folder / "doc1.txt").write_text("# Doc 1\n\nText file content.")
        (docs_folder / "doc2.txt").write_text("# Doc 2\n\nText file content.")

        # Create .md files
        (docs_folder / "doc3.md").write_text("# Doc 3\n\nMarkdown content.")
        (docs_folder / "doc4.md").write_text("# Doc 4\n\nMarkdown content.")

        # Create non-document files (should be ignored)
        (docs_folder / "readme.pdf").write_bytes(b"PDF content")
        (docs_folder / "config.json").write_text('{"key": "value"}')

        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=docs_folder,
            max_chunk_tokens=1000
        )

        # Assert - Should process only .txt and .md files
        assert batch_result.total_documents == 4
        assert batch_result.successful_documents == 4

    def test_batch_processing_preserves_processing_order(
        self,
        configured_pipeline,
        tmp_path
    ):
        """Test batch processing maintains consistent processing order"""
        # Arrange
        docs_folder = tmp_path / "ordered_docs"
        docs_folder.mkdir()

        # Create documents with specific names
        doc_names = ["doc_a.txt", "doc_b.txt", "doc_c.txt"]
        for name in doc_names:
            (docs_folder / name).write_text(f"# {name}\n\nContent for {name}.")

        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=docs_folder,
            max_chunk_tokens=1000
        )

        # Assert - Documents should be processed in sorted order
        result_doc_ids = [result.document_id for result in batch_result.results]

        # Expected order is alphabetical (sorted by filename)
        expected_order = ["doc_a", "doc_b", "doc_c"]
        assert result_doc_ids == expected_order

    def test_batch_processing_report_completeness(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """Test batch processing report contains all required fields"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify report completeness
        report = batch_result.batch_report

        # Time tracking
        assert report.start_time is not None
        assert report.end_time is not None
        assert report.total_duration_seconds >= 0
        assert report.end_time >= report.start_time

        # Token tracking
        assert report.total_tokens_consumed >= 0

        # Cache tracking
        assert report.total_cache_hits >= 0

        # Performance metrics
        assert report.average_chunks_per_document >= 0

        # Error tracking
        assert isinstance(report.errors_by_document, dict)

    def test_batch_processing_chunk_count_consistency(
        self,
        configured_pipeline,
        batch_test_folder
    ):
        """Test batch processing maintains consistent chunk counts"""
        # Act
        batch_result = configured_pipeline.process_folder(
            folder_path=batch_test_folder,
            max_chunk_tokens=1000
        )

        # Assert - Verify chunk count consistency
        # Sum of individual document chunks should equal total
        sum_of_chunks = sum(result.total_chunks for result in batch_result.results)
        assert batch_result.total_chunks == sum_of_chunks

        # Each result should have non-zero chunks
        for result in batch_result.results:
            assert result.total_chunks > 0
            assert len(result.chunks) == result.total_chunks
