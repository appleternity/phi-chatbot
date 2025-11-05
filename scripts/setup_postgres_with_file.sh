#!/bin/bash
# PostgreSQL Setup and Restore Script
# Usage: bash scripts/setup_postgres_with_file.sh <backup_file>

set -e

# Configuration
CONTAINER="langgraph-postgres-vector"
DATABASE="medical_knowledge"
USER="postgres"

echo "🔄 PostgreSQL Setup and Restore Starting..."
echo ""

# Check if backup file argument is provided
if [ -z "$1" ]; then
    echo "❌ Error: No backup file specified"
    echo ""
    echo "Usage: bash scripts/setup_postgres_with_file.sh <backup_file>"
    echo "Example: bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "📁 Backup file: $BACKUP_FILE"
echo "   Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Error: Container '$CONTAINER' is not running"
    echo "   Start with: docker-compose up -d"
    exit 1
fi

# Step 1: Drop existing database (if exists)
echo "🗑️  Step 1: Dropping existing database (if exists)..."
docker exec "$CONTAINER" psql -U "$USER" -c "DROP DATABASE IF EXISTS $DATABASE;" 2>/dev/null || true
echo "   ✓ Database dropped"
echo ""

# Step 2: Create new database
echo "🏗️  Step 2: Creating new database..."
docker exec "$CONTAINER" psql -U "$USER" -c "CREATE DATABASE $DATABASE;"
echo "   ✓ Database '$DATABASE' created"
echo ""

# Step 3: Install pgvector extension
echo "🔌 Step 3: Installing pgvector extension..."
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "CREATE EXTENSION vector;"
echo "   ✓ pgvector extension installed"
echo ""

# Step 4: Create database schema (tables and indexes)
echo "📋 Step 4: Creating database schema..."

# Create schema_metadata table
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "
CREATE TABLE IF NOT EXISTS schema_metadata (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);"

# Create vector_chunks table (1024 dimensions for Qwen3-Embedding-0.6B)
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "
CREATE TABLE IF NOT EXISTS vector_chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    chapter_title TEXT,
    section_title TEXT,
    subsection_title TEXT[],
    summary TEXT,
    token_count INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);"

# Create HNSW index for cosine similarity search
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "
CREATE INDEX IF NOT EXISTS idx_embedding_cosine
ON vector_chunks
USING hnsw (embedding vector_cosine_ops);"

# Create metadata indexes
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "
CREATE INDEX IF NOT EXISTS idx_source_document
ON vector_chunks(source_document);

CREATE INDEX IF NOT EXISTS idx_chapter_title
ON vector_chunks(chapter_title);"

# Store schema metadata
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "
INSERT INTO schema_metadata (key, value) VALUES ('embedding_dimension', '1024')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO schema_metadata (key, value) VALUES ('vector_type', 'vector')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO schema_metadata (key, value) VALUES ('index_type', 'HNSW (vector_cosine_ops)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO schema_metadata (key, value) VALUES ('storage_info', '4 bytes/dim, 4.0 KB/vector')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;"

echo "   ✓ Schema migration complete"
echo ""

# Step 5: Restore backup
echo "📦 Step 5: Restoring data from backup..."
echo "   This may take a few minutes..."
cat "$BACKUP_FILE" | docker exec -i "$CONTAINER" pg_restore \
  -U "$USER" \
  -d "$DATABASE" \
  --verbose 2>&1 | grep -E "(processing|restoring)" | head -20 || true
echo "   ✓ Data restore complete"
echo ""

# Step 6: Run ANALYZE to update query statistics
echo "📊 Step 6: Analyzing database (updating query statistics)..."
docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -c "ANALYZE;"
echo "   ✓ Database analysis complete"
echo ""

# Step 7: Verify restoration
echo "🔍 Step 7: Verifying restoration..."

# Check pgvector extension
PGVECTOR_VERSION=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -t -c \
  "SELECT extversion FROM pg_extension WHERE extname = 'vector';" | xargs)

# Check chunk count
CHUNK_COUNT=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -t -c \
  "SELECT COUNT(*) FROM vector_chunks;" | xargs)

# Check document count
DOC_COUNT=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -t -c \
  "SELECT COUNT(DISTINCT source_document) FROM vector_chunks;" | xargs)

# Check database size
DB_SIZE=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DATABASE" -t -c \
  "SELECT pg_size_pretty(pg_database_size('$DATABASE'));" | xargs)

echo "   ✓ Verification complete"
echo ""
echo "📊 Database Statistics:"
echo "   pgvector version: $PGVECTOR_VERSION"
echo "   Total chunks: $CHUNK_COUNT"
echo "   Total documents: $DOC_COUNT"
echo "   Database size: $DB_SIZE"
echo ""

echo "✅ PostgreSQL setup and restore complete!"
echo ""
echo "🎯 Next steps:"
echo "   - Test a query: python -c \"import asyncio; from app.core.postgres_retriever import PostgreSQLRetriever; ...\""
echo "   - Run your application: python -m app.main"
