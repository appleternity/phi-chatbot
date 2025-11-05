# PostgreSQL Backup & Restore Scripts

Shell scripts for backing up and restoring the `medical_knowledge` PostgreSQL database with pgvector extension.

## Overview

This directory contains two scripts:

1. **`backup_postgres.sh`** - Simple database backup script
2. **`setup_postgres_with_file.sh`** - Complete database setup and restore from backup

## Prerequisites

Before using these scripts, ensure you have:

- **Docker** installed and running
- **PostgreSQL container** running (`langgraph-postgres-vector`)
- **Backup file** (for restore script only)

### Starting the PostgreSQL Container

```bash
# From project root
docker-compose up -d

# Verify container is running
docker ps | grep postgres-vector
```

## Scripts

### 1. backup_postgres.sh

**Purpose**: Create a backup of the `medical_knowledge` database.

**Usage**:

```bash
# Run from project root
bash scripts/backup_postgres.sh
```

**What it does**:
1. Creates `backups/` directory if it doesn't exist
2. Checks if PostgreSQL container is running
3. Dumps database to `backups/medical_knowledge-YYYYMMDD-HHMMSS.dump`
4. Creates symlink `backups/medical_knowledge-latest.dump` → most recent backup
5. Displays backup file size

**Output format**: Custom compressed format (`pg_dump -Fc --compress=9`)

**Example output**:

```
🔄 PostgreSQL Backup Starting...

📦 Creating backup...
   Database: medical_knowledge
   Container: langgraph-postgres-vector
   Output: ./backups/medical_knowledge-20250105-143022.dump

✅ Backup completed successfully
   File: ./backups/medical_knowledge-20250105-143022.dump
   Size: 45M

📌 Latest backup symlink updated
   ./backups/medical_knowledge-latest.dump -> medical_knowledge-20250105-143022.dump

✅ Backup complete
```

### 2. setup_postgres_with_file.sh

**Purpose**: Complete database setup from clean slate and restore data from backup.

**Usage**:

```bash
# Run from project root
bash scripts/setup_postgres_with_file.sh <backup_file>

# Examples:
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-20250105-143022.dump
```

**What it does**:
1. Validates backup file exists
2. Checks if PostgreSQL container is running
3. Drops existing `medical_knowledge` database (if exists)
4. Creates new `medical_knowledge` database
5. Installs `pgvector` extension
6. Creates database schema (tables and indexes) using direct SQL commands
7. Restores data from backup file
8. Runs `ANALYZE` to update query statistics for optimal performance
9. Verifies restoration (chunk count, document count, database size)

**Example output**:

```
🔄 PostgreSQL Setup and Restore Starting...

📁 Backup file: backups/medical_knowledge-latest.dump
   Size: 45M

🗑️  Step 1: Dropping existing database (if exists)...
   ✓ Database dropped

🏗️  Step 2: Creating new database...
   ✓ Database 'medical_knowledge' created

🔌 Step 3: Installing pgvector extension...
   ✓ pgvector extension installed

📋 Step 4: Creating database schema...
   ✓ Schema migration complete

📦 Step 5: Restoring data from backup...
   This may take a few minutes...
   ✓ Data restore complete

📊 Step 6: Analyzing database (updating query statistics)...
   ✓ Database analysis complete

🔍 Step 7: Verifying restoration...
   ✓ Verification complete

📊 Database Statistics:
   pgvector version: 0.6.0
   Total chunks: 1247
   Total documents: 42
   Database size: 125 MB

✅ PostgreSQL setup and restore complete!

🎯 Next steps:
   - Test a query: python -c "import asyncio; from app.core.postgres_retriever import PostgreSQLRetriever; ..."
   - Run your application: python -m app.main
```

## Common Workflows

### Daily Backup

```bash
# Create a backup (manual)
bash scripts/backup_postgres.sh
```

### Automated Daily Backup (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM (adjust path to your project directory)
0 2 * * * cd /path/to/langgraph && bash scripts/backup_postgres.sh >> backups/backup.log 2>&1
```

### Restore from Backup

```bash
# Using latest backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# Using specific backup
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-20250105-143022.dump
```

### Clone Database to New Machine

```bash
# On source machine
bash scripts/backup_postgres.sh

# Copy backup file to new machine
scp backups/medical_knowledge-latest.dump user@newmachine:/path/to/langgraph/backups/

# On new machine
docker-compose up -d
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump
```

### Test Backup Integrity

```bash
# Create test backup
bash scripts/backup_postgres.sh

# Restore to verify (will overwrite database!)
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# Check data
docker exec langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT COUNT(*) FROM vector_chunks;"
```

## File Locations

### Backups Directory

```
backups/
├── medical_knowledge-20250104-020000.dump
├── medical_knowledge-20250105-020000.dump
├── medical_knowledge-20250106-020000.dump
└── medical_knowledge-latest.dump -> medical_knowledge-20250106-020000.dump
```

**Note**: The `backups/` directory is git-ignored. Backup files are not committed to version control.

### Environment Variables

Both scripts use these default values:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTAINER` | `langgraph-postgres-vector` | PostgreSQL Docker container name |
| `DATABASE` | `medical_knowledge` | Database name |
| `USER` | `postgres` | PostgreSQL user |
| `BACKUP_DIR` | `./backups` | Backup directory (relative to project root) |

To customize, edit the script files directly.

## Troubleshooting

### Container Not Running

**Error**:
```
❌ Error: Container 'langgraph-postgres-vector' is not running
   Start with: docker-compose up -d
```

**Solution**:
```bash
docker-compose up -d
docker ps  # Verify container is running
```

### Backup File Not Found

**Error**:
```
❌ Error: Backup file not found: backups/medical_knowledge-latest.dump
```

**Solution**:
```bash
# Check available backups
ls -lh backups/

# Create a new backup
bash scripts/backup_postgres.sh

# Use correct backup file path
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-YYYYMMDD-HHMMSS.dump
```

### Permission Denied

**Error**:
```
bash: scripts/backup_postgres.sh: Permission denied
```

**Solution**:
```bash
# Make script executable
chmod +x scripts/backup_postgres.sh
chmod +x scripts/setup_postgres_with_file.sh

# Or run with bash explicitly
bash scripts/backup_postgres.sh
```

### Schema Creation Fails

**Error**:
```
ERROR: type "vector" does not exist
```

**Solution**: pgvector extension must be installed first (Step 3 in the script does this automatically). If this error occurs, the extension installation failed:

```bash
# Manually install pgvector extension
docker exec langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "CREATE EXTENSION vector;"

# Verify extension is installed
docker exec langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

### Restore Takes Too Long

**Symptom**: Restore step hangs or takes >30 minutes

**Solutions**:
```bash
# Check container logs
docker logs langgraph-postgres-vector

# Monitor PostgreSQL activity
docker exec langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "SELECT * FROM pg_stat_activity;"

# For very large databases, restore manually with parallel jobs
docker cp backups/medical_knowledge-latest.dump langgraph-postgres-vector:/tmp/backup.dump
docker exec langgraph-postgres-vector pg_restore \
  -U postgres \
  -d medical_knowledge \
  -j 4 \
  /tmp/backup.dump
```

## Advanced Usage

### Backup to Remote Storage

```bash
# Backup and upload to S3
bash scripts/backup_postgres.sh
aws s3 cp backups/medical_knowledge-latest.dump s3://my-bucket/postgres-backups/

# Download from S3 and restore
aws s3 cp s3://my-bucket/postgres-backups/medical_knowledge-latest.dump backups/
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump
```

### Backup Retention

```bash
# Delete backups older than 30 days
find backups/ -name "medical_knowledge-*.dump" -type f -mtime +30 -delete

# Keep only last 10 backups
ls -t backups/medical_knowledge-*.dump | tail -n +11 | xargs rm -f
```

### Schema-Only Backup

For development environments (no data):

```bash
docker exec langgraph-postgres-vector pg_dump \
  -U postgres \
  -Fc \
  --schema-only \
  medical_knowledge > backups/schema-only.dump
```

## What is ANALYZE?

**ANALYZE** is a PostgreSQL command that collects statistics about table contents to help the query planner make better decisions.

- **What it does**: Scans tables and gathers statistics (row counts, data distribution, common values)
- **Why after restore**: Restored databases have outdated statistics, leading to slow queries
- **Impact**: Read-only operation, takes seconds, significantly improves query performance
- **When to run**: After restore, after large data imports, periodically in production

```bash
# Manual ANALYZE (if needed)
docker exec langgraph-postgres-vector psql -U postgres -d medical_knowledge -c "ANALYZE;"
```

## Security Notes

- **Backup files contain sensitive data** - store securely
- **No passwords in scripts** - uses Docker exec (inherits container auth)
- **Local backups only** - does not transmit data over network
- **Git-ignored** - `backups/` directory excluded from version control

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Docker container logs: `docker logs langgraph-postgres-vector`
3. Verify PostgreSQL connection: `docker exec langgraph-postgres-vector psql -U postgres -l`
4. Check project documentation: `CLAUDE.md`
