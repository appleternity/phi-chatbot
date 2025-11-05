-- Initialize pgvector extension and create schema
-- This script runs automatically when the Docker container is first created

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create vector_chunks table
CREATE TABLE IF NOT EXISTS vector_chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    chapter_title TEXT,
    section_title TEXT,
    subsection_title TEXT[],  -- Array of subsection titles
    summary TEXT,
    token_count INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,  -- pgvector type for 1024-dimensional embeddings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create metadata indexes (HNSW index created AFTER bulk data insertion for better performance)
CREATE INDEX IF NOT EXISTS idx_source_document ON vector_chunks(source_document);
CREATE INDEX IF NOT EXISTS idx_chapter_title ON vector_chunks(chapter_title);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_vector_chunks_updated_at
    BEFORE UPDATE ON vector_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (if using specific user)
-- GRANT ALL PRIVILEGES ON DATABASE medical_knowledge TO medical_rag_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medical_rag_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO medical_rag_user;
