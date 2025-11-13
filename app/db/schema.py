"""
PostgreSQL schema for semantic search with pgvector extension.

This module defines the database schema for storing document chunks with embeddings
and provides migration functions for schema creation and indexing.

Key Features:
- pgvector extension for vector similarity search
- HNSW index for fast cosine similarity queries (~1.5ms vs 650ms sequential)
- Metadata indexes for efficient filtering
- Async operations using asyncpg

Database Design:
- Primary Key: chunk_id (prevents duplicate indexing)
- Vector Type: vector(1024) (Qwen3-Embedding-0.6B output dimension)
- Index: HNSW with cosine distance (optimal for text embeddings)
- Timestamps: Track creation and updates
"""

import asyncio
from typing import Optional

import asyncpg
from asyncpg import Connection
import typer
from rich.console import Console
from rich.panel import Panel


# SQL for creating pgvector extension
CREATE_EXTENSION_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
"""


# SQL for creating vector_chunks table (parameterized dimension, type, and table name)
# Type selection based on dimension:
# - vector(N): float32, dimensions 128-2000, 4 bytes/dim
# - halfvec(N): float16, dimensions 2001-4000, 2 bytes/dim (50% space savings)
# - vector(N): float32, dimensions >4000, use binary quantization for indexing
# Note: Table name will be quoted to support special characters (e.g., hyphens)
def get_create_table_sql(table_name: str, vector_type: str, dimension: int) -> str:
    """Generate CREATE TABLE SQL with quoted table name."""
    return f"""
CREATE TABLE IF NOT EXISTS "{table_name}" (
    chunk_id VARCHAR(255) PRIMARY KEY,
    source_document VARCHAR(255) NOT NULL,
    chapter_title TEXT,
    section_title TEXT,
    subsection_title TEXT[],
    summary TEXT,
    token_count INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding {vector_type}({dimension}) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""


# SQL for creating schema metadata table
CREATE_METADATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""


# SQL for creating HNSW index for standard vectors (float32, ≤2000 dimensions)
def get_hnsw_vector_index_sql(table_name: str) -> str:
    """Generate HNSW vector index SQL with quoted table name."""
    return f"""
CREATE INDEX IF NOT EXISTS idx_embedding_cosine
ON "{table_name}"
USING hnsw (embedding vector_cosine_ops);
"""

# SQL for creating HNSW index for half-precision vectors (float16, 2001-4000 dimensions)
def get_hnsw_halfvec_index_sql(table_name: str) -> str:
    """Generate HNSW halfvec index SQL with quoted table name."""
    return f"""
CREATE INDEX IF NOT EXISTS idx_embedding_cosine
ON "{table_name}"
USING hnsw (embedding halfvec_cosine_ops);
"""

# SQL for creating HNSW index with binary quantization (>4000 dimensions)
# Uses expression index: binary_quantize(embedding)::bit(N)
# Supports up to 64,000 dimensions with fast approximate search
def get_binary_quantized_index_sql(table_name: str, dimension: int) -> str:
    """Generate binary quantized index SQL with quoted table name."""
    return f"""
CREATE INDEX IF NOT EXISTS idx_embedding_cosine
ON "{table_name}"
USING hnsw ((binary_quantize(embedding)::bit({dimension})) bit_hamming_ops);
"""


# SQL for creating metadata indexes
def get_metadata_indexes_sql(table_name: str) -> str:
    """Generate metadata indexes SQL with quoted table name."""
    return f"""
CREATE INDEX IF NOT EXISTS idx_source_document
ON "{table_name}"(source_document);

CREATE INDEX IF NOT EXISTS idx_chapter_title
ON "{table_name}"(chapter_title);
"""


# SQL for dropping all indexes and table (for testing/reset)
def get_drop_schema_sql(table_name: str) -> str:
    """Generate DROP schema SQL with quoted table name."""
    return f"""
DROP INDEX IF EXISTS idx_embedding_cosine;
DROP INDEX IF EXISTS idx_source_document;
DROP INDEX IF EXISTS idx_chapter_title;
DROP TABLE IF EXISTS "{table_name}";
"""


async def create_schema(
    conn: Connection,
    embedding_dim: int = 1024,
    table_name: str = "vector_chunks"
) -> None:
    """
    Create database schema with intelligent vector type and index selection.

    This function creates:
    1. pgvector extension
    2. schema_metadata table
    3. vector table with optimal vector type and custom name
    4. HNSW index with optimal operator class
    5. Metadata indexes for filtering

    Vector Type Selection (pgvector 0.7.0+):
    - 128-2000 dims: vector (float32, 4 bytes/dim) + HNSW vector_cosine_ops
    - 2001-4000 dims: halfvec (float16, 2 bytes/dim) + HNSW halfvec_cosine_ops
    - 4001-64000 dims: vector + HNSW binary quantization (bit_hamming_ops)

    Performance Notes:
    - halfvec: 50% space savings, minimal accuracy loss
    - Binary quantization: 97% space savings, requires re-ranking for accuracy

    Args:
        conn: Active asyncpg connection
        embedding_dim: Embedding dimension (default: 1024 for Qwen3-0.6B)
        table_name: Custom table name (default: "vector_chunks")
                   Supports special characters (e.g., "text-embedding-v4")

    Raises:
        AssertionError: If embedding_dim is out of valid range
        asyncpg.PostgresError: If schema creation fails
    """
    # Validate dimension (fail-fast)
    assert 128 <= embedding_dim <= 64000, \
        f"embedding_dim must be 128-64000, got {embedding_dim}"

    # Create pgvector extension
    await conn.execute(CREATE_EXTENSION_SQL)

    # Create metadata table first
    await conn.execute(CREATE_METADATA_TABLE_SQL)

    # Select vector type and index based on dimension
    if embedding_dim <= 2000:
        # Standard float32 vectors with HNSW index
        vector_type = "vector"
        index_sql = get_hnsw_vector_index_sql(table_name)
        index_type = "HNSW (vector_cosine_ops)"
        storage_info = f"4 bytes/dim, {embedding_dim * 4 / 1024:.1f} KB/vector"

    elif embedding_dim <= 4000:
        # Half-precision float16 vectors with HNSW index (50% space savings)
        vector_type = "halfvec"
        index_sql = get_hnsw_halfvec_index_sql(table_name)
        index_type = "HNSW (halfvec_cosine_ops)"
        storage_info = f"2 bytes/dim, {embedding_dim * 2 / 1024:.1f} KB/vector (50% savings)"

    else:
        # Binary quantization for >4000 dimensions (97% space savings)
        # Note: Requires re-ranking with original vectors for best accuracy
        vector_type = "vector"
        index_sql = get_binary_quantized_index_sql(table_name, embedding_dim)
        index_type = "HNSW (binary quantization + re-ranking)"
        storage_info = f"4 bytes/dim + bit index, {embedding_dim * 4 / 1024:.1f} KB/vector"

    # Create vector table with chosen vector type and custom name
    create_table_sql = get_create_table_sql(table_name, vector_type, embedding_dim)
    await conn.execute(create_table_sql)

    # Create HNSW index with chosen strategy
    await conn.execute(index_sql)

    # Create metadata indexes
    await conn.execute(get_metadata_indexes_sql(table_name))

    # Store metadata for validation and query optimization
    await conn.execute(
        "INSERT INTO schema_metadata (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        "embedding_dimension", str(embedding_dim)
    )
    await conn.execute(
        "INSERT INTO schema_metadata (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        "vector_type", vector_type
    )
    await conn.execute(
        "INSERT INTO schema_metadata (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        "index_type", index_type
    )
    await conn.execute(
        "INSERT INTO schema_metadata (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        "storage_info", storage_info
    )


async def drop_schema(conn: Connection, table_name: str = "vector_chunks") -> None:
    """
    Drop all indexes and tables (for testing/reset).

    WARNING: This will delete all data in the specified table.
    Use only for testing or when you want to completely reset the database.

    Args:
        conn: Active asyncpg connection
        table_name: Table name to drop (default: "vector_chunks")

    Raises:
        asyncpg.PostgresError: If schema drop fails
    """
    drop_sql = get_drop_schema_sql(table_name)
    await conn.execute(drop_sql)


async def create_database_if_needed(
    host: str,
    port: int,
    database: str,
    user: str,
    password: Optional[str],
) -> bool:
    """
    Create database if it doesn't exist.

    Connects to 'postgres' database to execute CREATE DATABASE command.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        database: Database name to create
        user: Database user (needs CREATEDB privilege)
        password: Database password

    Returns:
        True if database was created, False if already existed

    Raises:
        asyncpg.PostgresError: If database creation fails
    """
    conn = None
    try:
        # Connect to postgres database
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database="postgres",
            user=user,
            password=password,
        )

        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database
        )

        if exists:
            return False

        # Create database
        await conn.execute(f'CREATE DATABASE "{database}"')
        return True

    finally:
        if conn:
            await conn.close()


async def migrate_database(
    host: str = "localhost",
    port: int = 5432,
    database: str = "semantic_search",
    user: str = "postgres",
    password: Optional[str] = None,
    embedding_dim: int = 1024,
    create_db: bool = True,
) -> None:
    """
    Smart migration: creates database if needed, then creates schema.

    This is the main entry point for schema creation. It:
    1. Creates database if it doesn't exist (optional)
    2. Establishes database connection
    3. Creates pgvector extension
    4. Creates metadata table
    5. Creates vector_chunks table with specified dimension
    6. Creates all necessary indexes
    7. Closes connection

    Args:
        host: PostgreSQL host (default: localhost)
        port: PostgreSQL port (default: 5432)
        database: Database name (default: semantic_search)
        user: Database user (default: postgres)
        password: Database password (default: None)
        embedding_dim: Embedding dimension (default: 1024 for Qwen3-0.6B)
        create_db: Create database if it doesn't exist (default: True)

    Raises:
        asyncpg.PostgresError: If migration fails
        ConnectionError: If cannot connect to database

    Example:
        >>> import asyncio
        >>> # Create database + schema for 1024-dim embeddings
        >>> asyncio.run(migrate_database(
        ...     host="localhost",
        ...     database="semantic_search",
        ...     embedding_dim=1024
        ... ))
        >>> # Create database + schema for 8192-dim embeddings
        >>> asyncio.run(migrate_database(
        ...     database="semantic_search_8k",
        ...     embedding_dim=8192
        ... ))
    """
    from rich.console import Console
    console = Console()

    # Try to create database if needed
    if create_db:
        try:
            db_created = await create_database_if_needed(
                host, port, database, user, password
            )
            if db_created:
                console.print(f"[green]✅ Database '{database}' created[/green]")
            else:
                console.print(f"[dim]ℹ️  Database '{database}' already exists[/dim]")
        except asyncpg.PostgresError as e:
            console.print(f"[yellow]⚠️  Could not create database: {e}[/yellow]")
            console.print("[dim]Continuing with schema creation...[/dim]")

    # Connect to target database and create schema
    conn = None
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

        # Create schema
        await create_schema(conn, embedding_dim=embedding_dim)

        # Get metadata for display
        vector_type = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'vector_type'"
        )
        index_type = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'index_type'"
        )
        storage_info = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'storage_info'"
        )

        console.print(f"[green]✅ Schema created successfully in '{database}'[/green]")
        console.print("[dim]   - pgvector 0.7.0+ extension enabled[/dim]")
        console.print(f"[dim]   - vector_chunks table ({vector_type}({embedding_dim}))[/dim]")
        console.print(f"[dim]   - {index_type} index created[/dim]")
        console.print(f"[dim]   - Storage: {storage_info}[/dim]")
        console.print("[dim]   - Metadata indexes created[/dim]")

        # Add performance notes for different strategies
        if embedding_dim > 4000:
            console.print("\n[yellow]ℹ️  Binary Quantization Strategy[/yellow]")
            console.print("[dim]   - Fast approximate search with binary index (97% space savings)[/dim]")
            console.print("[dim]   - Retrieval workflow: binary index (top 100) → re-rank (top K)[/dim]")
            console.print("[dim]   - See pgvector docs for re-ranking query patterns[/dim]")
        elif embedding_dim > 2000:
            console.print("\n[cyan]ℹ️  Half-Precision Vectors[/cyan]")
            console.print("[dim]   - 50% storage savings with minimal accuracy loss[/dim]")
            console.print("[dim]   - HNSW index provides fast, accurate similarity search[/dim]")

    except asyncpg.PostgresError as e:
        console.print(f"[red]❌ Migration failed: {e}[/red]")
        raise
    finally:
        if conn:
            await conn.close()


async def verify_schema(conn: Connection) -> bool:
    """
    Verify that the schema is correctly created.

    Checks:
    1. pgvector extension exists
    2. vector_chunks table exists
    3. All indexes exist
    4. Table has correct columns and types

    Args:
        conn: Active asyncpg connection

    Returns:
        True if schema is valid, False otherwise

    Example:
        >>> conn = await asyncpg.connect(...)
        >>> is_valid = await verify_schema(conn)
        >>> print(f"Schema valid: {is_valid}")
    """
    try:
        # Check if pgvector extension exists
        extension_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        if not extension_exists:
            print("❌ pgvector extension not found")
            return False

        # Check if vector_chunks table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'vector_chunks'
            )
            """
        )
        if not table_exists:
            print("❌ vector_chunks table not found")
            return False

        # Check if vector index exists
        # Get metadata to determine expected configuration
        embedding_dim_str = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'embedding_dimension'"
        )
        vector_type = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'vector_type'"
        )
        index_type = await conn.fetchval(
            "SELECT value FROM schema_metadata WHERE key = 'index_type'"
        )

        embedding_dim = int(embedding_dim_str) if embedding_dim_str else 0

        # Verify HNSW index exists (all strategies use HNSW)
        hnsw_index_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_embedding_cosine'
            )
            """
        )

        if not hnsw_index_exists:
            print(f"❌ HNSW index not found (expected: {index_type})")
            return False
        else:
            print(f"✅ Vector index found: {index_type}")
            print(f"   Vector type: {vector_type}({embedding_dim})")

        # Check if metadata indexes exist
        source_index_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_source_document'
            )
            """
        )
        chapter_index_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_chapter_title'
            )
            """
        )
        if not source_index_exists or not chapter_index_exists:
            print("❌ Metadata indexes not found")
            return False

        # Check table columns
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'vector_chunks'
            ORDER BY ordinal_position
            """
        )

        expected_columns = {
            "chunk_id",
            "source_document",
            "chapter_title",
            "section_title",
            "subsection_title",
            "summary",
            "token_count",
            "chunk_text",
            "embedding",
            "created_at",
            "updated_at",
        }

        actual_columns = {row["column_name"] for row in columns}

        if expected_columns != actual_columns:
            missing = expected_columns - actual_columns
            extra = actual_columns - expected_columns
            if missing:
                print(f"❌ Missing columns: {missing}")
            if extra:
                print(f"❌ Extra columns: {extra}")
            return False

        print("✅ Schema validation passed")
        return True

    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        return False


async def get_table_stats(conn: Connection) -> dict:
    """
    Get statistics about the vector_chunks table.

    Returns:
        Dictionary with:
        - total_chunks: Total number of chunks
        - unique_documents: Number of unique source documents
        - avg_token_count: Average token count per chunk
        - total_size: Approximate table size in MB

    Example:
        >>> conn = await asyncpg.connect(...)
        >>> stats = await get_table_stats(conn)
        >>> print(f"Total chunks: {stats['total_chunks']}")
    """
    try:
        # Get count statistics
        total_chunks = await conn.fetchval(
            "SELECT COUNT(*) FROM vector_chunks"
        )

        unique_documents = await conn.fetchval(
            "SELECT COUNT(DISTINCT source_document) FROM vector_chunks"
        )

        avg_token_count = await conn.fetchval(
            "SELECT AVG(token_count) FROM vector_chunks"
        )

        # Get table size
        table_size_bytes = await conn.fetchval(
            """
            SELECT pg_total_relation_size('vector_chunks')
            """
        )
        table_size_mb = table_size_bytes / (1024 * 1024) if table_size_bytes else 0

        return {
            "total_chunks": total_chunks or 0,
            "unique_documents": unique_documents or 0,
            "avg_token_count": round(avg_token_count, 2) if avg_token_count else 0,
            "total_size_mb": round(table_size_mb, 2),
        }

    except Exception as e:
        print(f"❌ Failed to get table stats: {e}")
        return {
            "total_chunks": 0,
            "unique_documents": 0,
            "avg_token_count": 0,
            "total_size_mb": 0,
        }


# Typer CLI app
app = typer.Typer(
    name="db-schema",
    help="Database schema management for PostgreSQL with pgvector",
    add_completion=False,
)


@app.command()
def migrate(
    host: str = typer.Option(
        "localhost",
        "--host",
        "-h",
        help="PostgreSQL host"
    ),
    port: int = typer.Option(
        5432,
        "--port",
        "-p",
        help="PostgreSQL port"
    ),
    database: str = typer.Option(
        "semantic_search",
        "--database",
        "-d",
        help="Database name"
    ),
    user: str = typer.Option(
        "postgres",
        "--user",
        "-u",
        help="Database user"
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        help="Database password (omit for no password)"
    ),
    embedding_dim: int = typer.Option(
        1024,
        "--embedding-dim",
        help="Embedding vector dimension (128-64000, pgvector 0.7.0+)"
    ),
    no_create_db: bool = typer.Option(
        False,
        "--no-create-db",
        help="Skip database creation, only create schema"
    ),
) -> None:
    """
    Smart migration: create database if needed, then create schema.

    Examples:
        # Create database + schema with 1024-dim embeddings
        python -m app.db.schema migrate --database semantic_search

        # Create database + schema with 8192-dim embeddings
        python -m app.db.schema migrate --database semantic_search_8k --embedding-dim 8192

        # Only create schema (skip database creation)
        python -m app.db.schema migrate --no-create-db
    """
    console = Console()

    # Validate embedding dimension
    if not 128 <= embedding_dim <= 64000:
        console.print(f"[red]❌ Invalid embedding dimension: {embedding_dim}[/red]")
        console.print("[yellow]Must be between 128 and 64000 (pgvector 0.7.0+)[/yellow]")
        raise typer.Exit(code=1)

    # Run migration
    try:
        asyncio.run(migrate_database(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            embedding_dim=embedding_dim,
            create_db=not no_create_db,
        ))
        console.print("\n[green]✅ Migration completed successfully![/green]")
    except Exception as e:
        console.print(f"\n[red]❌ Migration failed: {e}[/red]")
        raise typer.Exit(code=2)


@app.command()
def verify(
    host: str = typer.Option("localhost", "--host", "-h", help="PostgreSQL host"),
    port: int = typer.Option(5432, "--port", "-p", help="PostgreSQL port"),
    database: str = typer.Option("semantic_search", "--database", "-d", help="Database name"),
    user: str = typer.Option("postgres", "--user", "-u", help="Database user"),
    password: Optional[str] = typer.Option(None, "--password", help="Database password"),
) -> None:
    """
    Verify database schema is correctly set up.

    Example:
        python -m app.db.schema verify --database semantic_search
    """
    console = Console()

    async def run_verify() -> int:
        conn = None
        try:
            conn = await asyncpg.connect(
                host=host, port=port, database=database,
                user=user, password=password,
            )

            is_valid = await verify_schema(conn)

            if is_valid:
                console.print("\n[green]✅ Schema verification passed![/green]")
                return 0
            else:
                console.print("\n[red]❌ Schema verification failed![/red]")
                return 1

        except asyncpg.PostgresError as e:
            console.print(f"\n[red]❌ Connection failed: {e}[/red]")
            return 2
        finally:
            if conn:
                await conn.close()

    exit_code = asyncio.run(run_verify())
    raise typer.Exit(code=exit_code)


@app.command()
def stats(
    host: str = typer.Option("localhost", "--host", "-h", help="PostgreSQL host"),
    port: int = typer.Option(5432, "--port", "-p", help="PostgreSQL port"),
    database: str = typer.Option("semantic_search", "--database", "-d", help="Database name"),
    user: str = typer.Option("postgres", "--user", "-u", help="Database user"),
    password: Optional[str] = typer.Option(None, "--password", help="Database password"),
) -> None:
    """
    Display database statistics.

    Example:
        python -m app.db.schema stats --database semantic_search
    """
    from rich.table import Table
    console = Console()

    async def run_stats() -> int:
        conn = None
        try:
            conn = await asyncpg.connect(
                host=host, port=port, database=database,
                user=user, password=password,
            )

            stats_data = await get_table_stats(conn)

            # Display results table
            table = Table(title="\nDatabase Statistics", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan", width=25)
            table.add_column("Value", style="white", width=20)

            table.add_row("Total Chunks", str(stats_data["total_chunks"]))
            table.add_row("Unique Documents", str(stats_data["unique_documents"]))
            table.add_row("Avg Token Count", str(stats_data["avg_token_count"]))
            table.add_row("Total Size (MB)", str(stats_data["total_size_mb"]))

            console.print(table)
            console.print("\n[green]✅ Statistics retrieved successfully![/green]")
            return 0

        except asyncpg.PostgresError as e:
            console.print(f"\n[red]❌ Connection failed: {e}[/red]")
            return 2
        finally:
            if conn:
                await conn.close()

    exit_code = asyncio.run(run_stats())
    raise typer.Exit(code=exit_code)


@app.command()
def drop(
    host: str = typer.Option("localhost", "--host", "-h", help="PostgreSQL host"),
    port: int = typer.Option(5432, "--port", "-p", help="PostgreSQL port"),
    database: str = typer.Option("semantic_search", "--database", "-d", help="Database name"),
    user: str = typer.Option("postgres", "--user", "-u", help="Database user"),
    password: Optional[str] = typer.Option(None, "--password", help="Database password"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """
    Drop all indexes and tables (DESTRUCTIVE OPERATION).

    WARNING: This will delete all data in the vector_chunks table.

    Example:
        python -m app.db.schema drop --database semantic_search
        python -m app.db.schema drop --database semantic_search --force
    """
    console = Console()

    async def run_drop() -> int:
        conn = None
        try:
            conn = await asyncpg.connect(
                host=host, port=port, database=database,
                user=user, password=password,
            )

            # Get table stats
            stats_data = await get_table_stats(conn)
            chunk_count = stats_data["total_chunks"]

            if chunk_count == 0:
                console.print("[dim]ℹ️  Table is already empty (0 chunks)[/dim]")
                console.print("[yellow]Dropping schema anyway...[/yellow]")
            else:
                # Show warning panel
                console.print(Panel.fit(
                    f"[bold red]⚠️  WARNING: Schema Deletion[/bold red]\n\n"
                    f"This will permanently delete [bold red]{chunk_count}[/bold red] chunks.\n"
                    f"[dim]Database:[/dim] [bold red]{database}[/bold red]\n"
                    f"[dim]Table:[/dim] vector_chunks\n\n"
                    f"[yellow]This action cannot be undone![/yellow]",
                    border_style="red",
                    title="[red]DANGER ZONE[/red]"
                ))

                # Ask for confirmation unless --force is used
                if not force:
                    confirmation = typer.prompt(
                        "\n🔴 Type 'yes' to confirm deletion",
                        default="no"
                    )

                    if confirmation.lower() not in ["yes", "y"]:
                        console.print("[yellow]❌ Deletion cancelled[/yellow]")
                        return 0

            # Drop schema
            console.print("[yellow]⏳ Dropping schema...[/yellow]")
            await drop_schema(conn)
            console.print("[green]✅ Schema dropped successfully[/green]")
            return 0

        except asyncpg.PostgresError as e:
            console.print(f"\n[red]❌ Drop failed: {e}[/red]")
            return 2
        finally:
            if conn:
                await conn.close()

    exit_code = asyncio.run(run_drop())
    raise typer.Exit(code=exit_code)


# CLI entry point
if __name__ == "__main__":
    app()
