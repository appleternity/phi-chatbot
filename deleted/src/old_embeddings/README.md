# Deprecated: Old Embedding Pipeline

**Date Deprecated**: 2025-11-12

## What Was This?

This was the original single-stage embedding pipeline that directly indexed chunks to the database:

```
Raw chunks → Generate embeddings → Insert to DB (all in one pass)
```

## Why Deprecated?

Replaced with a superior two-stage pipeline:

```
Stage 1: Raw chunks → Generate embeddings → Save to Parquet
Stage 2: Read Parquet → Create table with known dimension → Bulk insert
```

### Benefits of New Architecture:

1. **Data Durability**: Parquet file = source of truth, can regenerate DB anytime
2. **Separation of Concerns**: Embedding generation (GPU-intensive) separate from DB ingestion (I/O-intensive)
3. **Flexibility**: Can ingest to multiple databases, test different schemas
4. **Known Dimensions**: Read dimension from Parquet metadata before table creation
5. **Inspectable**: Easy to inspect embeddings with `pd.read_parquet()`
6. **Batch Efficiency**: PostgreSQL COPY for bulk insert (10-100x faster)

## New Commands

**Stage 1: Generate Embeddings**
```bash
python -m src.embeddings.generate_embeddings \
    --input data/chunking_final \
    --output data/embeddings.parquet
```

**Stage 2: Ingest to Database**
```bash
python -m src.embeddings.ingest_embeddings \
    --input data/embeddings.parquet \
    --table-name vector_chunks
```

## Files Moved Here

- `cli.py` - Old CLI interface
- `indexer.py` - Old DocumentIndexer class
- `models.py` - Old data models

**Do not use these files**. They are kept for reference only.
