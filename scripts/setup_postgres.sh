#!/bin/bash
# PostgreSQL + pgvector Docker Setup Script
# Purpose: Initialize Docker container with PostgreSQL and pgvector extension
# Usage: bash scripts/setup_postgres.sh

set -e

echo "=== PostgreSQL + pgvector Docker Setup ==="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is running"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Copying from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example"
    else
        echo "❌ Error: .env.example not found. Please create environment configuration."
        exit 1
    fi
fi

# Load environment variables
source .env

# Start Docker containers
echo ""
echo "Starting PostgreSQL + pgvector container..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker exec langgraph-postgres-vector pg_isready -U ${POSTGRES_USER:-postgres} > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "  Waiting... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Error: PostgreSQL failed to start within timeout"
    echo "Check logs with: docker-compose logs postgres-vector"
    exit 1
fi

# Verify pgvector extension is available
echo ""
echo "Verifying pgvector extension..."
if docker exec langgraph-postgres-vector psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-medical_knowledge} -c "SELECT 1" > /dev/null 2>&1; then
    echo "✓ Database is accessible"
else
    echo "❌ Error: Cannot access database"
    exit 1
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "PostgreSQL Details:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: ${POSTGRES_DB:-medical_knowledge}"
echo "  User: ${POSTGRES_USER:-postgres}"
echo ""
echo "Next steps:"
echo "  1. Run database migrations: python -m app.db.schema migrate"
echo "  2. Index documents: python -m src.embeddings.cli index --input data/chunking_final"
echo "  3. Test search: python test_search.py"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f postgres-vector"
echo "  - Stop database: docker-compose stop"
echo "  - Restart database: docker-compose restart postgres-vector"
echo "  - Remove database (delete data): docker-compose down -v"
echo ""
