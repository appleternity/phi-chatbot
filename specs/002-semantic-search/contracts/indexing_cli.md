# CLI Contract: Indexing Pipeline

**Feature**: 002-semantic-search
**Status**: IMMUTABLE (CLI interface must remain stable)
**Purpose**: Define command-line interface for batch indexing of document chunks

---

## Commands

### 1. `index` - Batch Index Document Chunks

**Purpose**: Index all chunks from `data/chunking_final` into PostgreSQL vector database.

**Signature**:
```bash
python -m src.embeddings.cli index \
  --input <directory> \
  --config <embedding_config_json> \
  [--batch-size <int>] \
  [--skip-existing] \
  [--verbose]
```

**Arguments**:
- `--input` (required): Path to directory containing chunk JSON files (e.g., `data/chunking_final`)
- `--config` (required): Path to JSON config file with embedding settings (model, device, batch_size)
- `--batch-size` (optional): Override batch size from config (default: from config)
- `--skip-existing` (optional): Skip chunks already in database (default: False, upsert mode)
- `--verbose` (optional): Enable detailed logging (default: False)

**Output**:
- Progress bar showing indexing status
- Summary: Total chunks processed, successes, failures, skipped
- Error log for failed chunks (written to `indexing_errors.log`)

**Exit Codes**:
- `0`: Success (all chunks indexed)
- `1`: Partial failure (some chunks failed, see error log)
- `2`: Complete failure (no chunks indexed, fatal error)

**Example**:
```bash
# Index all chunks with default config
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --config config/embedding_config.json \
  --verbose

# Skip already-indexed chunks (faster re-runs)
python -m src.embeddings.cli index \
  --input data/chunking_final \
  --config config/embedding_config.json \
  --skip-existing
```

**Example Config** (`config/embedding_config.json`):
```json
{
  "model_name": "Qwen/Qwen3-Embedding-0.6B",
  "device": "mps",
  "batch_size": 16,
  "max_length": 1024,
  "normalize_embeddings": true,
  "instruction": null
}
```

---

### 2. `reindex` - Force Re-indexing of Specific Chunks

**Purpose**: Force re-generation of embeddings for specific chunks (useful for model updates).

**Signature**:
```bash
python -m src.embeddings.cli reindex \
  --chunk-ids <chunk_id1,chunk_id2,...> \
  --config <embedding_config_json> \
  [--verbose]
```

**Arguments**:
- `--chunk-ids` (required): Comma-separated list of chunk IDs to reindex
- `--config` (required): Path to JSON config file with embedding settings
- `--verbose` (optional): Enable detailed logging

**Output**:
- List of reindexed chunks with new timestamps
- Summary: Total reindexed, successes, failures

**Exit Codes**:
- `0`: Success (all specified chunks reindexed)
- `1`: Partial failure (some chunks failed)
- `2`: Complete failure (no chunks reindexed)

**Example**:
```bash
python -m src.embeddings.cli reindex \
  --chunk-ids "02_aripiprazole_chunk_017,02_aripiprazole_chunk_018" \
  --config config/embedding_config.json \
  --verbose
```

---

### 3. `validate` - Validate Indexed Data Quality

**Purpose**: Check database for missing chunks, invalid embeddings, or metadata issues.

**Signature**:
```bash
python -m src.embeddings.cli validate \
  --input <directory> \
  [--check-embeddings] \
  [--verbose]
```

**Arguments**:
- `--input` (required): Path to original chunk directory (for comparison)
- `--check-embeddings` (optional): Validate embedding dimensions and values (default: False)
- `--verbose` (optional): Enable detailed logging

**Output**:
- Validation report: missing chunks, invalid embeddings, metadata mismatches
- Summary: Total chunks in DB vs directory, validation errors

**Exit Codes**:
- `0`: Success (all validation checks passed)
- `3`: Validation failures found (see report)

**Example**:
```bash
python -m src.embeddings.cli validate \
  --input data/chunking_final \
  --check-embeddings \
  --verbose
```

---

### 4. `stats` - Display Indexing Statistics

**Purpose**: Show database statistics (chunk count, embedding dimensions, storage size).

**Signature**:
```bash
python -m src.embeddings.cli stats [--verbose]
```

**Arguments**:
- `--verbose` (optional): Show detailed per-document statistics

**Output**:
- Total chunks indexed
- Embedding dimension (should be 1024)
- Database storage size (MB)
- Chunks per source document (if --verbose)

**Exit Codes**:
- `0`: Success

**Example**:
```bash
python -m src.embeddings.cli stats --verbose
```

---

## Contract Test Requirements

### 1. Command Availability
- All 4 commands (index, reindex, validate, stats) are accessible via `python -m src.embeddings.cli`
- Invalid commands show help message and exit with code 2

### 2. Argument Validation
- Missing required arguments (--input, --config) exit with code 2 and show usage
- Invalid paths (non-existent directories) exit with code 2 and show error
- Invalid config JSON exits with code 2 and shows parse error

### 3. Output Format
- Progress bar updates during indexing (tqdm or rich)
- Summary statistics printed at end of each command
- Verbose mode prints per-chunk details
- Error messages written to stderr

### 4. Error Handling
- Database connection failures exit with code 2 (fatal error)
- Individual chunk failures logged but don't stop processing (exit code 1)
- MPS device unavailable falls back to CPU (warning, not error)

### 5. Exit Code Consistency
- Exit code 0: Complete success
- Exit code 1: Partial success (some failures)
- Exit code 2: Fatal error (no progress made)
- Exit code 3: Validation failures (validate command only)

### 6. Configuration Validation
- Config JSON validated against EmbeddingConfig Pydantic model
- Invalid device (not "mps", "cuda", "cpu") exits with code 2
- Invalid batch_size (not in [1, 128]) exits with code 2

### 7. Performance Requirements
- Index 500 chunks in under 30 minutes on Apple Silicon
- Progress bar updates at least every 5 chunks
- Batch processing uses configured batch_size (no hardcoded values)

### 8. Idempotency
- Running `index` twice with `--skip-existing` skips already-indexed chunks
- Running `reindex` with same chunk_ids produces same embeddings (deterministic)

**Test Location**: tests/integration/test_indexing_cli.py

---

## Implementation Checklist

- [ ] Implement CLI using Typer (type-safe argument parsing)
- [ ] Add progress bars with tqdm or rich
- [ ] Implement error logging to `indexing_errors.log`
- [ ] Validate config JSON with Pydantic before processing
- [ ] Test all exit codes (0, 1, 2, 3)
- [ ] Write integration tests for each command
- [ ] Document CLI in project README
