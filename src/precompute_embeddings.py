"""CLI script to pre-compute FAISS embeddings for mental health medication documents.

This script loads documents, computes embeddings, and saves artifacts for fast loading.

Usage:
    python -m src.precompute_embeddings
    python -m src.precompute_embeddings --output data/embeddings/ --model sentence-transformers/all-MiniLM-L6-v2
"""

import argparse
import asyncio
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import List

import faiss
import numpy as np
from tqdm import tqdm

from app.config import settings
from app.core.retriever import Document, FAISSRetriever
from app.utils.data_loader import load_medical_documents


async def precompute_embeddings(
    output_dir: Path,
    embedding_model: str,
) -> None:
    """Pre-compute FAISS embeddings and save artifacts.

    Args:
        output_dir: Directory to save artifacts
        embedding_model: Name of sentence-transformers model to use

    Raises:
        ValueError: If document loading or embedding computation fails
        IOError: If artifact saving fails
    """
    print(f"🚀 Starting embedding pre-computation...")
    print(f"   Model: {embedding_model}")
    print(f"   Output: {output_dir}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load documents
    print("\n📚 Loading documents...")
    try:
        documents = await load_medical_documents()
        print(f"   ✓ Loaded {len(documents)} documents")
    except Exception as e:
        raise ValueError(f"Failed to load documents: {e}")

    if not documents:
        raise ValueError("No documents found to process")

    # Step 2: Initialize retriever and compute embeddings
    print(f"\n🔢 Computing embeddings with {embedding_model}...")
    try:
        retriever = FAISSRetriever(embedding_model=embedding_model)

        # Show progress bar for embedding computation
        with tqdm(total=len(documents), desc="   Processing documents", unit="doc") as pbar:
            # Add documents (this computes embeddings internally)
            await retriever.add_documents(documents)
            pbar.update(len(documents))

        print(f"   ✓ Computed embeddings for {len(documents)} documents")
    except Exception as e:
        raise ValueError(f"Failed to compute embeddings: {e}")

    # Step 3: Validate embeddings were created
    if retriever._embeddings is None or retriever._index is None:
        raise ValueError("Embeddings or FAISS index not properly initialized")

    embeddings_array = retriever._embeddings
    embedding_dim = embeddings_array.shape[1]
    print(f"   ✓ Embedding dimension: {embedding_dim}")

    # Step 4: Save artifacts
    print("\n💾 Saving artifacts...")

    try:
        # Save FAISS index
        faiss_path = output_dir / "faiss_index.pkl"
        with open(faiss_path, "wb") as f:
            pickle.dump(retriever._index, f)
        print(f"   ✓ Saved FAISS index: {faiss_path}")

        # Save documents
        docs_path = output_dir / "documents.pkl"
        with open(docs_path, "wb") as f:
            pickle.dump(documents, f)
        print(f"   ✓ Saved documents: {docs_path}")

        # Save embeddings as NumPy array
        embeddings_path = output_dir / "embeddings.npy"
        np.save(embeddings_path, embeddings_array)
        print(f"   ✓ Saved embeddings: {embeddings_path}")

        # Save metadata
        metadata = {
            "model": embedding_model,
            "embedding_dim": int(embedding_dim),
            "doc_count": len(documents),
            "timestamp": datetime.utcnow().isoformat(),
            "faiss_index_type": "IndexFlatL2",
        }
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print(f"   ✓ Saved metadata: {metadata_path}")

    except Exception as e:
        raise IOError(f"Failed to save artifacts: {e}")

    # Step 5: Validation
    print("\n✅ Validating artifacts...")
    try:
        # Verify files exist and have reasonable sizes
        for file_path, min_size in [
            (faiss_path, 100),  # FAISS index should be at least 100 bytes
            (docs_path, 1000),  # Documents should be at least 1KB
            (embeddings_path, 1000),  # Embeddings should be at least 1KB
            (metadata_path, 100),  # Metadata should be at least 100 bytes
        ]:
            if not file_path.exists():
                raise ValueError(f"Missing artifact: {file_path}")
            size = file_path.stat().st_size
            if size < min_size:
                raise ValueError(f"Artifact too small ({size} bytes): {file_path}")
            print(f"   ✓ {file_path.name} ({size:,} bytes)")

        print("\n🎉 Pre-computation completed successfully!")
        print(f"\nTo use these embeddings, update your FAISSRetriever to load from:")
        print(f"   {output_dir.absolute()}")

    except Exception as e:
        raise ValueError(f"Validation failed: {e}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-compute FAISS embeddings for mental health medication documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings
  python -m src.precompute_embeddings

  # Custom output directory
  python -m src.precompute_embeddings --output /path/to/embeddings/

  # Custom embedding model
  python -m src.precompute_embeddings --model sentence-transformers/all-mpnet-base-v2
        """,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/embeddings"),
        help="Output directory for artifacts (default: data/embeddings/)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=settings.embedding_model,
        help=f"Sentence-transformers model name (default: {settings.embedding_model})",
    )

    args = parser.parse_args()

    # Run async function
    try:
        asyncio.run(precompute_embeddings(
            output_dir=args.output,
            embedding_model=args.model,
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
