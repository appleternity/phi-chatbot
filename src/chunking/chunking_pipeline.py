"""
Orchestrator for document chunking system.

This module coordinates the 2-phase document chunking pipeline:
Phase 1: Structure Analysis (StructureAnalyzer with Gemini Pro)
Phase 2: Chunk Extraction (ChunkExtractor with Claude Haiku)

It also handles validation, batch processing, and performance tracking.
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from time import time as get_time
from typing import Dict, Any, List
from tqdm import tqdm

from .chunk_extractor import ChunkExtractor
from .llm_provider import LLMProvider
from .models import (
    BatchProcessingResult,
    BatchReport,
    Chunk,
    ChunkExtractionError,
    Document,
    ProcessingReport,
    ProcessingResult,
    Structure,
    StructureAnalysisError,
    TextCoverageError,
    TokenCounter,
)
from .structure_analyzer import StructureAnalyzer
from .text_aligner import TextAligner


class ChunkingPipeline:
    """
    Main orchestrator for document chunking system.

    Coordinates the 2-phase processing:
    1. Structure analysis (StructureAnalyzer with Gemini Pro)
    2. Chunk extraction (ChunkExtractor with Claude Haiku)

    Validates output and tracks performance metrics.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        output_dir: Path,
        structure_model: str = "google/gemini-2.5-pro",
        extraction_model: str = "anthropic/claude-haiku-4.5",
        max_chunk_tokens: int = 1000
    ):
        """
        Initialize chunking pipeline.

        Args:
            llm_provider: LLM provider for API calls
            output_dir: Directory for output chunks (creates subdirs per document)
            structure_model: Model for Phase 1 structure analysis (default: Gemini Pro)
            extraction_model: Model for Phase 2 chunk extraction (default: Claude Haiku)
            max_chunk_tokens: Maximum tokens per chunk (default: 1000)
        """
        self.llm_provider = llm_provider
        self.output_dir = Path(output_dir)
        self.structure_model = structure_model
        self.extraction_model = extraction_model
        self.max_chunk_tokens = max_chunk_tokens

        # Initialize shared utilities
        self.token_counter = TokenCounter()

        # Initialize Phase components (no lazy loading)
        self.structure_analyzer = StructureAnalyzer(
            llm_client=self.llm_provider,
            model=self.structure_model,
            max_chunk_tokens=self.max_chunk_tokens,
            output_dir=self.output_dir
        )

        # Chunk extractor will be initialized per-document with output_dir
        # (since each document gets its own subdirectory)

    def _analyze_with_retry(
        self,
        document: Document,
        redo: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze document structure with exponential backoff for Gemini timeouts.

        Args:
            document: Document to analyze
            redo: If True, bypass cache
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Structure analysis result with structure and tokens consumed

        Raises:
            StructureAnalysisError: If all retries fail
        """
        import logging
        logger = logging.getLogger(__name__)

        for attempt in range(max_retries):
            try:
                return self.structure_analyzer.analyze(document, redo=redo)
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    sleep_time = 2 ** attempt
                    logger.warning(
                        f"Structure analysis failed (attempt {attempt + 1}/{max_retries}): {e}\n"
                        f"Retrying in {sleep_time}s..."
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Structure analysis failed after {max_retries} attempts")
                    raise

    def _extract_with_retry(
        self,
        chunk_extractor: ChunkExtractor,
        document: Document,
        structure: Structure,
        redo: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Extract chunks with exponential backoff for API timeouts.

        Args:
            chunk_extractor: ChunkExtractor instance to use
            document: Document to extract chunks from
            structure: Document structure from Phase 1
            redo: If True, bypass output file checks
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Extraction result with chunks and tokens consumed

        Raises:
            ChunkExtractionError: If all retries fail
        """
        import logging
        logger = logging.getLogger(__name__)

        for attempt in range(max_retries):
            try:
                return chunk_extractor.extract_chunks(
                    document=document,
                    structure=structure,
                    redo=redo
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    sleep_time = 2 ** attempt
                    logger.warning(
                        f"Chunk extraction failed (attempt {attempt + 1}/{max_retries}): {e}\n"
                        f"Retrying in {sleep_time}s..."
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Chunk extraction failed after {max_retries} attempts")
                    raise

    def process_document(
        self,
        document: Document,
        redo: bool = False
    ) -> ProcessingResult:
        """
        Process a single document through the 2-phase pipeline.

        Creates a subdirectory for each document in output_dir:
        - output_dir/{document_id}/{document_id}_structure.json
        - output_dir/{document_id}/{document_id}_chunk_001.json
        - output_dir/{document_id}/{document_id}_chunk_002.json
        - ...

        Args:
            document: Document to process
            redo: If True, bypass cache and force reprocessing (default: False)

        Returns:
            ProcessingResult with chunks, metrics, and validation results

        Raises:
            StructureAnalysisError: If Phase 1 fails after retries
            ChunkExtractionError: If Phase 2 fails
            TextCoverageError: If validation fails (< 99% coverage)
        """
        start_time = datetime.utcnow()
        start_timestamp = get_time()

        # Initialize token counters
        phase_1_tokens = 0
        phase_2_tokens = 0
        cache_hits = 0
        errors = []

        # Create document-specific output directory
        doc_output_dir = self.output_dir / document.document_id
        doc_output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # ================================================================
            # Phase 1: Structure Analysis (with retry logic for Gemini)
            # ================================================================
            print(f"Analyzing structure for document: {document.document_id}")
            structure_result = self._analyze_with_retry(document, redo=redo)

            structure: Structure = structure_result["structure"]
            phase_1_tokens = structure_result.get("tokens_consumed", 0)

            # Check if structure was cached
            if structure_result.get("cache_hit", False):
                cache_hits += 1

            # Save structure JSON to document output directory
            structure_file = doc_output_dir / f"{document.document_id}_structure.json"
            structure_file.write_text(
                json.dumps(structure.dict(), default=str, indent=2)
            )

            # ================================================================
            # Phase 2: Chunk Extraction (with document-specific output)
            # ================================================================
            print(f"Extracting chunks for document: {document.document_id}")
            chunk_extractor = ChunkExtractor(
                llm_client=self.llm_provider,
                token_counter=self.token_counter,
                model=self.extraction_model,
                max_chunk_tokens=self.max_chunk_tokens,
                output_dir=doc_output_dir,  # Document-specific output directory
                document_id=document.document_id
            )

            extraction_result = self._extract_with_retry(
                chunk_extractor=chunk_extractor,
                document=document,
                structure=structure,
                redo=redo
            )

            chunks: List[Chunk] = extraction_result["chunks"]
            phase_2_tokens = extraction_result.get("tokens_consumed", 0)

            # ================================================================
            # Validation: Text Coverage (99% coverage required)
            # ================================================================
            coverage_ratio, missing_segments = TextAligner.verify_coverage(
                original_text=document.content,
                chunks=chunks,
                min_coverage=0.99  # 99% minimum
            )

            # ================================================================
            # Calculate Metrics
            # ================================================================
            end_time = datetime.utcnow()
            end_timestamp = get_time()
            duration_seconds = end_timestamp - start_timestamp

            total_tokens = sum(chunk.token_count for chunk in chunks)
            total_tokens_consumed = phase_1_tokens + phase_2_tokens

            # Create processing report
            processing_report = ProcessingReport(
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration_seconds,
                phase_1_tokens=phase_1_tokens,
                phase_2_tokens=phase_2_tokens,
                total_tokens_consumed=total_tokens_consumed,
                cache_hits=cache_hits,
                errors=errors
            )

            # Create processing result
            result = ProcessingResult(
                document_id=document.document_id,
                chunks=chunks,
                structure=structure,
                text_coverage_ratio=coverage_ratio,
                total_chunks=len(chunks),
                total_tokens=total_tokens,
                processing_report=processing_report
            )

            return result

        except Exception as e:
            # Fail-fast with detailed context
            error_context = (
                f"Document: {document.document_id} | "
                f"Error type: {type(e).__name__} | "
                f"Message: {str(e)}"
            )

            # Re-raise with additional context
            if isinstance(e, (
                StructureAnalysisError,
                ChunkExtractionError,
                TextCoverageError
            )):
                # Known chunking errors - re-raise with context
                raise type(e)(f"{error_context} | Original: {str(e)}") from e
            else:
                # Unknown error - wrap in ChunkExtractionError
                raise ChunkExtractionError(
                    f"Unexpected error during document processing: {error_context}"
                ) from e

    def process_folder(
        self,
        folder_path: Path,
        redo: bool = False
    ) -> BatchProcessingResult:
        """
        Process all documents in a folder (batch processing).

        Args:
            folder_path: Path to folder containing documents
            redo: If True, bypass cache and force reprocessing (default: False)

        Returns:
            BatchProcessingResult with aggregated metrics

        Raises:
            FileNotFoundError: If folder doesn't exist
            ChunkExtractionError: If any document processing fails (fail-fast)
        """
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")

        # ================================================================
        # Discover Documents
        # ================================================================
        document_files = []
        for pattern in ["*.txt", "*.md"]:
            document_files.extend(folder_path.rglob(pattern))

        if not document_files:
            raise ValueError(f"No .txt or .md files found in {folder_path}")

        # ================================================================
        # Process Documents Sequentially (Fail-Fast)
        # ================================================================
        batch_start_time = datetime.utcnow()
        batch_start_timestamp = get_time()

        results: List[ProcessingResult] = []
        failed_documents: List[str] = []
        errors_by_document: dict = {}

        total_tokens_consumed = 0
        total_cache_hits = 0

        for doc_file in tqdm(sorted(document_files)):
            print(f"Processing document: {doc_file.name}")
            try:
                # Load document
                document = Document.from_file(doc_file)

                # Process document
                result = self.process_document(
                    document=document,
                    redo=redo
                )

                # Accumulate results
                results.append(result)
                total_tokens_consumed += result.processing_report.total_tokens_consumed
                total_cache_hits += result.processing_report.cache_hits

            except Exception as e:
                # Track failed document
                doc_id = doc_file.stem
                failed_documents.append(doc_id)
                errors_by_document[doc_id] = [str(e)]

                # Fail-fast: re-raise error with batch context
                batch_context = (
                    f"Batch processing failed at document: {doc_id} | "
                    f"Processed: {len(results)}/{len(document_files)} | "
                    f"Error: {type(e).__name__}: {str(e)}"
                )
                raise ChunkExtractionError(batch_context) from e

        # ================================================================
        # Aggregate Metrics
        # ================================================================
        batch_end_time = datetime.utcnow()
        batch_end_timestamp = get_time()
        total_duration_seconds = batch_end_timestamp - batch_start_timestamp

        total_chunks = sum(r.total_chunks for r in results)
        average_chunks_per_document = total_chunks / len(results) if results else 0.0

        # Create batch report
        batch_report = BatchReport(
            start_time=batch_start_time,
            end_time=batch_end_time,
            total_duration_seconds=total_duration_seconds,
            total_tokens_consumed=total_tokens_consumed,
            total_cache_hits=total_cache_hits,
            average_chunks_per_document=average_chunks_per_document,
            errors_by_document=errors_by_document
        )

        # Create batch result
        batch_id = str(uuid.uuid4())
        batch_result = BatchProcessingResult(
            batch_id=batch_id,
            results=results,
            failed_documents=failed_documents,
            total_documents=len(document_files),
            successful_documents=len(results),
            total_chunks=total_chunks,
            batch_report=batch_report
        )

        return batch_result
