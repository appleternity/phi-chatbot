"""CLI script to pre-compute parenting video embeddings with hierarchical parent-child chunking.

This script processes VTT video transcripts and builds indices for hybrid retrieval:
- FAISS vector index for semantic search (child embeddings)
- BM25 keyword index for term matching
- Parent-child relationship mapping
- Video metadata catalog

The hierarchical structure enables:
- Broad context retrieval (parents ~750 tokens)
- Precise semantic search (children ~150 tokens)
- Fast hybrid retrieval with pre-computed embeddings

Output Structure:
    data/parenting_index/
    ├── faiss_index.pkl          # FAISS vector index (child embeddings)
    ├── bm25_index.pkl           # BM25 keyword index (tokenized docs)
    ├── parent_chunks.pkl        # Dict[parent_id, parent_data]
    ├── child_documents.pkl      # List[Document] with embeddings
    ├── video_catalog.json       # Metadata about all processed videos
    └── metadata.json            # Index statistics and config

Usage:
    # Process all VTT files with default settings
    python -m src.precompute_parenting_embeddings --force

    # Test mode - process only first 10 files
    python -m src.precompute_parenting_embeddings --limit 10

    # Custom directories
    python -m src.precompute_parenting_embeddings \\
        --input-dir data/videos/ \\
        --output-dir data/custom_index/
"""

import argparse
import asyncio
import json
import logging
import pickle
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from tqdm import tqdm

from app.config import settings
from app.core.retriever import Document
from app.core.transcript_chunker import TranscriptChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ParentingEmbeddingsPreprocessor:
    """Process VTT transcripts into hierarchical parent-child indices.

    This class orchestrates the complete pipeline:
    1. Scan and validate VTT files
    2. Extract video metadata from filenames
    3. Process transcripts with TranscriptChunker
    4. Build FAISS and BM25 indices
    5. Generate comprehensive metadata and catalog
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        child_chunk_size: int = 150,
        parent_chunk_size: int = 750,
        overlap: int = 30,
        embedding_model: str = None,
    ):
        """Initialize preprocessor with configuration.

        Args:
            input_dir: Directory containing VTT files
            output_dir: Directory to save indices and metadata
            child_chunk_size: Target tokens per child chunk (default 150)
            parent_chunk_size: Target tokens per parent chunk (default 750)
            overlap: Overlap tokens for context preservation (default 30)
            embedding_model: SentenceTransformer model name (default from settings)
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.child_chunk_size = child_chunk_size
        self.parent_chunk_size = parent_chunk_size
        self.overlap = overlap
        self.embedding_model = embedding_model or settings.embedding_model

        # Initialize transcript chunker
        self.chunker = TranscriptChunker(
            child_chunk_size=child_chunk_size,
            parent_chunk_size=parent_chunk_size,
            overlap=overlap,
            model_name=self.embedding_model,
        )

        # Statistics
        self.stats = {
            "total_videos": 0,
            "successful_videos": 0,
            "failed_videos": 0,
            "total_parents": 0,
            "total_children": 0,
            "processing_errors": [],
        }

    def scan_vtt_files(self, limit: Optional[int] = None) -> List[Path]:
        """Scan input directory for VTT files.

        Args:
            limit: Maximum number of files to process (None for all)

        Returns:
            List of VTT file paths

        Raises:
            ValueError: If input directory doesn't exist or contains no VTT files
        """
        if not self.input_dir.exists():
            raise ValueError(f"Input directory does not exist: {self.input_dir}")

        vtt_files = sorted(self.input_dir.glob("*.vtt"))

        if not vtt_files:
            raise ValueError(f"No VTT files found in {self.input_dir}")

        if limit and limit > 0:
            vtt_files = vtt_files[:limit]
            logger.info(f"Limiting processing to first {limit} files")

        logger.info(f"Found {len(vtt_files)} VTT files to process")
        return vtt_files

    def extract_video_metadata(self, vtt_path: Path) -> Dict:
        """Extract video metadata from VTT filename.

        Expected filename format:
            video_{video_id}_{title}.vtt

        Examples:
            video_12949_Feeding_Littles_7102023.vtt
            video_1069_VID_008_12_21_Listening.vtt

        Args:
            vtt_path: Path to VTT file

        Returns:
            Dictionary with video metadata:
                {
                    'video_id': str,
                    'title': str,
                    'filename': str,
                    'source': str
                }
        """
        filename = vtt_path.stem  # Filename without .vtt extension

        # Parse filename: video_{id}_{title}
        match = re.match(r"video_(\d+)_(.+)", filename)

        if match:
            video_id = match.group(1)
            title_raw = match.group(2)

            # Clean title: replace underscores and common patterns
            title = title_raw.replace("_", " ")
            # Remove date patterns like "7102023" or "12_21"
            title = re.sub(r"\d{7,8}", "", title)
            title = re.sub(r"\d{2}_\d{2}", "", title)
            # Clean up extra spaces
            title = " ".join(title.split()).strip()

            # Remove trailing dots or special characters
            title = re.sub(r"[：.]+$", "", title)
        else:
            # Fallback for non-standard filenames
            video_id = filename
            title = filename.replace("_", " ")

        return {
            "video_id": video_id,
            "title": title,
            "filename": vtt_path.name,
            "source": "parenting_videos",
        }

    def process_single_vtt(
        self, vtt_path: Path
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Process a single VTT file into parent-child chunks.

        Args:
            vtt_path: Path to VTT file

        Returns:
            Tuple of (chunks_dict, error_message)
            - chunks_dict: {'parents': [...], 'children': [...]} if successful
            - error_message: Error description if failed, None if successful
        """
        try:
            # Extract video metadata
            video_metadata = self.extract_video_metadata(vtt_path)

            # Create chunks with TranscriptChunker
            chunks = self.chunker.create_chunks(
                vtt_path=str(vtt_path), video_metadata=video_metadata
            )

            logger.info(
                f"✓ Processed {vtt_path.name}: "
                f"{len(chunks['parents'])} parents, "
                f"{len(chunks['children'])} children"
            )

            return chunks, None

        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            logger.error(f"✗ {vtt_path.name}: {error_msg}")
            return None, error_msg

        except ValueError as e:
            error_msg = f"Malformed VTT file: {e}"
            logger.warning(f"⚠ {vtt_path.name}: {error_msg}")
            return None, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {e}"
            logger.error(f"✗ {vtt_path.name}: {error_msg}")
            return None, error_msg

    def build_indices(
        self,
        all_parents: List[Dict],
        all_children: List[Dict],
    ) -> Tuple[object, object, Dict, List[Document]]:
        """Build FAISS and BM25 indices from chunks.

        Args:
            all_parents: List of all parent chunks
            all_children: List of all child chunks

        Returns:
            Tuple of (faiss_index, bm25_index, parent_store, child_documents)
            - faiss_index: FAISS IndexFlatL2 with child embeddings
            - bm25_index: BM25Okapi index for keyword search
            - parent_store: Dict mapping parent_id to parent data
            - child_documents: List[Document] with embeddings for children

        Raises:
            ValueError: If no children to index
        """
        if not all_children:
            raise ValueError("No child chunks to build indices")

        logger.info(f"\n🔨 Building indices...")

        # Step 1: Create Document objects for children
        child_documents = []
        child_embeddings = []

        for child in all_children:
            doc = Document(
                id=child["child_id"],
                content=child["text"],
                metadata={
                    "parent_id": child["parent_id"],
                    "video_id": child.get("video_id", ""),
                    "title": child.get("title", ""),
                    "time_start": child["time_start"],
                    "time_end": child["time_end"],
                    "speakers": child["speakers"],
                    "char_start": child["char_start"],
                    "char_end": child["char_end"],
                    "source": child.get("source", "parenting_videos"),
                },
                parent_id=child["parent_id"],
                timestamp_start=child["time_start"],
                timestamp_end=child["time_end"],
            )
            child_documents.append(doc)
            child_embeddings.append(child["embedding"])

        logger.info(f"   ✓ Created {len(child_documents)} child documents")

        # Step 2: Build FAISS index from child embeddings
        embeddings_array = np.vstack(child_embeddings).astype("float32")
        dimension = embeddings_array.shape[1]

        faiss_index = faiss.IndexFlatL2(dimension)
        faiss_index.add(embeddings_array)

        logger.info(
            f"   ✓ Built FAISS index: dimension={dimension}, "
            f"vectors={len(child_documents)}"
        )

        # Step 3: Build BM25 index from child text
        tokenized_corpus = [doc.content.lower().split() for doc in child_documents]
        bm25_index = BM25Okapi(tokenized_corpus)

        logger.info(f"   ✓ Built BM25 index: documents={len(tokenized_corpus)}")

        # Step 4: Build parent store (parent_id → parent_data mapping)
        parent_store = {}
        for parent in all_parents:
            parent_id = parent["parent_id"]
            parent_store[parent_id] = {
                "parent_id": parent_id,
                "text": parent["text"],
                "video_id": parent.get("video_id", ""),
                "title": parent.get("title", ""),
                "time_start": parent["time_start"],
                "time_end": parent["time_end"],
                "speakers": parent["speakers"],
                "char_start": parent["char_start"],
                "char_end": parent["char_end"],
                "child_count": parent["child_count"],
                "child_ids": parent.get("child_ids", []),
                "source": parent.get("source", "parenting_videos"),
            }

        logger.info(f"   ✓ Built parent store: {len(parent_store)} parents")

        return faiss_index, bm25_index, parent_store, child_documents

    def generate_video_catalog(self, all_parents: List[Dict]) -> Dict:
        """Generate video catalog with per-video statistics.

        Args:
            all_parents: List of all parent chunks

        Returns:
            Dictionary mapping video_id to video metadata:
                {
                    'video_id': {
                        'video_id': str,
                        'title': str,
                        'filename': str,
                        'parent_count': int,
                        'total_duration_seconds': float,
                        'speakers': List[str]
                    }
                }
        """
        catalog = {}

        # Group parents by video_id
        videos = defaultdict(list)
        for parent in all_parents:
            video_id = parent.get("video_id", "unknown")
            videos[video_id].append(parent)

        # Generate catalog entry for each video
        for video_id, parents in videos.items():
            # Get video metadata from first parent
            first_parent = parents[0]

            # Calculate total duration (from first to last timestamp)
            if parents:
                start_time = self._time_to_seconds(parents[0]["time_start"])
                end_time = self._time_to_seconds(parents[-1]["time_end"])
                duration = end_time - start_time
            else:
                duration = 0.0

            # Collect unique speakers
            all_speakers = set()
            for parent in parents:
                all_speakers.update(parent.get("speakers", []))

            catalog[video_id] = {
                "video_id": video_id,
                "title": first_parent.get("title", ""),
                "filename": first_parent.get("filename", ""),
                "parent_count": len(parents),
                "total_duration_seconds": round(duration, 2),
                "speakers": sorted(list(all_speakers)),
            }

        return catalog

    def _time_to_seconds(self, timestamp: str) -> float:
        """Convert VTT timestamp to seconds.

        Args:
            timestamp: Timestamp in format "HH:MM:SS.mmm" or "MM:SS.mmm"

        Returns:
            Time in seconds as float
        """
        try:
            parts = timestamp.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = parts
                hours = int(hours)
            elif len(parts) == 2:
                hours = 0
                minutes, seconds = parts
            else:
                return 0.0

            minutes = int(minutes)
            seconds = float(seconds)

            return hours * 3600 + minutes * 60 + seconds

        except Exception:
            return 0.0

    def save_indices(
        self,
        faiss_index: object,
        bm25_index: object,
        parent_store: Dict,
        child_documents: List[Document],
        video_catalog: Dict,
    ) -> None:
        """Save all indices and metadata to disk.

        Args:
            faiss_index: FAISS index object
            bm25_index: BM25 index object
            parent_store: Dictionary of parent chunks
            child_documents: List of child Document objects
            video_catalog: Video metadata catalog

        Raises:
            IOError: If unable to save files
        """
        logger.info(f"\n💾 Saving indices to {self.output_dir}...")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save FAISS index
            faiss_path = self.output_dir / "faiss_index.pkl"
            with open(faiss_path, "wb") as f:
                pickle.dump(faiss_index, f)
            size_mb = faiss_path.stat().st_size / (1024 * 1024)
            logger.info(f"   ✓ Saved FAISS index: {faiss_path.name} ({size_mb:.2f} MB)")

            # Save BM25 index
            bm25_path = self.output_dir / "bm25_index.pkl"
            with open(bm25_path, "wb") as f:
                pickle.dump(bm25_index, f)
            size_mb = bm25_path.stat().st_size / (1024 * 1024)
            logger.info(f"   ✓ Saved BM25 index: {bm25_path.name} ({size_mb:.2f} MB)")

            # Save parent chunks
            parents_path = self.output_dir / "parent_chunks.pkl"
            with open(parents_path, "wb") as f:
                pickle.dump(parent_store, f)
            size_mb = parents_path.stat().st_size / (1024 * 1024)
            logger.info(f"   ✓ Saved parent chunks: {parents_path.name} ({size_mb:.2f} MB)")

            # Save child documents
            docs_path = self.output_dir / "child_documents.pkl"
            with open(docs_path, "wb") as f:
                pickle.dump(child_documents, f)
            size_mb = docs_path.stat().st_size / (1024 * 1024)
            logger.info(f"   ✓ Saved child documents: {docs_path.name} ({size_mb:.2f} MB)")

            # Save video catalog
            catalog_path = self.output_dir / "video_catalog.json"
            with open(catalog_path, "w", encoding="utf-8") as f:
                json.dump(video_catalog, f, indent=2, ensure_ascii=False)
            logger.info(f"   ✓ Saved video catalog: {catalog_path.name}")

            # Save metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "embedding_model": self.embedding_model,
                "child_chunk_size": self.child_chunk_size,
                "parent_chunk_size": self.parent_chunk_size,
                "overlap": self.overlap,
                "embedding_dim": int(
                    faiss_index.d if hasattr(faiss_index, "d") else 0
                ),
                "statistics": {
                    "total_videos": self.stats["total_videos"],
                    "successful_videos": self.stats["successful_videos"],
                    "failed_videos": self.stats["failed_videos"],
                    "total_parent_chunks": len(parent_store),
                    "total_child_chunks": len(child_documents),
                    "faiss_index_type": "IndexFlatL2",
                    "bm25_tokenization": "simple_whitespace",
                },
                "processing_errors": self.stats["processing_errors"],
            }

            metadata_path = self.output_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"   ✓ Saved metadata: {metadata_path.name}")

        except Exception as e:
            logger.error(f"Failed to save indices: {e}")
            raise IOError(f"Failed to save indices to {self.output_dir}: {e}")

    def validate_indices(self) -> None:
        """Validate saved indices exist and have reasonable sizes.

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"\n✅ Validating indices...")

        required_files = [
            ("faiss_index.pkl", 1000),  # At least 1KB
            ("bm25_index.pkl", 1000),
            ("parent_chunks.pkl", 1000),
            ("child_documents.pkl", 1000),
            ("video_catalog.json", 100),
            ("metadata.json", 100),
        ]

        all_valid = True
        for filename, min_size in required_files:
            file_path = self.output_dir / filename
            if not file_path.exists():
                logger.error(f"   ✗ Missing file: {filename}")
                all_valid = False
            else:
                size = file_path.stat().st_size
                if size < min_size:
                    logger.warning(
                        f"   ⚠ File too small ({size} bytes): {filename}"
                    )
                else:
                    size_kb = size / 1024
                    logger.info(f"   ✓ {filename} ({size_kb:.1f} KB)")

        if not all_valid:
            raise ValueError("Index validation failed: missing required files")

        logger.info(f"   ✓ All indices validated successfully")

    def print_summary(self, video_catalog: Dict) -> None:
        """Print processing summary report.

        Args:
            video_catalog: Video metadata catalog
        """
        print("\n" + "=" * 80)
        print("📊 PROCESSING SUMMARY")
        print("=" * 80)

        print(f"\n📹 Videos:")
        print(f"   Total processed:  {self.stats['total_videos']}")
        print(f"   Successful:       {self.stats['successful_videos']} ✓")
        print(f"   Failed:           {self.stats['failed_videos']} ✗")

        print(f"\n📦 Chunks:")
        print(f"   Parent chunks:    {self.stats['total_parents']:,}")
        print(f"   Child chunks:     {self.stats['total_children']:,}")
        print(
            f"   Avg children/parent: {self.stats['total_children'] / max(self.stats['total_parents'], 1):.1f}"
        )

        print(f"\n⚙️  Configuration:")
        print(f"   Embedding model:  {self.embedding_model}")
        print(f"   Parent size:      {self.parent_chunk_size} tokens (~3min)")
        print(f"   Child size:       {self.child_chunk_size} tokens (~35sec)")
        print(f"   Overlap:          {self.overlap} tokens")

        if video_catalog:
            total_duration = sum(
                v["total_duration_seconds"] for v in video_catalog.values()
            )
            hours = int(total_duration // 3600)
            minutes = int((total_duration % 3600) // 60)
            print(f"\n⏱️  Total video duration: {hours}h {minutes}m")

        if self.stats["processing_errors"]:
            print(f"\n⚠️  Processing Errors ({len(self.stats['processing_errors'])}):")
            for error in self.stats["processing_errors"][:5]:  # Show first 5
                print(f"   • {error['file']}: {error['error']}")
            if len(self.stats["processing_errors"]) > 5:
                print(f"   ... and {len(self.stats['processing_errors']) - 5} more")

        print(f"\n💾 Output directory:")
        print(f"   {self.output_dir.absolute()}")

        print("\n" + "=" * 80)
        print("🎉 Pre-computation completed successfully!")
        print("=" * 80)

    async def run(self, limit: Optional[int] = None) -> None:
        """Run the complete preprocessing pipeline.

        Args:
            limit: Maximum number of VTT files to process (None for all)

        Raises:
            ValueError: If input validation fails
            IOError: If file operations fail
        """
        start_time = datetime.now()

        logger.info("🚀 Starting parenting embeddings pre-computation...")
        logger.info(f"   Input:  {self.input_dir}")
        logger.info(f"   Output: {self.output_dir}")

        # Step 1: Scan VTT files
        vtt_files = self.scan_vtt_files(limit=limit)
        self.stats["total_videos"] = len(vtt_files)

        # Step 2: Process all VTT files
        logger.info(f"\n📝 Processing {len(vtt_files)} VTT files...")

        all_parents = []
        all_children = []
        global_parent_counter = 0
        global_child_counter = 0

        with tqdm(total=len(vtt_files), desc="Processing videos", unit="video") as pbar:
            for vtt_path in vtt_files:
                chunks, error = self.process_single_vtt(vtt_path)

                if chunks:
                    # Re-assign parent and child IDs to ensure uniqueness across videos
                    # Create mapping from old IDs to new IDs
                    parent_id_map = {}

                    for parent in chunks["parents"]:
                        old_parent_id = parent["parent_id"]
                        new_parent_id = f"parent_{global_parent_counter}"
                        parent_id_map[old_parent_id] = new_parent_id
                        parent["parent_id"] = new_parent_id
                        global_parent_counter += 1

                    for child in chunks["children"]:
                        # Update parent_id reference
                        old_parent_id = child["parent_id"]
                        child["parent_id"] = parent_id_map.get(old_parent_id, old_parent_id)

                        # Update child_id
                        child["child_id"] = f"child_{global_child_counter}"
                        global_child_counter += 1

                    all_parents.extend(chunks["parents"])
                    all_children.extend(chunks["children"])
                    self.stats["successful_videos"] += 1
                else:
                    self.stats["failed_videos"] += 1
                    self.stats["processing_errors"].append(
                        {"file": vtt_path.name, "error": error}
                    )

                pbar.update(1)

        self.stats["total_parents"] = len(all_parents)
        self.stats["total_children"] = len(all_children)

        logger.info(
            f"\n✓ Processed {self.stats['successful_videos']}/{self.stats['total_videos']} videos"
        )
        logger.info(
            f"   Parents: {len(all_parents):,}, Children: {len(all_children):,}"
        )

        if not all_children:
            raise ValueError(
                "No child chunks generated. Cannot build indices. "
                f"Failed videos: {self.stats['failed_videos']}"
            )

        # Step 3: Build indices
        faiss_index, bm25_index, parent_store, child_documents = self.build_indices(
            all_parents, all_children
        )

        # Step 4: Generate video catalog
        video_catalog = self.generate_video_catalog(all_parents)
        logger.info(f"   ✓ Generated catalog for {len(video_catalog)} videos")

        # Step 5: Save all artifacts
        self.save_indices(
            faiss_index, bm25_index, parent_store, child_documents, video_catalog
        )

        # Step 6: Validate saved files
        self.validate_indices()

        # Step 7: Print summary
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n⏱️  Total processing time: {elapsed_time:.1f}s")

        self.print_summary(video_catalog)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-compute parenting video embeddings with hierarchical chunking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all VTT files with default settings (overwrite existing)
  python -m src.precompute_parenting_embeddings --force

  # Test mode - process only first 10 files
  python -m src.precompute_parenting_embeddings --limit 10

  # Custom directories
  python -m src.precompute_parenting_embeddings \\
      --input-dir data/videos/ \\
      --output-dir data/custom_index/

  # Custom chunking parameters
  python -m src.precompute_parenting_embeddings \\
      --child-size 200 \\
      --parent-size 1000 \\
      --overlap 50

Output Files:
  faiss_index.pkl          FAISS vector index (child embeddings)
  bm25_index.pkl           BM25 keyword index (tokenized docs)
  parent_chunks.pkl        Dict[parent_id, parent_data]
  child_documents.pkl      List[Document] with embeddings
  video_catalog.json       Metadata about all processed videos
  metadata.json            Index statistics and configuration
        """,
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/video_transcripts"),
        help="Directory containing VTT files (default: data/video_transcripts/)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/parenting_index"),
        help="Output directory for indices (default: data/parenting_index/)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing indices if present",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N files (for testing)",
    )

    parser.add_argument(
        "--child-size",
        type=int,
        default=150,
        help="Child chunk size in tokens (default: 150 ~35sec)",
    )

    parser.add_argument(
        "--parent-size",
        type=int,
        default=750,
        help="Parent chunk size in tokens (default: 750 ~3min)",
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=30,
        help="Overlap size in tokens (default: 30)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Embedding model name (default: {settings.embedding_model})",
    )

    args = parser.parse_args()

    # Check if output directory exists and handle --force flag
    if args.output_dir.exists() and not args.force:
        print(f"\n⚠️  Output directory already exists: {args.output_dir}")
        print("   Use --force to overwrite existing indices")
        print("   Or specify a different --output-dir")
        exit(1)

    # Create preprocessor
    try:
        preprocessor = ParentingEmbeddingsPreprocessor(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            child_chunk_size=args.child_size,
            parent_chunk_size=args.parent_size,
            overlap=args.overlap,
            embedding_model=args.model,
        )

        # Run preprocessing pipeline
        asyncio.run(preprocessor.run(limit=args.limit))

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        exit(1)

    except Exception as e:
        logger.exception("Fatal error during preprocessing")
        print(f"\n\n❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
