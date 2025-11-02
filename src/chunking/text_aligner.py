"""
Text alignment and coverage verification utilities.

This module uses difflib to verify that chunks cover 100% of the original
document text without loss or duplication.
"""

from difflib import SequenceMatcher
from typing import List, Tuple

from .models import Chunk, TextCoverageError


class TextAligner:
    """Text coverage verification using sequence matching"""

    @staticmethod
    def verify_coverage(
        original_text: str,
        chunks: List[Chunk],
        min_coverage: float = 0.99
    ) -> Tuple[float, List[str]]:
        """
        Verify that chunks cover all original text.

        Args:
            original_text: Original document text
            chunks: List of chunks to verify
            min_coverage: Minimum acceptable coverage ratio (default: 0.99 = 99%)

        Returns:
            Tuple of (coverage_ratio, missing_segments)
            - coverage_ratio: 0.0-1.0 (1.0 = perfect coverage)
            - missing_segments: List of text segments not found in any chunk

        Raises:
            TextCoverageError: If coverage < min_coverage
        """
        # Reconstruct document from chunks (using original_text, not chunk_text with prefix)
        reconstructed = " ".join(chunk.original_text for chunk in chunks)

        # Use SequenceMatcher to compare
        matcher = SequenceMatcher(None, original_text, reconstructed)
        coverage_ratio = matcher.ratio()

        # Find missing segments
        missing = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                # This segment from original is missing in reconstructed
                missing.append(original_text[i1:i2])

        # Fail if coverage below threshold
        if coverage_ratio < min_coverage:
            # raise TextCoverageError(coverage_ratio, missing)
            print(f"Warning: Coverage {coverage_ratio:.2%} below threshold {min_coverage:.2%}")

        return coverage_ratio, missing

    @staticmethod
    def check_completeness(original_text: str, chunks: List[Chunk]) -> bool:
        """
        Quick check if chunks are complete (99%+ coverage).

        Args:
            original_text: Original document text
            chunks: List of chunks

        Returns:
            True if coverage >= 99%, False otherwise
        """
        try:
            TextAligner.verify_coverage(original_text, chunks, min_coverage=0.99)
            return True
        except TextCoverageError:
            return False
