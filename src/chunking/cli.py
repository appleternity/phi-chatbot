"""
Simple CLI for document chunking pipeline.

Usage:
    python -m src.chunking.cli process --input chapter1.txt --output output/
    python -m src.chunking.cli process --input book/ --output output/
"""

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

from .chunking_pipeline import ChunkingPipeline
from .llm_provider import OpenRouterProvider
from .logger import setup_logging
from .models import Document

# Initialize
console = Console()
app = typer.Typer(
    name="chunking",
    help="Document chunking pipeline with LLM-based structure analysis",
    no_args_is_help=True
)


@app.command()
def process(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to document file or folder to process",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Output directory for chunks (creates subdirs per document)",
            resolve_path=True
        )
    ],
    structure_model: Annotated[
        str,
        typer.Option(
            "--structure-model",
            help="Model for structure analysis (Phase 1)"
        )
    ] = "google/gemini-2.5-pro",
    extraction_model: Annotated[
        str,
        typer.Option(
            "--extraction-model",
            help="Model for chunk extraction (Phase 2)"
        )
    ] = "anthropic/claude-haiku-4.5",
    max_tokens: Annotated[
        int,
        typer.Option(
            "--max-tokens",
            help="Maximum tokens per chunk",
            min=100,
            max=2000
        )
    ] = 1000,
    redo: Annotated[
        bool,
        typer.Option(
            "--redo",
            help="Force reprocessing even if output files exist (applies to both structure and chunks)"
        )
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
):
    """
    Process documents into contextual chunks using 2-phase pipeline.

    Phase 1: Structure Analysis (default: Gemini 2.5 Pro)
    Phase 2: Chunk Extraction (default: Claude Haiku 4.5)

    Output structure:
        output_dir/
        └── document_id/
            ├── document_id_structure.json
            ├── document_id_chunk_001.json
            ├── document_id_chunk_002.json
            └── ...

    Examples:
        # Process single file
        python -m src.chunking.cli process --input chapter1.txt --output output/

        # Process folder
        python -m src.chunking.cli process --input book/ --output output/

        # Override models
        python -m src.chunking.cli process \\
            --input chapter1.txt \\
            --output output/ \\
            --structure-model openai/gpt-4o \\
            --extraction-model google/gemini-2.0-flash-exp

        # Force reprocess
        python -m src.chunking.cli process --input chapter1.txt --output output/ --redo
    """
    # Setup environment
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] OPENROUTER_API_KEY not found in environment")
        console.print("Please set OPENROUTER_API_KEY in .env file or environment variables")
        raise typer.Exit(2)

    # Setup logging
    logger = setup_logging(log_level, use_context=False)

    # Initialize components
    llm_provider = OpenRouterProvider(api_key=api_key)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize pipeline
    console.print("[cyan]Initializing pipeline...[/cyan]")
    console.print(f"[dim]Structure model: {structure_model}[/dim]")
    console.print(f"[dim]Extraction model: {extraction_model}[/dim]")
    console.print(f"[dim]Max tokens: {max_tokens}[/dim]")
    console.print(f"[dim]Output: {output_dir}[/dim]\n")

    pipeline = ChunkingPipeline(
        llm_provider=llm_provider,
        output_dir=output_dir,
        structure_model=structure_model,
        extraction_model=extraction_model,
        max_chunk_tokens=max_tokens
    )

    # Process input
    if input_path.is_file():
        # Single file processing
        console.print(f"[cyan]Processing file: {input_path.name}[/cyan]\n")

        document = Document.from_file(input_path)
        result = pipeline.process_document(document, redo=redo)

        # Print results
        console.print(f"\n[green]✓[/green] Processed: {result.document_id}")
        console.print(f"[cyan]Chunks:[/cyan] {result.total_chunks}")
        console.print(f"[cyan]Tokens consumed:[/cyan] {result.processing_report.total_tokens_consumed:,}")
        console.print(f"[cyan]Coverage:[/cyan] {result.text_coverage_ratio:.1%}")
        console.print(f"[cyan]Duration:[/cyan] {result.processing_report.duration_seconds:.2f}s")
        console.print(f"[cyan]Output:[/cyan] {output_dir / result.document_id}/")

        logger.info(
            f"Processed {result.document_id}: "
            f"{result.total_chunks} chunks, "
            f"{result.processing_report.total_tokens_consumed:,} tokens"
        )

    else:
        # Folder processing
        console.print(f"[cyan]Processing folder: {input_path}[/cyan]\n")

        result = pipeline.process_folder(input_path, redo=redo)

        # Print results
        console.print("\n[green]✓[/green] Batch complete")
        console.print(f"[cyan]Documents processed:[/cyan] {result.successful_documents}/{result.total_documents}")
        console.print(f"[cyan]Total chunks:[/cyan] {result.total_chunks}")
        console.print(f"[cyan]Tokens consumed:[/cyan] {result.batch_report.total_tokens_consumed:,}")
        console.print(f"[cyan]Duration:[/cyan] {result.batch_report.total_duration_seconds:.2f}s")
        console.print(f"[cyan]Output:[/cyan] {output_dir}/")

        if result.failed_documents:
            console.print(f"\n[yellow]Failed documents:[/yellow] {len(result.failed_documents)}")
            for doc_id in result.failed_documents:
                console.print(f"  - {doc_id}")

        logger.info(
            f"Batch processed: {result.successful_documents} documents, "
            f"{result.total_chunks} chunks, "
            f"{result.batch_report.total_tokens_consumed:,} tokens"
        )


if __name__ == "__main__":
    app()
