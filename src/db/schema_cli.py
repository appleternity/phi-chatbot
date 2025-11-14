"""
Database schema CLI tool for PostgreSQL with pgvector.

This module provides command-line interface for database schema management,
moved from app/db/schema.py to consolidate all CLI tools under src/.

Commands:
- migrate: Create database and schema with smart defaults from .env
- verify: Verify schema is correctly set up
- stats: Display database statistics
- enable-keyword-search: Enable pg_trgm extension for keyword search
- drop: Drop all indexes and tables (destructive)

Usage:
    python -m src.db.schema_cli migrate
    python -m src.db.schema_cli enable-keyword-search --table text-embedding-v4
"""

import asyncio
import os
from typing import Optional

import asyncpg
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

# Import core schema functions from app
from app.db.schema import (
    migrate_database,
    verify_schema,
    get_table_stats,
    drop_schema,
    enable_keyword_search,
)

# Load environment variables
load_dotenv()

# Get defaults from environment
DEFAULT_HOST = os.getenv("POSTGRES_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DEFAULT_DATABASE = os.getenv("POSTGRES_DB", "medical_knowledge")
DEFAULT_USER = os.getenv("POSTGRES_USER", "postgres")
DEFAULT_PASSWORD = os.getenv("POSTGRES_PASSWORD")

# Typer CLI app
app = typer.Typer(
    name="db-schema",
    help="Database schema management for PostgreSQL with pgvector",
    add_completion=False,
)


@app.command()
def migrate(
    host: str = typer.Option(
        DEFAULT_HOST,
        "--host",
        "-h",
        help=f"PostgreSQL host (default from .env: {DEFAULT_HOST})"
    ),
    port: int = typer.Option(
        DEFAULT_PORT,
        "--port",
        "-p",
        help=f"PostgreSQL port (default from .env: {DEFAULT_PORT})"
    ),
    database: str = typer.Option(
        DEFAULT_DATABASE,
        "--database",
        "-d",
        help=f"Database name (default from .env: {DEFAULT_DATABASE})"
    ),
    user: str = typer.Option(
        DEFAULT_USER,
        "--user",
        "-u",
        help=f"Database user (default from .env: {DEFAULT_USER})"
    ),
    password: Optional[str] = typer.Option(
        DEFAULT_PASSWORD,
        "--password",
        help="Database password (default from .env or omit for no password)"
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

    Reads connection defaults from .env file for convenience.

    Examples:
        # Use all defaults from .env
        python -m src.db.schema_cli migrate

        # Override specific values
        python -m src.db.schema_cli migrate --database my_db --embedding-dim 8192

        # Only create schema (skip database creation)
        python -m src.db.schema_cli migrate --no-create-db
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
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help=f"PostgreSQL host (default: {DEFAULT_HOST})"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help=f"PostgreSQL port (default: {DEFAULT_PORT})"),
    database: str = typer.Option(DEFAULT_DATABASE, "--database", "-d", help=f"Database name (default: {DEFAULT_DATABASE})"),
    user: str = typer.Option(DEFAULT_USER, "--user", "-u", help=f"Database user (default: {DEFAULT_USER})"),
    password: Optional[str] = typer.Option(DEFAULT_PASSWORD, "--password", help="Database password (default from .env)"),
) -> None:
    """
    Verify database schema is correctly set up.

    Example:
        python -m src.db.schema_cli verify
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
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help=f"PostgreSQL host (default: {DEFAULT_HOST})"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help=f"PostgreSQL port (default: {DEFAULT_PORT})"),
    database: str = typer.Option(DEFAULT_DATABASE, "--database", "-d", help=f"Database name (default: {DEFAULT_DATABASE})"),
    user: str = typer.Option(DEFAULT_USER, "--user", "-u", help=f"Database user (default: {DEFAULT_USER})"),
    password: Optional[str] = typer.Option(DEFAULT_PASSWORD, "--password", help="Database password (default from .env)"),
) -> None:
    """
    Display database statistics.

    Example:
        python -m src.db.schema_cli stats
    """
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


@app.command(name="enable-keyword-search")
def enable_keyword_search_cli(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help=f"PostgreSQL host (default: {DEFAULT_HOST})"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help=f"PostgreSQL port (default: {DEFAULT_PORT})"),
    database: str = typer.Option(DEFAULT_DATABASE, "--database", "-d", help=f"Database name (default: {DEFAULT_DATABASE})"),
    user: str = typer.Option(DEFAULT_USER, "--user", "-u", help=f"Database user (default: {DEFAULT_USER})"),
    password: Optional[str] = typer.Option(DEFAULT_PASSWORD, "--password", help="Database password (default from .env)"),
    table_name: str = typer.Option("vector_chunks", "--table", "-t", help="Table name to enable keyword search on"),
) -> None:
    """
    Enable pg_trgm extension and create GIN index for keyword search.

    This command enables trigram-based fuzzy text matching for keyword search
    alongside vector similarity search.

    Examples:
        python -m src.db.schema_cli enable-keyword-search
        python -m src.db.schema_cli enable-keyword-search --table text-embedding-v4
    """
    console = Console()

    async def run_enable() -> int:
        conn = None
        try:
            conn = await asyncpg.connect(
                host=host, port=port, database=database,
                user=user, password=password,
            )

            console.print(f"[yellow]⏳ Enabling pg_trgm extension and creating GIN index on table '{table_name}'...[/yellow]")
            await enable_keyword_search(conn, table_name=table_name)
            console.print(f"[green]✅ Keyword search enabled successfully for table '{table_name}'![/green]")
            console.print("\n[dim]Next steps:[/dim]")
            console.print("[dim]  1. Set ENABLE_KEYWORD_SEARCH=true in .env[/dim]")
            console.print(f"[dim]  2. Set TABLE_NAME={table_name} in .env (if not already set)[/dim]")
            console.print("[dim]  3. Restart your application[/dim]")
            console.print("[dim]  4. Test hybrid search with keyword matching[/dim]")
            return 0

        except asyncpg.PostgresError as e:
            console.print(f"\n[red]❌ Migration failed: {e}[/red]")
            return 2
        except Exception as e:
            console.print(f"\n[red]❌ Error: {e}[/red]")
            return 1
        finally:
            if conn:
                await conn.close()

    exit_code = asyncio.run(run_enable())
    raise typer.Exit(code=exit_code)


@app.command()
def drop(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help=f"PostgreSQL host (default: {DEFAULT_HOST})"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help=f"PostgreSQL port (default: {DEFAULT_PORT})"),
    database: str = typer.Option(DEFAULT_DATABASE, "--database", "-d", help=f"Database name (default: {DEFAULT_DATABASE})"),
    user: str = typer.Option(DEFAULT_USER, "--user", "-u", help=f"Database user (default: {DEFAULT_USER})"),
    password: Optional[str] = typer.Option(DEFAULT_PASSWORD, "--password", help="Database password (default from .env)"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """
    Drop all indexes and tables (DESTRUCTIVE OPERATION).

    WARNING: This will delete all data in the vector_chunks table.

    Example:
        python -m src.db.schema_cli drop
        python -m src.db.schema_cli drop --force
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
