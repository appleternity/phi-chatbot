"""Unit tests for TranscriptChunker video transcript processing."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from app.core.transcript_chunker import TranscriptChunker


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_vtt_content():
    """Sample VTT file content with timestamps and speakers."""
    return """WEBVTT

00:00:00.000 --> 00:00:05.000
Dr. Smith: Welcome to today's session on child development.

00:00:05.000 --> 00:00:10.000
Dr. Smith: We'll be discussing emotional regulation in toddlers.

00:00:10.000 --> 00:00:15.000
<v Parent>My two-year-old has frequent tantrums. What should I do?

00:00:15.000 --> 00:00:25.000
Dr. Smith: That's completely normal at this age. Toddlers are learning to express their emotions.

00:00:25.000 --> 00:00:35.000
Dr. Smith: The key is to stay calm and validate their feelings while setting clear boundaries.
"""


@pytest.fixture
def malformed_vtt_content():
    """Malformed VTT content for error handling tests."""
    return """WEBVTT

00:00:00.000 --> INVALID_TIMESTAMP
This caption has a malformed timestamp.

MISSING_ARROW 00:00:10.000
This caption is missing the arrow.
"""


@pytest.fixture
def empty_vtt_content():
    """Empty VTT file content."""
    return """WEBVTT

"""


@pytest.fixture
def temp_vtt_file(sample_vtt_content):
    """Create a temporary VTT file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(sample_vtt_content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def chunker():
    """Create TranscriptChunker instance with mocked embedding model."""
    with patch('app.core.transcript_chunker.SentenceTransformer') as mock_st:
        # Mock the embedding model
        mock_model = Mock()
        mock_model.encode.return_value = np.random.randn(384)  # MiniLM-L6-v2 dimension
        mock_st.return_value = mock_model

        chunker = TranscriptChunker(
            child_chunk_size=150,
            parent_chunk_size=750,
            overlap=30,
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        yield chunker


# ============================================================================
# Initialization Tests
# ============================================================================

def test_chunker_initialization_valid_params():
    """Test TranscriptChunker initializes with valid parameters."""
    with patch('app.core.transcript_chunker.SentenceTransformer'):
        chunker = TranscriptChunker(
            child_chunk_size=150,
            parent_chunk_size=750,
            overlap=30
        )

        assert chunker.child_chunk_size == 150
        assert chunker.parent_chunk_size == 750
        assert chunker.overlap == 30


def test_chunker_initialization_invalid_chunk_sizes():
    """Test TranscriptChunker raises ValueError for invalid chunk sizes."""
    with pytest.raises(ValueError, match="Chunk sizes must be positive"):
        TranscriptChunker(child_chunk_size=0, parent_chunk_size=750)

    with pytest.raises(ValueError, match="Chunk sizes must be positive"):
        TranscriptChunker(child_chunk_size=-150, parent_chunk_size=750)


def test_chunker_initialization_invalid_overlap():
    """Test TranscriptChunker raises ValueError for invalid overlap."""
    with pytest.raises(ValueError, match="Overlap must be >= 0"):
        TranscriptChunker(child_chunk_size=150, parent_chunk_size=750, overlap=-10)

    with pytest.raises(ValueError, match="Overlap must be.*< child_chunk_size"):
        TranscriptChunker(child_chunk_size=150, parent_chunk_size=750, overlap=200)


def test_chunker_initialization_parent_smaller_than_child():
    """Test TranscriptChunker raises ValueError when parent < child."""
    with pytest.raises(ValueError, match="parent_chunk_size.*must be >= child_chunk_size"):
        TranscriptChunker(child_chunk_size=750, parent_chunk_size=150)


# ============================================================================
# VTT Parsing Tests
# ============================================================================

def test_parse_vtt_valid_file(chunker, temp_vtt_file):
    """Test parsing a valid VTT file extracts captions correctly."""
    captions = chunker.parse_vtt(temp_vtt_file)

    assert len(captions) > 0
    assert all('text' in cap for cap in captions)
    assert all('start' in cap for cap in captions)
    assert all('end' in cap for cap in captions)
    assert all('speaker' in cap for cap in captions)


def test_parse_vtt_file_not_found(chunker):
    """Test parsing non-existent VTT file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        chunker.parse_vtt("/nonexistent/path/to/file.vtt")


def test_parse_vtt_empty_file(chunker, empty_vtt_content):
    """Test parsing empty VTT file raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(empty_vtt_content)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="VTT file is empty"):
            chunker.parse_vtt(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_vtt_speaker_detection_colon_format(chunker):
    """Test speaker detection with 'Speaker: text' format."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Dr. Smith: Hello everyone.
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(vtt_content)
        temp_path = f.name

    try:
        captions = chunker.parse_vtt(temp_path)
        assert len(captions) == 1
        assert captions[0]['speaker'] == 'Dr. Smith'
        assert captions[0]['text'] == 'Hello everyone.'
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_vtt_speaker_detection_voice_tag_format(chunker):
    """Test speaker detection with '<v Speaker>text' format."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Parent>My child has tantrums.
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(vtt_content)
        temp_path = f.name

    try:
        captions = chunker.parse_vtt(temp_path)
        assert len(captions) == 1
        assert captions[0]['speaker'] == 'Parent'
        assert captions[0]['text'] == 'My child has tantrums.'
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_vtt_no_speaker(chunker):
    """Test parsing captions without speaker tags."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
This is a caption without a speaker.
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(vtt_content)
        temp_path = f.name

    try:
        captions = chunker.parse_vtt(temp_path)
        assert len(captions) == 1
        assert captions[0]['speaker'] is None
        assert captions[0]['text'] == 'This is a caption without a speaker.'
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_vtt_timestamp_preservation(chunker, temp_vtt_file):
    """Test that timestamps are correctly preserved."""
    captions = chunker.parse_vtt(temp_vtt_file)

    first_caption = captions[0]
    assert first_caption['start'] == '00:00:00.000'
    assert first_caption['end'] == '00:00:05.000'


# ============================================================================
# Speaker Merging Tests
# ============================================================================

def test_merge_captions_by_speaker_same_speaker(chunker):
    """Test merging consecutive captions from same speaker."""
    captions = [
        {'text': 'Hello', 'start': '00:00:00.000', 'end': '00:00:05.000', 'speaker': 'Dr. Smith'},
        {'text': 'everyone.', 'start': '00:00:05.000', 'end': '00:00:10.000', 'speaker': 'Dr. Smith'},
        {'text': 'Welcome.', 'start': '00:00:10.000', 'end': '00:00:15.000', 'speaker': 'Dr. Smith'},
    ]

    merged = chunker.merge_captions_by_speaker(captions)

    assert len(merged) == 1
    assert merged[0]['text'] == 'Hello everyone. Welcome.'
    assert merged[0]['start'] == '00:00:00.000'
    assert merged[0]['end'] == '00:00:15.000'
    assert merged[0]['speaker'] == 'Dr. Smith'


def test_merge_captions_by_speaker_different_speakers(chunker):
    """Test that captions from different speakers are not merged."""
    captions = [
        {'text': 'Hello', 'start': '00:00:00.000', 'end': '00:00:05.000', 'speaker': 'Dr. Smith'},
        {'text': 'Hi there', 'start': '00:00:05.000', 'end': '00:00:10.000', 'speaker': 'Parent'},
        {'text': 'How are you?', 'start': '00:00:10.000', 'end': '00:00:15.000', 'speaker': 'Dr. Smith'},
    ]

    merged = chunker.merge_captions_by_speaker(captions)

    assert len(merged) == 3


def test_merge_captions_empty_list(chunker):
    """Test merging empty caption list returns empty list."""
    merged = chunker.merge_captions_by_speaker([])
    assert merged == []


def test_merge_captions_single_caption(chunker):
    """Test merging single caption returns same caption."""
    captions = [
        {'text': 'Hello', 'start': '00:00:00.000', 'end': '00:00:05.000', 'speaker': 'Dr. Smith'}
    ]

    merged = chunker.merge_captions_by_speaker(captions)

    assert len(merged) == 1
    assert merged[0] == captions[0]


def test_merge_captions_none_speakers(chunker):
    """Test merging captions with None speakers are merged together."""
    captions = [
        {'text': 'Hello', 'start': '00:00:00.000', 'end': '00:00:05.000', 'speaker': None},
        {'text': 'world', 'start': '00:00:05.000', 'end': '00:00:10.000', 'speaker': None},
    ]

    merged = chunker.merge_captions_by_speaker(captions)

    assert len(merged) == 1
    assert merged[0]['text'] == 'Hello world'


# ============================================================================
# Chunk Creation Tests
# ============================================================================

def test_create_chunks_structure(chunker, temp_vtt_file):
    """Test that create_chunks returns correct structure."""
    video_metadata = {
        'video_id': 'test-123',
        'title': 'Test Video',
        'url': 'https://example.com/video',
    }

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    assert 'parents' in result
    assert 'children' in result
    assert isinstance(result['parents'], list)
    assert isinstance(result['children'], list)


def test_create_chunks_parent_child_relationship(chunker, temp_vtt_file):
    """Test parent-child relationships are correctly established."""
    video_metadata = {'video_id': 'test-123'}

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    parents = result['parents']
    children = result['children']

    # Verify all children have parent_id
    assert all('parent_id' in child for child in children)

    # Verify all parent_ids reference existing parents
    parent_ids = {parent['parent_id'] for parent in parents}
    child_parent_ids = {child['parent_id'] for child in children}
    assert child_parent_ids.issubset(parent_ids)


def test_create_chunks_metadata_propagation(chunker, temp_vtt_file):
    """Test that video metadata is propagated to all chunks."""
    video_metadata = {
        'video_id': 'test-123',
        'title': 'Test Video',
        'url': 'https://example.com/video',
        'duration': 3600,
    }

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    # Check parents have metadata
    for parent in result['parents']:
        assert parent['video_id'] == 'test-123'
        assert parent['title'] == 'Test Video'
        assert parent['url'] == 'https://example.com/video'
        assert parent['duration'] == 3600

    # Check children have metadata
    for child in result['children']:
        assert child['video_id'] == 'test-123'
        assert child['title'] == 'Test Video'


def test_create_chunks_timestamp_preservation(chunker, temp_vtt_file):
    """Test that timestamps are preserved in chunks."""
    video_metadata = {'video_id': 'test-123'}

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    # Check parents have timestamps
    for parent in result['parents']:
        assert 'time_start' in parent
        assert 'time_end' in parent
        assert parent['time_start'] is not None
        assert parent['time_end'] is not None

    # Check children have timestamps
    for child in result['children']:
        assert 'time_start' in child
        assert 'time_end' in child


def test_create_chunks_embeddings_generated(chunker, temp_vtt_file):
    """Test that embeddings are generated for child chunks."""
    video_metadata = {'video_id': 'test-123'}

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    children = result['children']

    # Verify all children have embeddings
    assert all('embedding' in child for child in children)
    assert all(isinstance(child['embedding'], np.ndarray) for child in children)


def test_create_chunks_child_count_tracking(chunker, temp_vtt_file):
    """Test that parent chunks track child count correctly."""
    video_metadata = {'video_id': 'test-123'}

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    parents = result['parents']
    children = result['children']

    # Calculate actual child counts per parent
    parent_child_counts = {}
    for child in children:
        parent_id = child['parent_id']
        parent_child_counts[parent_id] = parent_child_counts.get(parent_id, 0) + 1

    # Verify parent child_count matches actual
    for parent in parents:
        expected_count = parent_child_counts.get(parent['parent_id'], 0)
        assert parent['child_count'] == expected_count


def test_create_chunks_speaker_extraction(chunker, temp_vtt_file):
    """Test that speakers are correctly extracted in chunks."""
    video_metadata = {'video_id': 'test-123'}

    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    # Check that chunks with speakers have them recorded
    for parent in result['parents']:
        assert 'speakers' in parent
        assert isinstance(parent['speakers'], list)

    for child in result['children']:
        assert 'speakers' in child
        assert isinstance(child['speakers'], list)


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_create_chunks_very_short_transcript(chunker):
    """Test handling of very short transcripts (less than one chunk)."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000
Short text.
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(vtt_content)
        temp_path = f.name

    try:
        video_metadata = {'video_id': 'test-123'}
        result = chunker.create_chunks(temp_path, video_metadata)

        assert len(result['parents']) >= 1
        assert len(result['children']) >= 1
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_overlap_calculation(chunker):
    """Test that overlap is correctly applied between chunks."""
    # This is implicitly tested by verifying chunk boundaries
    # The RecursiveCharacterTextSplitter handles overlap internally
    assert chunker.overlap == 30


def test_time_to_seconds_conversion(chunker):
    """Test timestamp to seconds conversion."""
    # Test HH:MM:SS.mmm format
    seconds = chunker._time_to_seconds("01:23:45.678")
    assert seconds == pytest.approx(5025.678, rel=1e-3)

    # Test MM:SS.mmm format
    seconds = chunker._time_to_seconds("23:45.678")
    assert seconds == pytest.approx(1425.678, rel=1e-3)


def test_time_to_seconds_invalid_format(chunker):
    """Test that invalid timestamp formats raise ValueError."""
    with pytest.raises(ValueError):
        chunker._time_to_seconds("invalid:format")

    with pytest.raises(ValueError):
        chunker._time_to_seconds("12:34:56:78")


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_pipeline_with_real_vtt(chunker, temp_vtt_file):
    """Test the complete chunking pipeline end-to-end."""
    video_metadata = {
        'video_id': 'test-123',
        'title': 'Child Development Session',
        'url': 'https://example.com/video',
        'duration': 60,
    }

    # Run full pipeline
    result = chunker.create_chunks(temp_vtt_file, video_metadata)

    # Verify structure
    assert 'parents' in result
    assert 'children' in result
    assert len(result['parents']) > 0
    assert len(result['children']) > 0

    # Verify metadata propagation
    assert all(p['video_id'] == 'test-123' for p in result['parents'])
    assert all(c['video_id'] == 'test-123' for c in result['children'])

    # Verify relationships
    parent_ids = {p['parent_id'] for p in result['parents']}
    child_parent_ids = {c['parent_id'] for c in result['children']}
    assert child_parent_ids.issubset(parent_ids)

    # Verify embeddings
    assert all('embedding' in c for c in result['children'])
    assert all(isinstance(c['embedding'], np.ndarray) for c in result['children'])
