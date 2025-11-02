"""
Unit tests for chunking utility components.

Tests the utility classes: TextAligner, MetadataValidator, and TokenCounter.
"""

import pytest

from src.chunking.models import (
    Chunk,
    ChunkMetadata,
    ProcessingMetadata,
    TextCoverageError,
    MetadataValidationError,
    TokenCounter,
    SectionV2,
)
from src.chunking.text_aligner import TextAligner
from src.chunking.metadata_validator import MetadataValidator


# ============================================================================
# TextAligner Tests
# ============================================================================


class TestTextAligner:
    """Test TextAligner utility"""

    def test_verify_coverage_perfect_match(self):
        """Test TextAligner with perfect text coverage"""
        # Arrange
        original_text = "This is a test document with multiple sections."

        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nThis is a test",
                original_text="This is a test",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 1",
                    subsection_title=None,
                    summary="Test summary for first chunk"
                ),
                token_count=50,
                character_span=(0, 14),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            ),
            Chunk(
                chunk_id="chunk_002",
                source_document="test_doc",
                chunk_text="Prefix\n\n document with multiple sections.",
                original_text=" document with multiple sections.",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 2",
                    subsection_title=None,
                    summary="Test summary for second chunk"
                ),
                token_count=50,
                character_span=(14, 48),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act
        coverage_ratio, missing_segments = TextAligner.verify_coverage(
            original_text=original_text,
            chunks=chunks,
            min_coverage=0.99
        )

        # Assert
        assert coverage_ratio >= 0.99
        assert len(missing_segments) == 0

    def test_verify_coverage_with_gaps(self):
        """Test TextAligner detects missing text segments"""
        # Arrange
        original_text = "This is a test document with multiple sections."

        # Only cover first part, missing the end
        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nThis is a test",
                original_text="This is a test",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 1",
                    subsection_title=None,
                    summary="Test summary for chunk"
                ),
                token_count=50,
                character_span=(0, 14),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act & Assert - Should raise TextCoverageError
        with pytest.raises(TextCoverageError) as exc_info:
            TextAligner.verify_coverage(
                original_text=original_text,
                chunks=chunks,
                min_coverage=0.99
            )

        # Verify error details
        error = exc_info.value
        assert error.coverage_ratio < 0.99
        assert len(error.missing_segments) > 0

    def test_verify_coverage_custom_threshold(self):
        """Test TextAligner with custom coverage threshold"""
        # Arrange
        original_text = "This is a test document."

        # Partial coverage
        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nThis is a test",
                original_text="This is a test",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 1",
                    subsection_title=None,
                    summary="Test summary for chunk"
                ),
                token_count=50,
                character_span=(0, 14),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act & Assert - Lower threshold should pass
        coverage_ratio, missing_segments = TextAligner.verify_coverage(
            original_text=original_text,
            chunks=chunks,
            min_coverage=0.50  # 50% threshold
        )

        assert coverage_ratio >= 0.50

        # Act & Assert - Higher threshold should fail
        with pytest.raises(TextCoverageError):
            TextAligner.verify_coverage(
                original_text=original_text,
                chunks=chunks,
                min_coverage=0.95  # 95% threshold
            )

    def test_check_completeness_success(self):
        """Test TextAligner.check_completeness() with complete coverage"""
        # Arrange
        original_text = "This is a complete test."

        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nThis is a complete test.",
                original_text="This is a complete test.",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 1",
                    subsection_title=None,
                    summary="Test summary for chunk"
                ),
                token_count=50,
                character_span=(0, 24),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act
        is_complete = TextAligner.check_completeness(original_text, chunks)

        # Assert
        assert is_complete is True

    def test_check_completeness_failure(self):
        """Test TextAligner.check_completeness() with incomplete coverage"""
        # Arrange
        original_text = "This is an incomplete test document."

        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nThis is",
                original_text="This is",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter 1",
                    section_title="Section 1",
                    subsection_title=None,
                    summary="Test summary for chunk"
                ),
                token_count=50,
                character_span=(0, 7),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act
        is_complete = TextAligner.check_completeness(original_text, chunks)

        # Assert
        assert is_complete is False


# ============================================================================
# MetadataValidator Tests
# ============================================================================


class TestMetadataValidator:
    """Test MetadataValidator utility"""

    def test_validate_metadata_valid(self):
        """Test MetadataValidator with valid metadata"""
        # Arrange
        valid_metadata = ChunkMetadata(
            chapter_title="Introduction to Testing",
            section_title="Why Test?",
            subsection_title="Benefits",
            summary="This section discusses the key benefits of software testing"
        )

        # Act & Assert - Should not raise
        MetadataValidator.validate_metadata(valid_metadata)

    def test_validate_metadata_no_subsection(self):
        """Test MetadataValidator with no subsection (valid case)"""
        # Arrange
        metadata = ChunkMetadata(
            chapter_title="Introduction",
            section_title="Overview",
            subsection_title=None,  # Optional field
            summary="A comprehensive overview of the testing process"
        )

        # Act & Assert - Should not raise
        MetadataValidator.validate_metadata(metadata)

    def test_validate_metadata_placeholder_chapter(self):
        """Test MetadataValidator rejects placeholder chapter title"""
        # Arrange
        invalid_metadata = ChunkMetadata(
            chapter_title="TODO",  # Placeholder
            section_title="Section",
            subsection_title=None,
            summary="Some meaningful summary here"
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="chapter_title contains placeholder"):
            MetadataValidator.validate_metadata(invalid_metadata)

    def test_validate_metadata_placeholder_section(self):
        """Test MetadataValidator rejects placeholder section title"""
        # Arrange
        invalid_metadata = ChunkMetadata(
            chapter_title="Chapter",
            section_title="N/A",  # Placeholder
            subsection_title=None,
            summary="Some meaningful summary here"
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="section_title contains placeholder"):
            MetadataValidator.validate_metadata(invalid_metadata)

    def test_validate_metadata_placeholder_summary(self):
        """Test MetadataValidator rejects placeholder summary"""
        # Arrange
        invalid_metadata = ChunkMetadata(
            chapter_title="Chapter",
            section_title="Section",
            subsection_title=None,
            summary="summary"  # Placeholder
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="summary contains placeholder"):
            MetadataValidator.validate_metadata(invalid_metadata)

    def test_validate_metadata_summary_too_short(self):
        """Test MetadataValidator rejects too-short summary"""
        # Arrange
        invalid_metadata = ChunkMetadata(
            chapter_title="Chapter",
            section_title="Section",
            subsection_title=None,
            summary="Short"  # Less than 10 chars
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="summary too short"):
            MetadataValidator.validate_metadata(invalid_metadata)

    def test_validate_metadata_summary_too_long(self):
        """Test MetadataValidator rejects too-long summary"""
        # Arrange
        long_summary = "A" * 501  # Over 500 chars
        invalid_metadata = ChunkMetadata(
            chapter_title="Chapter",
            section_title="Section",
            subsection_title=None,
            summary=long_summary
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="summary too long"):
            MetadataValidator.validate_metadata(invalid_metadata)

    def test_validate_chunk_success(self):
        """Test MetadataValidator.validate_chunk() with valid chunk"""
        # Arrange
        valid_chunk = Chunk(
            chunk_id="chunk_001",
            source_document="test_doc",
            chunk_text="Prefix\n\nTest content",
            original_text="Test content",
            contextual_prefix="Prefix",
            metadata=ChunkMetadata(
                chapter_title="Chapter",
                section_title="Section",
                subsection_title=None,
                summary="A meaningful summary of the content"
            ),
            token_count=500,
            character_span=(0, 12),
            processing_metadata=ProcessingMetadata(
                phase_1_model="openai/gpt-4o",
                phase_2_model="openai/gpt-4o",
                phase_3_model="google/gemini-2.0-flash-exp"
            )
        )

        # Act & Assert - Should not raise
        MetadataValidator.validate_chunk(valid_chunk)

    def test_validate_chunk_invalid_token_count_zero(self):
        """Test MetadataValidator.validate_chunk() rejects zero token count"""
        # Arrange
        invalid_chunk = Chunk(
            chunk_id="chunk_001",
            source_document="test_doc",
            chunk_text="Prefix\n\nTest content",
            original_text="Test content",
            contextual_prefix="Prefix",
            metadata=ChunkMetadata(
                chapter_title="Chapter",
                section_title="Section",
                subsection_title=None,
                summary="A meaningful summary"
            ),
            token_count=0,  # Invalid
            character_span=(0, 12),
            processing_metadata=ProcessingMetadata(
                phase_1_model="openai/gpt-4o",
                phase_2_model="openai/gpt-4o",
                phase_3_model="google/gemini-2.0-flash-exp"
            )
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="invalid token_count"):
            MetadataValidator.validate_chunk(invalid_chunk)

    def test_validate_chunk_exceeds_token_limit(self):
        """Test MetadataValidator.validate_chunk() rejects chunks over limit"""
        # Arrange
        invalid_chunk = Chunk(
            chunk_id="chunk_001",
            source_document="test_doc",
            chunk_text="Prefix\n\nTest content",
            original_text="Test content",
            contextual_prefix="Prefix",
            metadata=ChunkMetadata(
                chapter_title="Chapter",
                section_title="Section",
                subsection_title=None,
                summary="A meaningful summary"
            ),
            token_count=1001,  # Over 1000 limit
            character_span=(0, 12),
            processing_metadata=ProcessingMetadata(
                phase_1_model="openai/gpt-4o",
                phase_2_model="openai/gpt-4o",
                phase_3_model="google/gemini-2.0-flash-exp"
            )
        )

        # Act & Assert
        with pytest.raises(MetadataValidationError, match="exceeds maximum token count"):
            MetadataValidator.validate_chunk(invalid_chunk)

    def test_validate_chunks_empty_list(self):
        """Test MetadataValidator.validate_chunks() rejects empty list"""
        # Act & Assert
        with pytest.raises(MetadataValidationError, match="chunk list is empty"):
            MetadataValidator.validate_chunks([])

    def test_validate_chunks_all_valid(self):
        """Test MetadataValidator.validate_chunks() with all valid chunks"""
        # Arrange
        chunks = [
            Chunk(
                chunk_id=f"chunk_{i:03d}",
                source_document="test_doc",
                chunk_text=f"Prefix\n\nContent {i}",
                original_text=f"Content {i}",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter",
                    section_title=f"Section {i}",
                    subsection_title=None,
                    summary=f"Summary for chunk {i} with meaningful content"
                ),
                token_count=100 + i * 10,
                character_span=(i * 20, (i + 1) * 20),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
            for i in range(1, 4)
        ]

        # Act & Assert - Should not raise
        MetadataValidator.validate_chunks(chunks)

    def test_calculate_completeness_score_perfect(self):
        """Test MetadataValidator.calculate_completeness_score() with 100% complete"""
        # Arrange
        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nContent",
                original_text="Content",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter",
                    section_title="Section",
                    subsection_title="Subsection",
                    summary="Complete meaningful summary"
                ),
                token_count=100,
                character_span=(0, 7),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act
        score = MetadataValidator.calculate_completeness_score(chunks)

        # Assert
        assert score == 1.0  # All fields present

    def test_calculate_completeness_score_partial(self):
        """Test MetadataValidator.calculate_completeness_score() with partial data"""
        # Arrange
        chunks = [
            Chunk(
                chunk_id="chunk_001",
                source_document="test_doc",
                chunk_text="Prefix\n\nContent",
                original_text="Content",
                contextual_prefix="Prefix",
                metadata=ChunkMetadata(
                    chapter_title="Chapter",
                    section_title="Section",
                    subsection_title=None,  # Missing optional field
                    summary="Meaningful summary"
                ),
                token_count=100,
                character_span=(0, 7),
                processing_metadata=ProcessingMetadata(
                    phase_1_model="openai/gpt-4o",
                    phase_2_model="openai/gpt-4o",
                    phase_3_model="google/gemini-2.0-flash-exp"
                )
            )
        ]

        # Act
        score = MetadataValidator.calculate_completeness_score(chunks)

        # Assert - 3 required fields all present = 100%
        assert score == 1.0  # subsection_title is optional


# ============================================================================
# TokenCounter Tests
# ============================================================================


class TestTokenCounter:
    """Test TokenCounter utility"""

    def test_count_tokens_basic(self):
        """Test TokenCounter.count_tokens() with basic text"""
        # Arrange
        counter = TokenCounter()
        text = "This is a simple test."
        model = "openai/gpt-4o"

        # Act
        token_count = counter.count_tokens(text, model)

        # Assert
        assert token_count > 0
        # Rough approximation: should be close to word count
        word_count = len(text.split())
        assert token_count >= word_count * 0.5  # At least half the word count
        assert token_count <= word_count * 2    # At most double the word count

    def test_count_tokens_empty_string(self):
        """Test TokenCounter.count_tokens() with empty string"""
        # Arrange
        counter = TokenCounter()
        text = ""
        model = "openai/gpt-4o"

        # Act
        token_count = counter.count_tokens(text, model)

        # Assert
        assert token_count == 0

    def test_count_tokens_whitespace_only(self):
        """Test TokenCounter.count_tokens() with whitespace"""
        # Arrange
        counter = TokenCounter()
        text = "   \n\n   "
        model = "openai/gpt-4o"

        # Act
        token_count = counter.count_tokens(text, model)

        # Assert
        assert token_count >= 0  # Should be minimal

    def test_count_tokens_long_text(self):
        """Test TokenCounter.count_tokens() with longer text"""
        # Arrange
        counter = TokenCounter()
        text = " ".join(["word"] * 500)  # 500 words
        model = "openai/gpt-4o"

        # Act
        token_count = counter.count_tokens(text, model)

        # Assert
        assert token_count > 0
        # Should be in reasonable range (250-1000 tokens)
        assert 250 <= token_count <= 1000

    def test_count_tokens_different_models(self):
        """Test TokenCounter.count_tokens() with different models"""
        # Arrange
        counter = TokenCounter()
        text = "This is a test sentence."

        models = [
            "openai/gpt-4o",
            "google/gemini-2.0-flash-exp",
            "anthropic/claude-3-5-sonnet-20241022"
        ]

        # Act - Count tokens for each model
        counts = {model: counter.count_tokens(text, model) for model in models}

        # Assert - All should give reasonable counts
        for model, count in counts.items():
            assert count > 0, f"Model {model} returned invalid count: {count}"
            # Counts may vary slightly between models, but should be in similar range
            assert 2 <= count <= 20, f"Model {model} count out of range: {count}"


# ============================================================================
# SectionV2 Tests (Title-Only Sections)
# ============================================================================


class TestSectionV2:
    """Test SectionV2 model with title-only sections (empty start_words/end_words)"""

    def test_section_v2_with_content(self):
        """Test SectionV2 with normal content (non-empty start_words/end_words)"""
        # Arrange & Act
        section = SectionV2(
            title="Introduction to Testing",
            level=1,
            parent_section="ROOT",
            summary="Overview of software testing fundamentals",
            start_words="Software testing is critical",
            end_words="quality and reliability in production"
        )

        # Assert
        assert section.title == "Introduction to Testing"
        assert section.start_words == "Software testing is critical"
        assert section.end_words == "quality and reliability in production"

    def test_section_v2_title_only_empty_fields(self):
        """Test SectionV2 with title-only section (empty start_words/end_words)"""
        # Arrange & Act
        section = SectionV2(
            title="Safety and Tolerability",
            level=1,
            parent_section="ROOT",
            summary="Summarizes the safety profile of amphetamine",
            start_words="",  # Empty for title-only
            end_words=""     # Empty for title-only
        )

        # Assert
        assert section.title == "Safety and Tolerability"
        assert section.start_words == ""
        assert section.end_words == ""
        assert section.summary == "Summarizes the safety profile of amphetamine"

    def test_section_v2_title_only_default_values(self):
        """Test SectionV2 with title-only section (omitting start_words/end_words)"""
        # Arrange & Act - Omit start_words/end_words entirely, should default to ""
        section = SectionV2(
            title="Architecture Overview",
            level=1,
            parent_section=None,
            summary="High-level architectural patterns and design principles"
        )

        # Assert
        assert section.title == "Architecture Overview"
        assert section.start_words == ""  # Should default to empty
        assert section.end_words == ""    # Should default to empty

    def test_section_v2_mixed_sections(self):
        """Test SectionV2 with mix of content and title-only sections"""
        # Arrange
        sections = [
            SectionV2(
                title="Chapter 1",
                level=1,
                parent_section="ROOT",
                summary="Chapter overview",
                start_words="",  # Title-only
                end_words=""
            ),
            SectionV2(
                title="Section 1.1",
                level=2,
                parent_section="Chapter 1",
                summary="Actual content section",
                start_words="This section covers",
                end_words="important details"
            ),
            SectionV2(
                title="Section 1.2",
                level=2,
                parent_section="Chapter 1",
                summary="Another content section",
                start_words="We will discuss",
                end_words="in the next section"
            )
        ]

        # Assert
        assert sections[0].start_words == ""  # Title-only
        assert sections[1].start_words != ""  # Has content
        assert sections[2].start_words != ""  # Has content

    def test_section_v2_empty_sentinel_parsing(self):
        """Test that [EMPTY] sentinel is properly converted to empty string"""
        # This simulates what the parser does when it encounters [EMPTY]
        # In the parser: start_words_clean = "" if start_words.strip() == "[EMPTY]" else start_words.strip()

        # Test the conversion logic
        test_value_empty = "[EMPTY]"
        test_value_content = "Some content here"

        # Simulate parser conversion
        converted_empty = "" if test_value_empty.strip() == "[EMPTY]" else test_value_empty.strip()
        converted_content = "" if test_value_content.strip() == "[EMPTY]" else test_value_content.strip()

        # Assert conversions
        assert converted_empty == ""
        assert converted_content == "Some content here"

        # Test creating section with converted values
        section = SectionV2(
            title="Test Section",
            level=1,
            parent_section="ROOT",
            summary="Test summary for empty sentinel validation",
            start_words=converted_empty,
            end_words=converted_empty
        )

        assert section.start_words == ""
        assert section.end_words == ""
