"""
Indexing pipeline for chunked documents to PostgreSQL with pgvector.

This module provides batch indexing functionality for JSON chunk files:
- Parse JSON chunk files and extract ChunkMetadata
- Generate embeddings using Qwen3EmbeddingEncoder with MPS acceleration
- Insert into PostgreSQL with duplicate handling (ON CONFLICT DO NOTHING)
- Error handling: log failures, continue processing remaining files
- Progress tracking with rich progress bar

Usage:
    from src.embeddings.indexer import DocumentIndexer
    from app.db.connection import get_pool

    pool = await get_pool()
    indexer = DocumentIndexer(
        db_pool=pool,
        model_name="Qwen/Qwen3-Embedding-0.6B",
        device="mps",
        batch_size=16,
        normalize_embeddings=True
    )

    stats = await indexer.index_directory(
        input_dir="data/chunking_final",
        skip_existing=True
    )
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)

from src.embeddings.encoder import Qwen3EmbeddingEncoder
from src.embeddings.models import ChunkMetadata, VectorDocument
from app.db.connection import DatabasePool


logger = logging.getLogger(__name__)
console = Console()


class IndexingError(Exception):
    """Base exception for indexing errors."""
    pass


class IndexingStats:
    """Statistics for indexing operations."""

    def __init__(self):
        self.total_files = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.errors: List[Dict[str, str]] = []

    def add_success(self) -> None:
        """Record successful indexing."""
        self.successful += 1

    def add_failure(self, file_path: str, error: str) -> None:
        """Record failed indexing."""
        self.failed += 1
        self.errors.append({
            "file": file_path,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def add_skip(self) -> None:
        """Record skipped file."""
        self.skipped += 1

    def finalize(self) -> None:
        """Mark indexing as complete."""
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> float:
        """Get total duration in seconds."""
        if self.end_time is None:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_seconds": round(self.duration_seconds, 2),
            "success_rate": round(self.successful / self.total_files * 100, 2) if self.total_files > 0 else 0,
            "errors": self.errors
        }


class DocumentIndexer:
    """
    Document indexer for batch embedding generation and database insertion.

    Provides high-level interface for indexing JSON chunk files:
    - Batch processing with configurable batch size
    - MPS acceleration for Apple Silicon
    - Duplicate handling with ON CONFLICT DO NOTHING
    - Progress tracking with rich progress bar
    - Error logging to indexing_errors.log

    Attributes:
        db_pool: Database connection pool
        encoder: Qwen3EmbeddingEncoder instance
        error_log_path: Path to error log file
    """

    def __init__(
        self,
        db_pool: DatabasePool,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: Literal["mps", "cuda", "cpu"] = "mps",
        batch_size: int = 16,
        max_length: int = 8196,
        normalize_embeddings: bool = True,
        instruction: Optional[str] = None,
        error_log_path: str = "indexing_errors.log"
    ):
        """
        Initialize document indexer.

        Args:
            db_pool: Initialized DatabasePool instance
            model_name: HuggingFace model ID (default: Qwen/Qwen3-Embedding-0.6B)
            device: Inference device - "mps", "cuda", or "cpu" (default: mps)
            batch_size: Batch size for embedding generation (default: 16)
            max_length: Maximum token length for inputs (default: 8196)
            normalize_embeddings: Whether to L2 normalize embeddings (default: True)
            instruction: Optional task-specific instruction prefix (default: None)
            error_log_path: Path to error log file (default: indexing_errors.log)
        """
        self.db_pool = db_pool
        self.error_log_path = Path(error_log_path)

        # Initialize encoder with direct parameters
        logger.info("Initializing Qwen3EmbeddingEncoder")
        self.encoder = Qwen3EmbeddingEncoder(
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
            normalize_embeddings=normalize_embeddings,
            instruction=instruction
        )
        logger.info(f"Encoder initialized: {self.encoder}")

        # Setup error logging
        self._setup_error_logging()

    def _setup_error_logging(self) -> None:
        """Setup error logging to file."""
        error_handler = logging.FileHandler(self.error_log_path)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        logger.addHandler(error_handler)
        logger.info(f"Error logging enabled: {self.error_log_path}")

    def parse_chunk_file(self, file_path: Path) -> Optional[ChunkMetadata]:
        """
        Parse JSON chunk file and extract ChunkMetadata.

        Extracts required fields:
        - chunk_id, source_document, chunk_text, token_count (required)
        - chapter_title, section_title, subsection_title, summary (optional, from metadata)

        Args:
            file_path: Path to JSON chunk file

        Returns:
            ChunkMetadata if parsing succeeds, None if file is invalid

        Raises:
            ValueError: If required fields are missing or invalid
            json.JSONDecodeError: If JSON is malformed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract metadata fields (optional, defaults to empty)
            metadata = data.get('metadata', {})

            # Create ChunkMetadata
            chunk_metadata = ChunkMetadata(
                chunk_id=data['chunk_id'],
                source_document=data['source_document'],
                chapter_title=metadata.get('chapter_title', ''),
                section_title=metadata.get('section_title', ''),
                subsection_title=metadata.get('subsection_title', []),
                summary=metadata.get('summary', ''),
                token_count=data['token_count'],
                chunk_text=data['chunk_text']
            )

            return chunk_metadata

        except KeyError as e:
            logger.error(f"Missing required field in {file_path}: {e}")
            raise ValueError(f"Missing required field: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            raise

    async def generate_embeddings(
        self,
        chunks: List[ChunkMetadata]
    ) -> List[VectorDocument]:
        """
        Generate embeddings for a batch of chunks.

        Args:
            chunks: List of ChunkMetadata objects

        Returns:
            List of VectorDocument objects with embeddings

        Raises:
            RuntimeError: If embedding generation fails
        """
        try:
            # Extract chunk texts
            texts = [chunk.chunk_text for chunk in chunks]

            # Generate embeddings in batch
            embeddings = self.encoder.encode(
                texts,
                batch_size=self.encoder.batch_size,
                show_progress=False
            )

            # Convert to VectorDocument objects
            vector_docs = []
            for chunk, embedding in zip(chunks, embeddings):
                vector_doc = VectorDocument(
                    **chunk.model_dump(),
                    embedding=embedding.tolist(),
                    created_at=datetime.now(timezone.utc)
                )
                vector_docs.append(vector_doc)

            return vector_docs

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")

    async def insert_documents(
        self,
        documents: List[VectorDocument]
    ) -> int:
        """
        Insert vector documents into database with duplicate handling.

        Uses ON CONFLICT (chunk_id) DO NOTHING to skip existing chunks.

        Args:
            documents: List of VectorDocument objects

        Returns:
            Number of documents successfully inserted

        Raises:
            RuntimeError: If database insertion fails
        """
        if not documents:
            return 0

        try:
            # Prepare INSERT query with ON CONFLICT DO NOTHING
            insert_query = """
            INSERT INTO vector_chunks (
                chunk_id,
                source_document,
                chapter_title,
                section_title,
                subsection_title,
                summary,
                token_count,
                chunk_text,
                embedding,
                created_at,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            )
            ON CONFLICT (chunk_id) DO NOTHING
            """

            # Insert documents
            inserted_count = 0
            for doc in documents:
                try:
                    await self.db_pool.execute(
                        insert_query,
                        doc.chunk_id,
                        doc.source_document,
                        doc.chapter_title,
                        doc.section_title,
                        doc.subsection_title,  # PostgreSQL array
                        doc.summary,
                        doc.token_count,
                        doc.chunk_text,
                        doc.embedding,  # pgvector handles list conversion
                        doc.created_at,
                        datetime.now(timezone.utc)
                    )
                    inserted_count += 1
                except Exception as e:
                    # Log individual insertion failures but continue
                    logger.error(f"Failed to insert {doc.chunk_id}: {e}")

            return inserted_count

        except Exception as e:
            logger.error(f"Database insertion failed: {e}")
            raise RuntimeError(f"Database insertion failed: {e}")

    async def check_chunk_exists(self, chunk_id: str) -> bool:
        """
        Check if chunk already exists in database.

        Args:
            chunk_id: Unique chunk identifier

        Returns:
            True if chunk exists, False otherwise
        """
        try:
            result = await self.db_pool.fetch(
                "SELECT EXISTS(SELECT 1 FROM vector_chunks WHERE chunk_id = $1)",
                chunk_id
            )
            return result[0]['exists'] if result else False
        except Exception as e:
            logger.warning(f"Failed to check if {chunk_id} exists: {e}")
            return False

    async def index_file(
        self,
        file_path: Path,
        skip_existing: bool = False
    ) -> bool:
        """
        Index a single chunk file.

        Args:
            file_path: Path to JSON chunk file
            skip_existing: Skip if chunk already exists in database

        Returns:
            True if indexing succeeded, False otherwise
        """
        try:
            # Parse chunk file
            chunk_metadata = self.parse_chunk_file(file_path)
            if chunk_metadata is None:
                return False

            # Check if exists (if skip_existing enabled)
            if skip_existing:
                exists = await self.check_chunk_exists(chunk_metadata.chunk_id)
                if exists:
                    logger.debug(f"Skipping existing chunk: {chunk_metadata.chunk_id}")
                    return True  # Return True for skipped (not an error)

            # Generate embedding
            vector_docs = await self.generate_embeddings([chunk_metadata])

            # Insert into database
            inserted = await self.insert_documents(vector_docs)

            return inserted > 0

        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return False

    async def index_directory(
        self,
        input_dir: str,
        skip_existing: bool = False,
        batch_size: Optional[int] = None,
        verbose: bool = False
    ) -> IndexingStats:
        """
        Index all chunk files in directory and subdirectories.

        Args:
            input_dir: Directory containing JSON chunk files
            skip_existing: Skip chunks that already exist in database
            batch_size: Batch size for embedding generation (default: from config)
            verbose: Enable verbose logging

        Returns:
            IndexingStats with success/failure counts and timing

        Raises:
            ValueError: If input directory doesn't exist
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_dir}")

        # Find all chunk files (exclude structure files)
        chunk_files = list(input_path.rglob("*chunk_*.json"))

        if not chunk_files:
            logger.warning(f"No chunk files found in {input_dir}")
            return IndexingStats()

        # Initialize stats
        stats = IndexingStats()
        stats.total_files = len(chunk_files)

        # Override batch size if specified
        if batch_size is not None:
            self.encoder.batch_size = batch_size

        # Setup progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]Indexing chunks...",
                total=stats.total_files
            )

            # Process files in batches
            for i in range(0, len(chunk_files), self.encoder.batch_size):
                batch_files = chunk_files[i:i + self.encoder.batch_size]

                # Parse batch
                batch_chunks = []
                for file_path in batch_files:
                    try:
                        # Check if skip_existing
                        chunk_metadata = self.parse_chunk_file(file_path)

                        if skip_existing:
                            exists = await self.check_chunk_exists(chunk_metadata.chunk_id)
                            if exists:
                                stats.add_skip()
                                progress.update(task, advance=1)
                                continue

                        batch_chunks.append(chunk_metadata)

                    except Exception as e:
                        stats.add_failure(str(file_path), str(e))
                        logger.error(f"Failed to parse {file_path}: {e}")
                        progress.update(task, advance=1)

                # Generate embeddings for batch
                if batch_chunks:
                    try:
                        vector_docs = await self.generate_embeddings(batch_chunks)
                        inserted = await self.insert_documents(vector_docs)
                        stats.successful += inserted

                        if verbose:
                            logger.info(
                                f"Batch complete: {inserted}/{len(batch_chunks)} inserted"
                            )

                        # Update progress for batch
                        progress.update(task, advance=len(batch_chunks))

                    except Exception as e:
                        # Batch failed - mark all as failed
                        for chunk in batch_chunks:
                            stats.add_failure(chunk.chunk_id, str(e))
                        logger.error(f"Batch embedding/insertion failed: {e}")
                        progress.update(task, advance=len(batch_chunks))

        # Finalize stats
        stats.finalize()

        # Log summary
        logger.info(
            f"Indexing complete: {stats.successful} successful, "
            f"{stats.failed} failed, {stats.skipped} skipped "
            f"in {stats.duration_seconds:.2f}s"
        )

        return stats

    async def validate_indexed_chunks(
        self,
        input_dir: str
    ) -> Dict[str, Any]:
        """
        Validate indexed chunks against JSON files.

        Checks:
        - Count matches: JSON files vs database records
        - Embedding dimensions are consistent (not hardcoded)
        - No NULL embeddings

        Args:
            input_dir: Directory containing JSON chunk files

        Returns:
            Dictionary with validation results:
            - total_files: Number of JSON chunk files
            - total_db_chunks: Number of database records
            - count_match: True if counts match
            - expected_dimension: Expected embedding dimension from model
            - invalid_embeddings: List of dicts with chunk_id, dimension, expected
            - validation_passed: True if all checks passed
        """
        input_path = Path(input_dir)

        # Count JSON files
        chunk_files = list(input_path.rglob("*chunk_*.json"))
        total_files = len(chunk_files)

        # Count database records
        total_db_chunks = await self.db_pool.fetchval(
            "SELECT COUNT(*) FROM vector_chunks"
        )

        # Get expected embedding dimension from encoder (generic validation)
        expected_dim = self.encoder.get_embedding_dimension()

        # Check for inconsistent embedding dimensions (no LIMIT - check all records)
        inconsistent_query = """
        SELECT chunk_id, vector_dims(embedding) as dim
        FROM vector_chunks
        WHERE vector_dims(embedding) != $1
           OR embedding IS NULL
        """

        inconsistent_results = await self.db_pool.fetch(
            inconsistent_query,
            expected_dim
        )

        invalid_embeddings = [
            {
                "chunk_id": row['chunk_id'],
                "dimension": row['dim'],
                "expected": expected_dim
            }
            for row in inconsistent_results
        ]

        # Validation results
        count_match = total_files == total_db_chunks
        validation_passed = count_match and len(invalid_embeddings) == 0

        results = {
            "total_files": total_files,
            "total_db_chunks": total_db_chunks,
            "count_match": count_match,
            "expected_dimension": expected_dim,
            "invalid_embeddings": invalid_embeddings,
            "validation_passed": validation_passed
        }

        # Fail-fast logging
        if validation_passed:
            logger.info("✅ Validation passed: All checks successful")
        else:
            if not count_match:
                logger.error(
                    f"❌ Count mismatch: {total_files} files vs {total_db_chunks} DB records"
                )
            if invalid_embeddings:
                logger.error(
                    f"❌ Found {len(invalid_embeddings)} chunks with inconsistent embeddings"
                )
                logger.error(f"Expected dimension: {expected_dim}")
                for invalid in invalid_embeddings[:5]:  # Show first 5
                    logger.error(
                        f"  - {invalid['chunk_id']}: dim={invalid['dimension']}"
                    )

        return results
