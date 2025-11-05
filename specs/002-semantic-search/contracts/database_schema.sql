-- Database Schema Contract: PostgreSQL + pgvector
-- Feature: 002-semantic-search
-- Status: IMMUTABLE (changing schema requires migration)
-- Purpose: Define vector_chunks table for semantic search

-- Enable pgvector extension (required for vector operations)
CREATE EXTENSION IF NOT EXISTS vector;

-- Main table: vector_chunks
-- Stores document chunks with 1024-dimensional embeddings
CREATE TABLE IF NOT EXISTS vector_chunks (
    -- Primary key: unique chunk identifier from source JSON
    chunk_id VARCHAR(255) PRIMARY KEY,

    -- Source metadata (from chunking pipeline)
    source_document VARCHAR(255) NOT NULL,  -- e.g., "02_aripiprazole"
    chapter_title TEXT,                     -- e.g., "Pharmacology"
    section_title TEXT,                     -- e.g., "Mechanism of Action"
    subsection_title TEXT[],                -- e.g., ["Dopamine Receptors", "Serotonin Receptors"]
    summary TEXT,                           -- Brief content summary (10-200 chars)
    token_count INTEGER NOT NULL CHECK (token_count > 0),

    -- Content and embedding
    chunk_text TEXT NOT NULL CHECK (length(chunk_text) >= 10),  -- Full text for RAG
    embedding vector(1024) NOT NULL,        -- Qwen3-Embedding-0.6B output (1024 dims)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- HNSW index for fast cosine similarity search
-- Performance: ~1.5ms query time (vs 650ms sequential scan)
-- Build time: After bulk insertion (faster than building incrementally)
CREATE INDEX IF NOT EXISTS idx_vector_chunks_embedding
    ON vector_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Metadata indexes for filtering
CREATE INDEX IF NOT EXISTS idx_vector_chunks_source_document
    ON vector_chunks(source_document);

CREATE INDEX IF NOT EXISTS idx_vector_chunks_chapter_title
    ON vector_chunks(chapter_title);

-- Trigger: Update updated_at timestamp on modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_vector_chunks_updated_at
    BEFORE UPDATE ON vector_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Contract Test Requirements
-- 1. Schema Validation:
--    - Table exists with correct name (vector_chunks)
--    - All columns have correct types and constraints
--    - Primary key on chunk_id
--    - NOT NULL constraints on required fields
--
-- 2. Index Validation:
--    - HNSW index exists on embedding column
--    - Uses vector_cosine_ops for cosine similarity
--    - Metadata indexes exist (source_document, chapter_title)
--
-- 3. Vector Operations:
--    - pgvector extension enabled
--    - vector(1024) type supports cosine similarity (<=>)
--    - HNSW index accelerates similarity queries
--
-- 4. Data Integrity:
--    - chunk_id uniqueness enforced (PRIMARY KEY)
--    - token_count > 0 enforced (CHECK constraint)
--    - chunk_text >= 10 chars enforced (CHECK constraint)
--    - subsection_title supports array storage (TEXT[])
--
-- 5. Timestamp Behavior:
--    - created_at defaults to NOW() on INSERT
--    - updated_at auto-updates on UPDATE (trigger)
--
-- Test Location: tests/contract/test_database_schema.py

-- Example Queries
-- Insert a chunk:
-- INSERT INTO vector_chunks (chunk_id, source_document, chapter_title, section_title,
--                            subsection_title, summary, token_count, chunk_text, embedding)
-- VALUES ('02_aripiprazole_chunk_017', '02_aripiprazole', 'Pharmacology', 'Mechanism of Action',
--         ARRAY['Dopamine Receptors', 'Serotonin Receptors'],
--         'Aripiprazole acts as partial agonist at D2 and 5-HT1A receptors', 342,
--         'Aripiprazole is a partial agonist...', '[0.123, 0.456, ...]');

-- Semantic search (cosine similarity):
-- SELECT chunk_id, chunk_text, 1 - (embedding <=> '[0.123, 0.456, ...]') AS similarity
-- FROM vector_chunks
-- ORDER BY embedding <=> '[0.123, 0.456, ...]'
-- LIMIT 20;

-- Filtered search:
-- SELECT chunk_id, chunk_text, 1 - (embedding <=> '[0.123, 0.456, ...]') AS similarity
-- FROM vector_chunks
-- WHERE source_document = '02_aripiprazole'
-- ORDER BY embedding <=> '[0.123, 0.456, ...]'
-- LIMIT 20;
