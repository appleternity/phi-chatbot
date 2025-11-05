#!/usr/bin/env python3
"""
Simple smoke test for the indexing pipeline.

This script tests:
1. Parsing a single chunk file (no database required)
2. Embedding generation (requires database connection)
3. Database insertion (requires database connection)

Prerequisites:
    1. Start PostgreSQL with pgvector:
       docker-compose up -d postgres

    2. Set environment variables:
       export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/semantic_search"
       # OR
       export POSTGRES_DB="semantic_search"
       export POSTGRES_USER="postgres"
       export POSTGRES_PASSWORD="postgres"

    3. Run database migration (create schema):
       python -m app.db.schema

Usage:
    python test_indexing.py
"""

import asyncio
import json
import sys
from pathlib import Path

from src.embeddings.indexer import DocumentIndexer
from app.db.connection import get_pool, close_pool


async def test_parse_chunk():
    """Test parsing a single chunk file."""
    print("\n" + "=" * 60)
    print("TEST 1: Parse Chunk File (No Database Required)")
    print("=" * 60)

    # Find first chunk file in data directory
    data_dir = Path("data/chunking_final")
    chunk_files = list(data_dir.rglob("*chunk_*.json"))

    if not chunk_files:
        print("❌ No chunk files found in data/chunking_final")
        return False

    test_file = chunk_files[0]
    print(f"Testing with: {test_file.name}")

    try:
        # Load raw JSON
        with open(test_file, 'r') as f:
            raw_data = json.load(f)

        print("✅ JSON loaded successfully")
        print(f"   - chunk_id: {raw_data.get('chunk_id', 'MISSING')}")
        print(f"   - source_document: {raw_data.get('source_document', 'MISSING')}")
        print(f"   - token_count: {raw_data.get('token_count', 'MISSING')}")
        print(f"   - chunk_text length: {len(raw_data.get('chunk_text', ''))}")

        # Parse with Pydantic directly (no database needed)
        from src.embeddings.models import ChunkMetadata

        metadata = raw_data.get('metadata', {})
        chunk_metadata = ChunkMetadata(
            chunk_id=raw_data['chunk_id'],
            source_document=raw_data['source_document'],
            chapter_title=metadata.get('chapter_title', ''),
            section_title=metadata.get('section_title', ''),
            subsection_title=metadata.get('subsection_title', []),
            summary=metadata.get('summary', ''),
            token_count=raw_data['token_count'],
            chunk_text=raw_data['chunk_text']
        )

        print("✅ ChunkMetadata parsed successfully")
        print(f"   - chunk_id: {chunk_metadata.chunk_id}")
        print(f"   - chapter_title: {chunk_metadata.chapter_title[:50] if chunk_metadata.chapter_title else 'None'}...")
        print(f"   - section_title: {chunk_metadata.section_title[:50] if chunk_metadata.section_title else 'None'}...")
        print(f"   - subsection_title: {chunk_metadata.subsection_title}")
        print(f"   - summary: {chunk_metadata.summary[:50] if chunk_metadata.summary else 'None'}...")

        return True

    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_embedding_generation():
    """Test embedding generation for a single chunk."""
    print("\n" + "=" * 60)
    print("TEST 2: Embedding Generation")
    print("=" * 60)

    try:
        # Initialize pool and indexer with direct parameters
        pool = await get_pool()
        indexer = DocumentIndexer(
            db_pool=pool,
            model_name="Qwen/Qwen3-Embedding-0.6B",
            device="mps",
            batch_size=1,
            normalize_embeddings=True
        )

        print("✅ Indexer created with Qwen3-Embedding-0.6B on mps")

        print("✅ Encoder initialized")

        # Find test chunk
        data_dir = Path("data/chunking_final")
        chunk_files = list(data_dir.rglob("*chunk_*.json"))

        if not chunk_files:
            print("❌ No chunk files found")
            await close_pool()
            return False

        # Parse chunk
        chunk_metadata = indexer.parse_chunk_file(chunk_files[0])
        print(f"✅ Chunk parsed: {chunk_metadata.chunk_id}")

        # Generate embedding
        vector_docs = await indexer.generate_embeddings([chunk_metadata])

        if not vector_docs:
            print("❌ No embeddings generated")
            await close_pool()
            return False

        vector_doc = vector_docs[0]

        print("✅ Embedding generated successfully")
        print(f"   - Dimension: {len(vector_doc.embedding)}")
        print(f"   - First 5 values: {vector_doc.embedding[:5]}")
        print(f"   - Min value: {min(vector_doc.embedding):.6f}")
        print(f"   - Max value: {max(vector_doc.embedding):.6f}")

        # Check for NaN/infinity
        import math
        has_nan = any(math.isnan(v) for v in vector_doc.embedding)
        has_inf = any(math.isinf(v) for v in vector_doc.embedding)

        if has_nan or has_inf:
            print(f"❌ Invalid values detected: NaN={has_nan}, Inf={has_inf}")
            await close_pool()
            return False

        print("✅ No NaN or infinity values detected")

        await close_pool()
        return True

    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_insertion():
    """Test inserting a single chunk into the database."""
    print("\n" + "=" * 60)
    print("TEST 3: Database Insertion")
    print("=" * 60)

    try:
        # Initialize pool and indexer with defaults
        pool = await get_pool()
        indexer = DocumentIndexer(db_pool=pool)

        print("✅ Database connected")

        # Find test chunk
        data_dir = Path("data/chunking_final")
        chunk_files = list(data_dir.rglob("*chunk_*.json"))

        if not chunk_files:
            print("❌ No chunk files found")
            await close_pool()
            return False

        # Parse and generate embedding
        chunk_metadata = indexer.parse_chunk_file(chunk_files[0])
        vector_docs = await indexer.generate_embeddings([chunk_metadata])

        if not vector_docs:
            print("❌ No embeddings generated")
            await close_pool()
            return False

        vector_doc = vector_docs[0]
        print(f"✅ Test document prepared: {vector_doc.chunk_id}")

        # Insert into database
        inserted_count = await indexer.insert_documents([vector_doc])

        print("✅ Database insertion completed")
        print(f"   - Inserted count: {inserted_count}")

        # Verify insertion
        result = await pool.fetch(
            "SELECT chunk_id, source_document, token_count, "
            "array_length(embedding::float[], 1) as embedding_dim "
            "FROM vector_chunks WHERE chunk_id = $1",
            vector_doc.chunk_id
        )

        if result:
            row = result[0]
            print("✅ Verification successful")
            print(f"   - chunk_id: {row['chunk_id']}")
            print(f"   - source_document: {row['source_document']}")
            print(f"   - token_count: {row['token_count']}")
            print(f"   - embedding_dim: {row['embedding_dim']}")
        else:
            print("❌ Chunk not found in database after insertion")
            await close_pool()
            return False

        # Test duplicate handling (ON CONFLICT DO NOTHING)
        print("\n--- Testing duplicate handling ---")
        inserted_count_2 = await indexer.insert_documents([vector_doc])
        print(f"✅ Duplicate insert handled (expected 0): {inserted_count_2}")

        await close_pool()
        return True

    except Exception as e:
        print(f"❌ Database insertion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all smoke tests."""
    print("\n" + "=" * 60)
    print("INDEXING PIPELINE SMOKE TESTS")
    print("=" * 60)
    print("\nThese tests verify basic functionality:")
    print("1. Parsing JSON chunk files")
    print("2. Generating embeddings with Qwen3-Embedding-0.6B")
    print("3. Inserting into PostgreSQL with pgvector")

    results = {
        "parse_chunk": await test_parse_chunk(),
        "embedding_generation": await test_embedding_generation(),
        "database_insertion": await test_database_insertion(),
    }

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED - Indexing pipeline is functional")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("⚠️  SOME TESTS FAILED - Check errors above")
        print("=" * 60)
        return 1


def main():
    """Main entry point."""
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
