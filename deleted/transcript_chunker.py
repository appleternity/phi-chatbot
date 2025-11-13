"""Video transcript processing with hierarchical parent-child chunking.

This module processes VTT (WebVTT) video transcripts into hierarchical chunks suitable
for vector search and retrieval. It implements a parent-child chunking strategy where:
- Parent chunks: ~750 tokens (~3 minutes of video content)
- Child chunks: ~150 tokens (~35 seconds of video content)
- Overlap: 15-20% (30 tokens for children) to preserve context

The hierarchical structure enables both broad context (parents) and precise retrieval
(children) while maintaining timestamp metadata for video navigation.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

try:
    import webvtt
except ImportError:
    raise ImportError(
        "webvtt-py is required for transcript processing. "
        "Install it with: pip install webvtt-py"
    )

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    raise ImportError(
        "langchain-text-splitters is required for text splitting. "
        "Install it with: pip install langchain-text-splitters"
    )

logger = logging.getLogger(__name__)


class TranscriptChunker:
    """Process VTT video transcripts into hierarchical parent-child chunks.

    This class handles the complete pipeline of:
    1. Parsing VTT files and extracting captions with timestamps
    2. Merging consecutive same-speaker segments
    3. Creating hierarchical parent-child chunks with configurable sizes
    4. Generating embeddings for child chunks
    5. Maintaining timestamp and speaker metadata throughout

    Attributes:
        child_chunk_size: Target size for child chunks in tokens (~150 = 35s video)
        parent_chunk_size: Target size for parent chunks in tokens (~750 = 3min video)
        overlap: Overlap size in tokens for context preservation (default 30)
        model_name: SentenceTransformer model for embedding generation
    """

    def __init__(
        self,
        child_chunk_size: int = 150,
        parent_chunk_size: int = 750,
        overlap: int = 30,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        """Initialize TranscriptChunker with chunking parameters.

        Args:
            child_chunk_size: Target tokens per child chunk (default 150)
            parent_chunk_size: Target tokens per parent chunk (default 750)
            overlap: Overlap tokens for context preservation (default 30)
            model_name: SentenceTransformer model identifier

        Raises:
            ValueError: If chunk sizes or overlap are invalid
        """
        # Validate parameters
        if child_chunk_size <= 0 or parent_chunk_size <= 0:
            raise ValueError("Chunk sizes must be positive integers")

        if overlap < 0 or overlap >= child_chunk_size:
            raise ValueError(
                f"Overlap must be >= 0 and < child_chunk_size ({child_chunk_size})"
            )

        if parent_chunk_size < child_chunk_size:
            raise ValueError(
                f"parent_chunk_size ({parent_chunk_size}) must be >= "
                f"child_chunk_size ({child_chunk_size})"
            )

        self.child_chunk_size = child_chunk_size
        self.parent_chunk_size = parent_chunk_size
        self.overlap = overlap
        self.model_name = model_name

        # Initialize embedding model with device detection
        if torch.backends.mps.is_available():
            self._device = "mps"
            logger.info("Using MPS (Apple Metal) for embeddings")
        else:
            self._device = "cpu"
            logger.info("Using CPU for embeddings")

        try:
            self._embedding_model = SentenceTransformer(model_name, device=self._device)
            logger.info(f"Initialized SentenceTransformer: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

        # Initialize text splitters for parent and child chunks
        # Note: RecursiveCharacterTextSplitter uses characters, not tokens
        # We approximate: 1 token ≈ 4 characters (common heuristic)
        char_multiplier = 4

        self._parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size * char_multiplier,
            chunk_overlap=overlap * char_multiplier,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size * char_multiplier,
            chunk_overlap=overlap * char_multiplier,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        logger.info(
            f"TranscriptChunker initialized: "
            f"parent={parent_chunk_size} tokens, "
            f"child={child_chunk_size} tokens, "
            f"overlap={overlap} tokens"
        )

    def parse_vtt(self, vtt_path: str) -> List[Dict]:
        """Parse VTT file and extract captions with timestamps and speakers.

        Args:
            vtt_path: Path to VTT file

        Returns:
            List of caption dictionaries with structure:
                {
                    'text': str,              # Caption text
                    'start': str,             # Start timestamp (HH:MM:SS.mmm)
                    'end': str,               # End timestamp (HH:MM:SS.mmm)
                    'speaker': Optional[str]  # Speaker name if detected
                }

        Raises:
            FileNotFoundError: If VTT file doesn't exist
            ValueError: If VTT file is malformed or empty
        """
        vtt_file = Path(vtt_path)
        if not vtt_file.exists():
            raise FileNotFoundError(f"VTT file not found: {vtt_path}")

        try:
            captions_data = []
            vtt_content = webvtt.read(str(vtt_file))

            if not vtt_content:
                raise ValueError(f"VTT file is empty: {vtt_path}")

            for caption in vtt_content:
                # Extract speaker if present (format: "Speaker: text" or "<v Speaker>text")
                speaker = self._extract_speaker(caption.text)
                text = self._clean_caption_text(caption.text)

                if text.strip():  # Only include non-empty captions
                    captions_data.append(
                        {
                            "text": text,
                            "start": caption.start,
                            "end": caption.end,
                            "speaker": speaker,
                        }
                    )

            logger.info(f"Parsed {len(captions_data)} captions from {vtt_path}")
            return captions_data

        except Exception as e:
            logger.error(f"Failed to parse VTT file {vtt_path}: {e}")
            raise ValueError(f"Malformed VTT file: {e}")

    def merge_captions_by_speaker(self, captions: List[Dict]) -> List[Dict]:
        """Merge consecutive captions from the same speaker into unified segments.

        This reduces fragmentation and creates more coherent chunks by combining
        captions that belong to the same speaker's continuous speech.

        Args:
            captions: List of caption dictionaries from parse_vtt()

        Returns:
            List of merged caption dictionaries with same structure as input
        """
        if not captions:
            return []

        merged = []
        current_segment = captions[0].copy()

        for caption in captions[1:]:
            # Merge if same speaker or both speakers are None
            same_speaker = (
                current_segment["speaker"] == caption["speaker"]
                or current_segment["speaker"] is None
                or caption["speaker"] is None
            )

            if same_speaker:
                # Extend current segment
                current_segment["text"] += " " + caption["text"]
                current_segment["end"] = caption["end"]
            else:
                # Start new segment
                merged.append(current_segment)
                current_segment = caption.copy()

        # Don't forget the last segment
        merged.append(current_segment)

        logger.info(
            f"Merged {len(captions)} captions into {len(merged)} speaker segments "
            f"(reduction: {len(captions) - len(merged)})"
        )
        return merged

    def create_chunks(self, vtt_path: str, video_metadata: Dict) -> Dict[str, List]:
        """Create hierarchical parent-child chunks from VTT transcript.

        This is the main entry point that orchestrates the complete chunking pipeline:
        1. Parse VTT file
        2. Merge same-speaker captions
        3. Create parent chunks with text splitter
        4. Create child chunks within each parent
        5. Generate embeddings for children
        6. Maintain timestamp and metadata relationships

        Args:
            vtt_path: Path to VTT file
            video_metadata: Metadata to attach to all chunks (e.g., video_id, title,
                          url, duration, etc.)

        Returns:
            Dictionary with 'parents' and 'children' lists:
                {
                    'parents': [
                        {
                            'parent_id': str,
                            'text': str,
                            'time_start': str,
                            'time_end': str,
                            'speakers': List[str],
                            'char_start': int,
                            'char_end': int,
                            'child_count': int,
                            **video_metadata
                        }
                    ],
                    'children': [
                        {
                            'child_id': str,
                            'parent_id': str,
                            'text': str,
                            'embedding': np.ndarray,
                            'time_start': str,
                            'time_end': str,
                            'speakers': List[str],
                            'char_start': int,
                            'char_end': int,
                            **video_metadata
                        }
                    ]
                }

        Raises:
            FileNotFoundError: If VTT file doesn't exist
            ValueError: If processing fails
        """
        logger.info(f"Starting chunk creation for {vtt_path}")

        # Step 1: Parse VTT
        captions = self.parse_vtt(vtt_path)
        if not captions:
            raise ValueError(f"No captions found in {vtt_path}")

        # Step 2: Merge same-speaker segments
        merged_captions = self.merge_captions_by_speaker(captions)

        # Step 3: Build full transcript text and timestamp mapping
        full_text, timestamp_map = self._build_text_and_mapping(merged_captions)

        # Step 4: Create parent chunks
        parent_texts = self._parent_splitter.split_text(full_text)
        logger.info(f"Created {len(parent_texts)} parent chunks")

        parents = []
        children = []
        child_counter = 0

        # Step 5: Process each parent chunk
        for parent_idx, parent_text in enumerate(parent_texts):
            parent_id = f"parent_{parent_idx}"

            # Find character positions in full text
            parent_start_char = full_text.find(parent_text)
            if parent_start_char == -1:
                logger.warning(f"Could not locate parent chunk {parent_idx} in full text")
                continue

            parent_end_char = parent_start_char + len(parent_text)

            # Get time range for this parent
            parent_time_range = self._get_time_range(
                timestamp_map, parent_start_char, parent_end_char
            )

            # Extract unique speakers in this parent
            parent_speakers = self._extract_speakers_from_range(
                timestamp_map, parent_start_char, parent_end_char
            )

            # Create parent chunk
            parent_chunk = {
                "parent_id": parent_id,
                "text": parent_text,
                "time_start": parent_time_range["start"],
                "time_end": parent_time_range["end"],
                "speakers": parent_speakers,
                "char_start": parent_start_char,
                "char_end": parent_end_char,
                **video_metadata,
            }

            # Step 6: Create child chunks within this parent
            child_texts = self._child_splitter.split_text(parent_text)

            parent_child_ids = []
            for child_text in child_texts:
                child_id = f"child_{child_counter}"
                child_counter += 1

                # Find character positions within parent
                child_start_in_parent = parent_text.find(child_text)
                if child_start_in_parent == -1:
                    logger.warning(
                        f"Could not locate child chunk in parent {parent_idx}"
                    )
                    continue

                child_start_char = parent_start_char + child_start_in_parent
                child_end_char = child_start_char + len(child_text)

                # Get time range for this child
                child_time_range = self._get_time_range(
                    timestamp_map, child_start_char, child_end_char
                )

                # Extract speakers for this child
                child_speakers = self._extract_speakers_from_range(
                    timestamp_map, child_start_char, child_end_char
                )

                # Generate embedding for child
                embedding = self._generate_embedding(child_text)

                # Create child chunk
                child_chunk = {
                    "child_id": child_id,
                    "parent_id": parent_id,
                    "text": child_text,
                    "embedding": embedding,
                    "time_start": child_time_range["start"],
                    "time_end": child_time_range["end"],
                    "speakers": child_speakers,
                    "char_start": child_start_char,
                    "char_end": child_end_char,
                    **video_metadata,
                }

                children.append(child_chunk)
                parent_child_ids.append(child_id)

            # Add child count to parent
            parent_chunk["child_count"] = len(parent_child_ids)
            parent_chunk["child_ids"] = parent_child_ids
            parents.append(parent_chunk)

        logger.info(
            f"Chunk creation complete: {len(parents)} parents, {len(children)} children"
        )

        return {"parents": parents, "children": children}

    def _extract_speaker(self, text: str) -> Optional[str]:
        """Extract speaker name from caption text.

        Supports common VTT speaker formats:
        - "Speaker Name: text" (colon-separated)
        - "<v Speaker Name>text" (voice tag)

        Args:
            text: Caption text

        Returns:
            Speaker name if found, None otherwise
        """
        # Try colon-separated format: "Speaker: text"
        colon_match = re.match(r"^([A-Za-z\s]+):\s*", text)
        if colon_match:
            return colon_match.group(1).strip()

        # Try voice tag format: "<v Speaker>text"
        voice_match = re.match(r"^<v\s+([^>]+)>", text)
        if voice_match:
            return voice_match.group(1).strip()

        return None

    def _clean_caption_text(self, text: str) -> str:
        """Remove speaker tags and formatting from caption text.

        Args:
            text: Raw caption text

        Returns:
            Cleaned text without speaker tags
        """
        # Remove voice tags: "<v Speaker>text" → "text"
        text = re.sub(r"<v\s+[^>]+>", "", text)

        # Remove speaker prefix: "Speaker: text" → "text"
        text = re.sub(r"^([A-Za-z\s]+):\s*", "", text)

        # Remove other common VTT tags
        text = re.sub(r"<[^>]+>", "", text)

        # Clean up whitespace
        text = " ".join(text.split())

        return text.strip()

    def _time_to_seconds(self, timestamp: str) -> float:
        """Convert VTT timestamp to seconds.

        Args:
            timestamp: Timestamp in format "HH:MM:SS.mmm" or "MM:SS.mmm"

        Returns:
            Time in seconds as float

        Raises:
            ValueError: If timestamp format is invalid
        """
        try:
            # Handle both "HH:MM:SS.mmm" and "MM:SS.mmm" formats
            parts = timestamp.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = parts
                hours = int(hours)
            elif len(parts) == 2:
                hours = 0
                minutes, seconds = parts
            else:
                raise ValueError(f"Invalid timestamp format: {timestamp}")

            minutes = int(minutes)
            seconds = float(seconds)

            return hours * 3600 + minutes * 60 + seconds

        except Exception as e:
            raise ValueError(f"Failed to parse timestamp '{timestamp}': {e}")

    def _build_text_and_mapping(
        self, captions: List[Dict]
    ) -> Tuple[str, List[Dict]]:
        """Build full transcript text and character-to-timestamp mapping.

        Args:
            captions: List of caption dictionaries

        Returns:
            Tuple of (full_text, timestamp_map) where timestamp_map is a list of:
                {
                    'char_start': int,
                    'char_end': int,
                    'time_start': str,
                    'time_end': str,
                    'speaker': Optional[str]
                }
        """
        full_text = ""
        timestamp_map = []

        for caption in captions:
            char_start = len(full_text)
            text = caption["text"]

            # Add text with space separator (if not first caption)
            if full_text:
                full_text += " " + text
                char_start = len(full_text) - len(text)
            else:
                full_text = text

            char_end = len(full_text)

            # Record mapping
            timestamp_map.append(
                {
                    "char_start": char_start,
                    "char_end": char_end,
                    "time_start": caption["start"],
                    "time_end": caption["end"],
                    "speaker": caption["speaker"],
                }
            )

        return full_text, timestamp_map

    def _get_time_range(
        self, timestamp_map: List[Dict], start_char: int, end_char: int
    ) -> Dict[str, str]:
        """Extract time range for a character range in the transcript.

        Args:
            timestamp_map: Character-to-timestamp mapping from _build_text_and_mapping
            start_char: Start character position
            end_char: End character position

        Returns:
            Dictionary with 'start' and 'end' timestamps
        """
        # Find captions that overlap with [start_char, end_char)
        start_time = None
        end_time = None

        for mapping in timestamp_map:
            # Check if this mapping overlaps with our range
            overlaps = not (
                mapping["char_end"] <= start_char or mapping["char_start"] >= end_char
            )

            if overlaps:
                if start_time is None:
                    start_time = mapping["time_start"]
                end_time = mapping["time_end"]

        # Fallback if no overlap found (shouldn't happen)
        if start_time is None or end_time is None:
            if timestamp_map:
                start_time = timestamp_map[0]["time_start"]
                end_time = timestamp_map[-1]["time_end"]
            else:
                start_time = "00:00:00.000"
                end_time = "00:00:00.000"

        return {"start": start_time, "end": end_time}

    def _extract_speakers_from_range(
        self, timestamp_map: List[Dict], start_char: int, end_char: int
    ) -> List[str]:
        """Extract unique speakers for a character range.

        Args:
            timestamp_map: Character-to-timestamp mapping
            start_char: Start character position
            end_char: End character position

        Returns:
            Sorted list of unique speaker names
        """
        speakers = set()

        for mapping in timestamp_map:
            # Check if this mapping overlaps with our range
            overlaps = not (
                mapping["char_end"] <= start_char or mapping["char_start"] >= end_char
            )

            if overlaps and mapping["speaker"]:
                speakers.add(mapping["speaker"])

        return sorted(list(speakers))

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array (shape: [embedding_dim])

        Raises:
            RuntimeError: If embedding generation fails
        """
        try:
            embedding = self._embedding_model.encode(
                text, convert_to_numpy=True, show_progress_bar=False
            )
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")
