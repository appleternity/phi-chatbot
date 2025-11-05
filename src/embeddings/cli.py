"""
CLI for document indexing pipeline.

This module provides command-line interface for indexing chunked documents:
- index: Batch index all chunks in directory
- Progress tracking with rich
- Validation after indexing
- Exit codes: 0 (success), 1 (partial failure), 2 (fatal error)

Usage:
    # Index all chunks in directory
    python -m src.embeddings.cli index \\
        --input data/chunking_final \\
        --config config/embedding_config.json

    # Index with skip-existing and custom batch size
    python -m src.embeddings.cli index \\
        --input data/chunking_final \\
        --batch-size 32 \\
        --skip-existing \\
        --verbose

    # Clear database before indexing (requires confirmation)
    python -m src.embeddings.cli index \\
        --input data/chunking_final \\
        --clear-db \\
        --verbose
"""

import asyncio
import logging
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel

from src.embeddings.indexer import DocumentIndexer
from app.db.connection import get_pool, close_pool

# Load environment variables from .env file
load_dotenv()


# Configure logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False)]
)

logger = logging.getLogger(__name__)
console = Console()

# Typer app
app = typer.Typer(
    name="embeddings-cli",
    help="CLI for document indexing with Qwen3-Embedding-0.6B",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


@app.command()
def index(
    input: str = typer.Option(
        ...,
        "--input",
        "-i",
        help="Input directory containing JSON chunk files"
    ),
    model_name: str = typer.Option(
        "Qwen/Qwen3-Embedding-0.6B",
        "--model-name",
        "-m",
        help="HuggingFace model ID for embeddings"
    ),
    device: str = typer.Option(
        "mps",
        "--device",
        "-d",
        help="Inference device: mps (Apple Silicon), cuda (NVIDIA), or cpu"
    ),
    batch_size: int = typer.Option(
        16,
        "--batch-size",
        "-b",
        help="Batch size for embedding generation (1-128)"
    ),
    max_length: int = typer.Option(
        8196,
        "--max-length",
        help="Maximum token length for inputs (128-32768)"
    ),
    normalize: bool = typer.Option(
        True,
        "--normalize/--no-normalize",
        help="L2 normalize embeddings"
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        "-s",
        help="Skip chunks that already exist in database"
    ),
    clear_db: bool = typer.Option(
        False,
        "--clear-db",
        help="Delete ALL existing documents in database before indexing (requires confirmation)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging"
    ),
):
    """
    Index all chunk files in directory to PostgreSQL.

    Reads JSON chunk files, generates embeddings using Qwen3-Embedding-0.6B,
    and inserts into vector_chunks table with ON CONFLICT DO NOTHING.

    Exit codes:
    - 0: Complete success (all chunks indexed)
    - 1: Partial failure (some chunks failed)
    - 2: Fatal error (configuration, database, or indexing pipeline failure)

    Examples:
        # Basic indexing with defaults
        python -m src.embeddings.cli index --input data/chunking_final

        # Custom model and device
        python -m src.embeddings.cli index --input data/chunking_final --model-name Qwen/Qwen3-Embedding-0.6B --device mps

        # Skip existing chunks
        python -m src.embeddings.cli index --input data/chunking_final --skip-existing --verbose

        # Custom batch size and max length
        python -m src.embeddings.cli index --input data/chunking_final --batch-size 32 --max-length 1024

        # Clear database before indexing (requires confirmation)
        python -m src.embeddings.cli index --input data/chunking_final --clear-db
    """
    # Enable verbose logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Display header
    console.print(Panel.fit(
        "[bold cyan]Document Indexing Pipeline[/bold cyan]\n"
        f"[dim]Model: {model_name}[/dim]\n"
        f"[dim]Device: {device} | Batch: {batch_size} | Normalize: {normalize}[/dim]",
        border_style="cyan"
    ))

    # Validate parameters
    assert batch_size >= 1, f"batch_size must be >= 1, got {batch_size}"
    assert max_length >= 1, f"max_length must be >= 1, got {max_length}"
    # Device validation handled by encoder (torch will raise error if invalid)

    # Run indexing pipeline
    async def run_indexing():
        db_pool = None
        try:
            # Initialize database pool
            console.print("[yellow]⏳ Initializing database connection...[/yellow]")
            db_pool = await get_pool()
            console.print("[green]✅ Database connected[/green]")

            # Handle --clear-db flag
            if clear_db:
                # Get current document count
                doc_count = await db_pool.fetchval("SELECT COUNT(*) FROM vector_chunks")

                if doc_count > 0:
                    # Get actual connected database name (fail-fast)
                    db_name = await db_pool.fetchval("SELECT current_database()")
                    assert db_name is not None, "Cannot determine database name from connection pool"

                    # Show warning panel
                    console.print(Panel.fit(
                        f"[bold red]⚠️  WARNING: Database Deletion[/bold red]\n\n"
                        f"This will permanently delete [bold red]{doc_count}[/bold red] documents.\n"
                        f"[dim]Database:[/dim] [bold red]{db_name}[/bold red]\n"
                        f"[dim]Table:[/dim] vector_chunks\n\n"
                        f"[yellow]This action cannot be undone![/yellow]",
                        border_style="red",
                        title="[red]DANGER ZONE[/red]"
                    ))

                    # Ask for confirmation
                    confirmation = typer.prompt(
                        "\n🔴 Type 'yes' to confirm deletion",
                        default="no"
                    )

                    if confirmation.lower() in ["yes", "y"]:
                        console.print("[yellow]⏳ Deleting all documents...[/yellow]")
                        await db_pool.execute("DELETE FROM vector_chunks")
                        console.print(f"[green]✅ Deleted {doc_count} documents from database[/green]")
                    else:
                        console.print("[yellow]❌ Deletion cancelled - keeping existing documents[/yellow]")
                        console.print("[dim]Tip: Use --skip-existing to avoid duplicate insertions[/dim]")
                else:
                    console.print("[dim]ℹ️  Database is already empty (0 documents)[/dim]")

            # Initialize indexer with direct parameters
            console.print("[yellow]⏳ Initializing Qwen3EmbeddingEncoder...[/yellow]")
            indexer = DocumentIndexer(
                db_pool=db_pool,
                model_name=model_name,
                device=device,
                batch_size=batch_size,
                max_length=max_length,
                normalize_embeddings=normalize
            )
            console.print("[green]✅ Encoder initialized[/green]")

            # Run indexing
            console.print(f"\n[bold]Starting indexing: {input}[/bold]")
            stats = await indexer.index_directory(
                input_dir=input,
                skip_existing=skip_existing,
                batch_size=batch_size,
                verbose=verbose
            )

            # Display results table
            table = Table(title="\nIndexing Results", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan", width=20)
            table.add_column("Value", style="white", width=15)

            table.add_row("Total Files", str(stats.total_files))
            table.add_row("Successful", f"[green]{stats.successful}[/green]")
            table.add_row("Failed", f"[red]{stats.failed}[/red]" if stats.failed > 0 else "0")
            table.add_row("Skipped", str(stats.skipped))
            table.add_row("Duration", f"{stats.duration_seconds:.2f}s")
            table.add_row("Success Rate", f"{stats.to_dict()['success_rate']:.2f}%")

            console.print(table)

            # Display errors if any
            if stats.errors:
                console.print("\n[bold red]Errors:[/bold red]")
                for error in stats.errors[:10]:  # Show first 10 errors
                    console.print(f"  • {error['file']}: {error['error']}")
                if len(stats.errors) > 10:
                    console.print(f"  [dim]... and {len(stats.errors) - 10} more errors[/dim]")
                console.print("\n[yellow]Full error log: indexing_errors.log[/yellow]")

            # Run validation
            if stats.successful > 0:
                console.print("\n[yellow]⏳ Running validation...[/yellow]")
                validation = await indexer.validate_indexed_chunks(input_dir=input)

                # Display validation results
                validation_table = Table(
                    title="Validation Results",
                    show_header=True,
                    header_style="bold magenta"
                )
                validation_table.add_column("Check", style="cyan", width=25)
                validation_table.add_column("Status", style="white", width=20)

                # Count match
                count_status = "[green]✅ PASS[/green]" if validation['count_match'] else "[red]❌ FAIL[/red]"
                validation_table.add_row(
                    "File Count Match",
                    f"{count_status} ({validation['total_files']} files, {validation['total_db_chunks']} DB)"
                )

                # Embedding validation
                embedding_status = "[green]✅ PASS[/green]" if not validation['invalid_embeddings'] else f"[red]❌ FAIL ({len(validation['invalid_embeddings'])} invalid)[/red]"
                validation_table.add_row("Embedding Validation", embedding_status)

                # Overall
                overall_status = "[green]✅ PASS[/green]" if validation['validation_passed'] else "[red]❌ FAIL[/red]"
                validation_table.add_row("Overall", overall_status)

                console.print(validation_table)

                if not validation['validation_passed']:
                    console.print("\n[red]❌ Validation failed - see errors above[/red]")

            # Determine exit code
            if stats.failed > 0:
                console.print("\n[yellow]⚠️  Indexing completed with failures[/yellow]")
                return 1  # Partial failure
            else:
                console.print("\n[green]✅ Indexing completed successfully![/green]")
                return 0  # Complete success

        except ValueError as e:
            console.print(f"\n[red]❌ Validation error: {e}[/red]")
            return 2  # Fatal error
        except Exception as e:
            console.print(f"\n[red]❌ Fatal error: {e}[/red]")
            logger.exception("Indexing failed with exception")
            return 2  # Fatal error
        finally:
            # Cleanup database pool
            if db_pool:
                console.print("\n[yellow]⏳ Closing database connection...[/yellow]")
                await close_pool()
                console.print("[green]✅ Database connection closed[/green]")

    # Run async indexing pipeline
    exit_code = asyncio.run(run_indexing())
    raise typer.Exit(code=exit_code)


@app.command()
def version():
    """Display version information."""
    console.print(Panel.fit(
        "[bold cyan]Document Indexing CLI[/bold cyan]\n\n"
        "[white]Version:[/white] 1.0.0\n"
        "[white]Model:[/white] Configurable (use --model-name)\n"
        "[white]Device:[/white] Configurable (mps/cuda/cpu)\n"
        "[white]Embedding Dimension:[/white] Model-dependent",
        border_style="cyan"
    ))




# Entry point
def main():
    """Main entry point for CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Indexing interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
        logger.exception("CLI failed with unexpected error")
        sys.exit(2)


if __name__ == "__main__":
    main()
