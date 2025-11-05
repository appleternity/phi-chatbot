#!/bin/bash
# PostgreSQL Backup Script
# Usage: bash scripts/backup_postgres.sh

set -e

# Configuration
BACKUP_DIR="./backups"
CONTAINER="langgraph-postgres-vector"
DATABASE="medical_knowledge"
USER="postgres"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/medical_knowledge-$DATE.dump"

echo "🔄 PostgreSQL Backup Starting..."
echo ""

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Error: Container '$CONTAINER' is not running"
    echo "   Start with: docker-compose up -d"
    exit 1
fi

# Perform backup
echo "📦 Creating backup..."
echo "   Database: $DATABASE"
echo "   Container: $CONTAINER"
echo "   Output: $BACKUP_FILE"
echo ""

docker exec "$CONTAINER" pg_dump \
  -U "$USER" \
  -Fc \
  --compress=9 \
  "$DATABASE" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup completed successfully"
    echo "   File: $BACKUP_FILE"
    echo "   Size: $SIZE"
    echo ""

    # Create symlink to latest backup
    ln -sf "$(basename "$BACKUP_FILE")" "$BACKUP_DIR/medical_knowledge-latest.dump"
    echo "📌 Latest backup symlink updated"
    echo "   $BACKUP_DIR/medical_knowledge-latest.dump -> $(basename "$BACKUP_FILE")"
else
    echo "❌ Backup failed"
    exit 1
fi

echo ""
echo "✅ Backup complete"
