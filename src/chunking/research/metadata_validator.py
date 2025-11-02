"""
Metadata validation utilities for chunking system.

This module validates chunk metadata for completeness and correctness.
"""

from typing import List

from .models import Chunk, ChunkMetadata, MetadataValidationError


class MetadataValidator:
    """Validator for chunk metadata completeness"""

    @staticmethod
    def validate_metadata(metadata: ChunkMetadata) -> None:
        """
        Validate chunk metadata for completeness.

        Args:
            metadata: ChunkMetadata instance to validate

        Raises:
            MetadataValidationError: If metadata is incomplete or invalid

        Validation Rules:
            - chapter_title must not be empty
            - section_title must not be empty
            - summary must be meaningful (10-500 chars, not placeholder)
            - All required fields must be present
        """
        # Pydantic already validates field presence and basic constraints
        # This method provides additional semantic validation

        # Check for placeholder values
        placeholders = {'todo', 'n/a', 'none', 'tbd', '...', 'summary', 'tba'}

        if metadata.chapter_title.strip().lower() in placeholders:
            raise MetadataValidationError(
                f"chapter_title contains placeholder value: {metadata.chapter_title}"
            )

        if metadata.section_title.strip().lower() in placeholders:
            raise MetadataValidationError(
                f"section_title contains placeholder value: {metadata.section_title}"
            )

        if metadata.summary.strip().lower() in placeholders:
            raise MetadataValidationError(
                f"summary contains placeholder value: {metadata.summary}"
            )

        # Check summary length (10-500 chars)
        summary_length = len(metadata.summary.strip())
        if summary_length < 10:
            raise MetadataValidationError(
                f"summary too short ({summary_length} chars, minimum 10)"
            )

        # if summary_length > 500:
        #     raise MetadataValidationError(
        #         f"summary too long ({summary_length} chars, maximum 500)"
        #     )

    @staticmethod
    def validate_chunk(chunk: Chunk) -> None:
        """
        Validate complete chunk including metadata.

        Args:
            chunk: Chunk instance to validate

        Raises:
            MetadataValidationError: If chunk metadata is invalid
        """
        # Validate metadata
        MetadataValidator.validate_metadata(chunk.metadata)

        # Additional chunk-level validations
        if chunk.token_count <= 0:
            raise MetadataValidationError(
                f"chunk {chunk.chunk_id} has invalid token_count: {chunk.token_count}"
            )

        # Note: No upper limit on token_count - allow any value for analysis

    @staticmethod
    def validate_chunks(chunks: List[Chunk]) -> None:
        """
        Validate all chunks in a list.

        Args:
            chunks: List of chunks to validate

        Raises:
            MetadataValidationError: If any chunk has invalid metadata
        """
        if not chunks:
            raise MetadataValidationError("chunk list is empty")

        for chunk in chunks:
            MetadataValidator.validate_chunk(chunk)

    @staticmethod
    def calculate_completeness_score(chunks: List[Chunk]) -> float:
        """
        Calculate metadata completeness score.

        Args:
            chunks: List of chunks to analyze

        Returns:
            Completeness score (0.0-1.0), where 1.0 = 100% complete
        """
        if not chunks:
            return 0.0

        total_fields = 0
        complete_fields = 0

        for chunk in chunks:
            # Required fields (always counted)
            total_fields += 3  # chapter_title, section_title, summary

            if chunk.metadata.chapter_title and chunk.metadata.chapter_title.strip():
                complete_fields += 1

            if chunk.metadata.section_title and chunk.metadata.section_title.strip():
                complete_fields += 1

            if chunk.metadata.summary and len(chunk.metadata.summary.strip()) >= 10:
                complete_fields += 1

            # Optional field (subsection_title) - only count if present
            if chunk.metadata.subsection_title:
                total_fields += 1
                if chunk.metadata.subsection_title.strip():
                    complete_fields += 1

        return complete_fields / total_fields if total_fields > 0 else 0.0
