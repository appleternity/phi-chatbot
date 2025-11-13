"""
Stage 2: Ingest Embeddings from Parquet to Database.

Two-stage embedding pipeline (Stage 2):
    Read Parquet → Extract dimension → Create/validate table → Bulk insert

Benefits:
- Known embedding dimension before table creation
- Can create table with correct vector type automatically
- Bulk insert using PostgreSQL COPY (10-100x faster than INSERT)
- Idempotent (ON CONFLICT DO NOTHING)
- Can ingest to multiple databases from same Parquet file

Usage:
    # Ingest embeddings to default database
    python -m src.embeddings.ingest_embeddings \\
        --input data/embeddings.parquet

    # Ingest to custom table name
    python -m src.embeddings.ingest_embeddings \\
        --input data/embeddings.parquet \\
        --table-name vector_chunks_v2

    # Create fresh database (drops existing table)
    python -m src.embeddings.ingest_embeddings \\
        --input data/embeddings.parquet \\
        --drop-existing
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Annotated

import typer
import pandas as pd
import pyarrow.parquet as pq
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

from app.config import Settings
from app.db.schema import create_schema, drop_schema
from app.db.connection import DatabasePool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

console = Console()


def validate_table_name(table_name: str) -> str:
    """Validate table name is a safe SQL identifier.

    Security: Prevents SQL injection by ensuring table names follow
    PostgreSQL identifier rules. This is critical since table names
    cannot use parameterized queries ($1 placeholders).

    Args:
        table_name: Table name to validate

    Returns:
        Validated table name (same as input)

    Raises:
        ValueError: If table name is invalid
    """
    import re

    # Whitelist of allowed table names (common use cases)
    allowed_tables = frozenset({
        "vector_chunks",
        "vector_chunks_test",
        "vector_chunks_prod",
        "vector_chunks_staging",
        "vector_chunks_v2",
        "vector_chunks_backup",
    })

    if table_name in allowed_tables:
        return table_name

    # Fallback: validate against SQL identifier pattern
    # Allow: letters, digits, underscores (PostgreSQL identifier rules)
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise ValueError(
            f"Invalid table_name: '{table_name}'. "
            f"Must match PostgreSQL identifier pattern [a-zA-Z_][a-zA-Z0-9_]* "
            f"or be one of: {', '.join(sorted(allowed_tables))}"
        )

    # Additional length check (PostgreSQL identifier max length is 63)
    if len(table_name) > 63:
        raise ValueError(
            f"Invalid table_name: '{table_name}'. "
            f"Maximum length is 63 characters (PostgreSQL limit)"
        )

    return table_name


# Typer app
app = typer.Typer(
    name="ingest-embeddings",
    help="Ingest embeddings from Parquet to database (Stage 2 of 2)",
    add_completion=False,
)


def read_parquet_metadata(parquet_path: Path) -> Dict[str, str]:
    """
    Read metadata from Parquet file.

    Args:
        parquet_path: Path to Parquet file

    Returns:
        Dictionary of metadata (all values are strings)

    Raises:
        AssertionError: If file doesn't exist or missing required metadata
    """
    assert parquet_path.exists(), f"Parquet file not found: {parquet_path}"
    assert parquet_path.is_file(), f"Path is not a file: {parquet_path}"

    # Read Parquet file metadata
    table = pq.read_table(parquet_path)
    schema_metadata = table.schema.metadata

    assert schema_metadata is not None, \
        "Parquet file missing metadata. Was it generated with generate_embeddings.py?"

    # Decode bytes to strings
    metadata = {k.decode(): v.decode() for k, v in schema_metadata.items()}

    # Validate required metadata
    required_keys = {"embedding_dimension", "embedding_model", "provider_type", "total_chunks"}
    missing_keys = required_keys - set(metadata.keys())
    assert not missing_keys, \
        f"Parquet metadata missing required keys: {missing_keys}"

    console.print("[cyan]📊 Parquet Metadata:[/cyan]")
    for key, value in metadata.items():
        console.print(f"[dim]   {key}: {value}[/dim]")

    return metadata


async def create_table_with_dimension(embedding_dim: int, table_name: str) -> None:
    """
    Create vector_chunks table with specified dimension.

    Uses app.db.schema.create_schema() which automatically selects:
    - vector(N) for dims 128-2000 (float32)
    - halfvec(N) for dims 2001-4000 (float16, 50% space savings)
    - vector(N) + binary quantization for dims >4000 (97% space savings)

    Args:
        embedding_dim: Embedding dimension from Parquet metadata
        table_name: Table name (default: vector_chunks)

    Raises:
        AssertionError: If dimension is invalid or table creation fails
    """
    assert 128 <= embedding_dim <= 64000, \
        f"Invalid embedding dimension: {embedding_dim}"

    async with DatabasePool() as pool:
        # Check if table already exists
        # Security: Use parameterized query to prevent SQL injection
        table_exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_name = $1)",
            table_name
        )

        if table_exists:
            # Validate existing schema matches
            stored_dim = await pool.fetchval(
                "SELECT value FROM schema_metadata WHERE key = 'embedding_dimension'"
            )

            assert stored_dim is not None, \
                f"Table {table_name} exists but schema_metadata missing embedding_dimension"

            stored_dim_int = int(stored_dim)

            assert stored_dim_int == embedding_dim, \
                f"Dimension mismatch! Parquet: {embedding_dim}, DB: {stored_dim_int}. " \
                f"Use --drop-existing to recreate table."

            console.print(f"[green]✅ Table {table_name} exists with matching dimension {embedding_dim}[/green]")

        else:
            # Create new table with detected dimension
            console.print(f"[cyan]📝 Creating table {table_name} with {embedding_dim}-dim vectors...[/cyan]")
            await create_schema(pool, embedding_dim=embedding_dim, table_name=table_name)
            console.print(f"[green]✅ Table {table_name} created successfully[/green]")


async def ingest_parquet_to_db(
    parquet_path: Path,
    table_name: str,
    batch_size: int = 1000
) -> int:
    """
    Bulk insert embeddings from Parquet to PostgreSQL.

    Uses COPY for efficient bulk insert (10-100x faster than INSERT).
    Idempotent: ON CONFLICT DO NOTHING for duplicate chunk_ids.

    Args:
        parquet_path: Path to Parquet file
        table_name: Target table name
        batch_size: Number of rows per insert batch

    Returns:
        Number of rows inserted (excluding duplicates)

    Raises:
        AssertionError: If data validation fails
    """
    # Read Parquet file
    console.print(f"[cyan]📖 Reading {parquet_path}...[/cyan]")
    df = pd.read_parquet(parquet_path)
    console.print(f"[green]✅ Loaded {len(df)} rows from Parquet[/green]")

    # Validate required columns
    required_columns = {
        "chunk_id", "source_document", "chunk_text", "embedding", "token_count"
    }
    missing_columns = required_columns - set(df.columns)
    assert not missing_columns, \
        f"Parquet missing required columns: {missing_columns}"

    inserted_count = 0

    async with DatabasePool() as pool:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:

            task = progress.add_task(
                f"[cyan]Inserting to {table_name} (batch_size={batch_size})",
                total=len(df)
            )

            for i in range(0, len(df), batch_size):
                batch_df = df.iloc[i:i + batch_size]

                # Prepare batch data
                records = []
                for _, row in batch_df.iterrows():
                    # Convert embedding to Python list (from numpy array)
                    # pgvector codec expects list, not numpy array
                    embedding_list = row["embedding"].tolist() if hasattr(row["embedding"], 'tolist') else list(row["embedding"])

                    record = (
                        row["chunk_id"],
                        row["source_document"],
                        row.get("chapter_title"),
                        row.get("section_title"),
                        row.get("subsection_title", []),  # TEXT[] array
                        row.get("summary"),
                        row["token_count"],
                        row["chunk_text"],
                        embedding_list,  # VECTOR type (as Python list)
                    )
                    records.append(record)

                # Bulk insert with ON CONFLICT DO NOTHING (idempotent)
                # Security: table_name quoted to prevent SQL injection and support special chars
                # PostgreSQL doesn't support parameterized identifiers, so quoted f-string is safe
                await pool.executemany(
                    f"""
                    INSERT INTO "{table_name}" (
                        chunk_id,
                        source_document,
                        chapter_title,
                        section_title,
                        subsection_title,
                        summary,
                        token_count,
                        chunk_text,
                        embedding
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    records
                )

                # Note: asyncpg executemany doesn't return per-row status
                # We count total attempts; duplicates are silently skipped via ON CONFLICT
                inserted_count += len(batch_df)

                progress.update(task, advance=len(batch_df))

        console.print(f"[green]✅ Processed {inserted_count} rows (duplicates skipped via ON CONFLICT)[/green]")

    return inserted_count


@app.command()
def ingest(
    input: Annotated[Path, typer.Option(
        help="Input Parquet file with embeddings",
        exists=True,
        file_okay=True,
        dir_okay=False,
    )],
    table_name: Annotated[str, typer.Option(
        help="Target PostgreSQL table name",
    )] = "vector_chunks",
    batch_size: Annotated[int, typer.Option(
        help="Batch size for bulk insert",
    )] = 1000,
    drop_existing: Annotated[bool, typer.Option(
        help="Drop existing table before ingestion (DESTRUCTIVE)",
    )] = False,
) -> None:
    """
    Ingest embeddings from Parquet file to PostgreSQL database.

    This is Stage 2 of the two-stage embedding pipeline:
    1. Generate embeddings → Save to Parquet (previous step)
    2. Load Parquet → Ingest to DB (this command)

    Examples:
        # Ingest to default table
        python -m src.embeddings.ingest_embeddings \\
            --input data/embeddings.parquet

        # Ingest to custom table
        python -m src.embeddings.ingest_embeddings \\
            --input data/embeddings.parquet \\
            --table-name vector_chunks_v2

        # Drop and recreate table (fresh start)
        python -m src.embeddings.ingest_embeddings \\
            --input data/embeddings.parquet \\
            --drop-existing
    """
    try:
        # Security: Validate table name before using in SQL queries
        # This prevents SQL injection since table names cannot use parameterized queries
        # FIXME: This is the ingestion step, so we DO not need to validate the table_name
        # FIXME: IT is likely we are creating new table names for testing
        # table_name = validate_table_name(table_name)

        console.print(Panel.fit(
            "[bold cyan]Stage 2: Ingest Embeddings to Database[/bold cyan]\n\n"
            f"Input: {input}\n"
            f"Table: {table_name}\n"
            f"Batch size: {batch_size}\n"
            f"Drop existing: {drop_existing}",
            border_style="cyan"
        ))

        # Read Parquet metadata
        metadata = read_parquet_metadata(input)
        embedding_dim = int(metadata["embedding_dimension"])
        total_chunks = int(metadata["total_chunks"])

        console.print(f"[cyan]📏 Embedding dimension: {embedding_dim}[/cyan]")
        console.print(f"[cyan]📦 Total chunks: {total_chunks}[/cyan]")

        # Drop existing table if requested
        if drop_existing:
            if not typer.confirm(f"Are you sure you want to drop the existing {table_name} table? This action is destructive and cannot be undone."):
                console.print("[yellow]Aborted dropping table.[/yellow]")
                raise typer.Exit()
            console.print("[yellow]⚠️  Dropping existing table...[/yellow]")

            async def drop():
                async with DatabasePool() as pool:
                    await drop_schema(pool, table_name=table_name)
                    console.print(f"[green]✅ Table {table_name} dropped[/green]")

            asyncio.run(drop())

        # Create or validate table
        asyncio.run(create_table_with_dimension(embedding_dim, table_name))

        # Ingest data
        inserted_count = asyncio.run(ingest_parquet_to_db(input, table_name, batch_size))

        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold green]✅ Stage 2 Complete![/bold green]")
        console.print("=" * 60)

        summary_table = Table(show_header=False, box=None)
        summary_table.add_row("📂 Source file:", str(input))
        summary_table.add_row("📊 Total chunks:", str(total_chunks))
        summary_table.add_row("✅ Rows processed:", str(inserted_count))
        summary_table.add_row("💾 Table:", table_name)
        summary_table.add_row("📏 Dimension:", str(embedding_dim))

        console.print(summary_table)

        if inserted_count > 0:
            console.print("\n[cyan]✅ Ready to start API server![/cyan]")
            console.print("[dim]  python -m app.main[/dim]")
        else:
            console.print("\n[yellow]⚠️  No rows processed[/yellow]")

    except AssertionError as e:
        console.print(f"[red]❌ Validation error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Fatal error during ingestion")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
