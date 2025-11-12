"""
Stage 1: Generate Embeddings and Save to Parquet.

Two-stage embedding pipeline (Stage 1):
    Raw chunks (JSON) → Generate embeddings → Save to Parquet file

Benefits:
- Parquet file becomes source of truth for embeddings
- Can regenerate DB from Parquet anytime
- Embedding generation separate from DB ingestion
- Easy to inspect with pandas: pd.read_parquet()
- Dimension metadata embedded in Parquet schema

Usage:
    # Generate embeddings for all chunks
    python -m src.embeddings.generate_embeddings \\
        --input data/chunking_final \\
        --output data/embeddings.parquet

    # Use OpenRouter API instead of local model
    python -m src.embeddings.generate_embeddings \\
        --input data/chunking_final \\
        --output data/embeddings.parquet \\
        --provider openrouter

    # Custom batch size and device
    python -m src.embeddings.generate_embeddings \\
        --input data/chunking_final \\
        --output data/embeddings.parquet \\
        --batch-size 32 \\
        --device mps
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Annotated
from datetime import datetime

import typer
import pandas as pd
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

from app.config import Settings
from app.embeddings import create_embedding_provider
from app.embeddings.base import EmbeddingProvider
from app.utils.retry import retry_on_network_error

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

console = Console()

# Typer app
app = typer.Typer(
    name="generate-embeddings",
    help="Generate embeddings and save to Parquet (Stage 1 of 2)",
    add_completion=False,
)


def load_chunks_from_directory(input_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all chunk JSON files from directory.

    Args:
        input_dir: Directory containing chunk JSON files

    Returns:
        List of chunk dictionaries

    Raises:
        AssertionError: If no chunks found or invalid data
    """
    input_path = Path(input_dir)
    assert input_path.exists(), f"Input directory not found: {input_path}"
    assert input_path.is_dir(), f"Input path is not a directory: {input_path}"

    # Find all chunk JSON files
    chunk_files = sorted(input_path.glob("*_chunk_*.json"))
    assert len(chunk_files) > 0, f"No chunk files found in {input_path}"

    console.print(f"[cyan]📂 Found {len(chunk_files)} chunk files in {input_dir}[/cyan]")

    # Load all chunks
    chunks = []
    for chunk_file in chunk_files:
        with open(chunk_file, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
            chunks.append(chunk_data)

    # Validate required fields
    required_fields = {"chunk_id", "source_document", "chunk_text"}
    for i, chunk in enumerate(chunks):
        missing_fields = required_fields - set(chunk.keys())
        assert not missing_fields, \
            f"Chunk {i} missing required fields: {missing_fields}"

    console.print(f"[green]✅ Loaded {len(chunks)} chunks successfully[/green]")
    return chunks


@retry_on_network_error(max_attempts=3, initial_delay=2.0)
def generate_embedding_with_retry(provider: EmbeddingProvider, text: str) -> np.ndarray:
    """
    Generate embedding with automatic retry on network errors.

    This wrapper adds retry logic for transient network failures.
    All other exceptions propagate immediately (fail-fast).

    Args:
        provider: Embedding provider instance
        text: Text to encode

    Returns:
        Embedding vector as numpy array

    Raises:
        httpx.TimeoutException: After max retry attempts
        openai.APIError: After max retry attempts
        Exception: Any non-transient error (propagates immediately)
    """
    return provider.encode(text)


def generate_embeddings_batch(
    chunks: List[Dict[str, Any]],
    provider: EmbeddingProvider,
    batch_size: int = 16
) -> pd.DataFrame:
    """
    Generate embeddings for all chunks with progress tracking.

    Args:
        chunks: List of chunk dictionaries
        provider: Embedding provider instance
        batch_size: Number of chunks to process at once

    Returns:
        DataFrame with chunks and embeddings

    Raises:
        AssertionError: If embedding dimension mismatch
        Exception: Any provider error (propagates naturally)
    """
    rows = []
    embedding_dim = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        task = progress.add_task(
            f"[cyan]Generating embeddings (batch_size={batch_size})",
            total=len(chunks)
        )

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Generate embeddings for batch
            texts = [chunk["chunk_text"] for chunk in batch]

            # Use retry wrapper for network resilience
            embeddings = []
            for text in texts:
                embedding = generate_embedding_with_retry(provider, text)
                embeddings.append(embedding)

            # Validate dimension consistency
            for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                if embedding_dim is None:
                    embedding_dim = len(embedding)
                    console.print(f"[dim]   Detected embedding dimension: {embedding_dim}[/dim]")
                else:
                    assert len(embedding) == embedding_dim, \
                        f"Dimension mismatch: chunk {i+j} has {len(embedding)}, expected {embedding_dim}"

                # Create row with all chunk data + embedding
                row = {
                    "chunk_id": chunk["chunk_id"],
                    "source_document": chunk["source_document"],
                    "chapter_title": chunk.get("chapter_title"),
                    "section_title": chunk.get("section_title"),
                    "subsection_title": chunk.get("subsection_title", []),
                    "summary": chunk.get("summary"),
                    "chunk_text": chunk["chunk_text"],
                    "token_count": chunk.get("token_count", 0),
                    "embedding": embedding.tolist(),  # Store as list[float] for readability
                }
                rows.append(row)

            progress.update(task, advance=len(batch))

    # Convert to DataFrame
    df = pd.DataFrame(rows)
    console.print(f"[green]✅ Generated {len(df)} embeddings[/green]")

    return df


def save_to_parquet(
    df: pd.DataFrame,
    output_path: Path,
    provider: EmbeddingProvider,
    model_name: str
) -> None:
    """
    Save DataFrame to Parquet with embedded metadata.

    Metadata includes:
    - embedding_model: Model identifier
    - embedding_dimension: Vector dimension
    - provider_type: Provider name
    - total_chunks: Number of chunks
    - generated_at: Timestamp

    Args:
        df: DataFrame with embeddings
        output_path: Output Parquet file path
        provider: Provider instance (for metadata)
        model_name: Model name/identifier

    Raises:
        AssertionError: If DataFrame is empty or missing required columns
    """
    assert len(df) > 0, "DataFrame is empty"
    assert "embedding" in df.columns, "DataFrame missing 'embedding' column"

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare metadata
    embedding_dim = len(df["embedding"].iloc[0])
    metadata = {
        "embedding_model": model_name,
        "embedding_dimension": str(embedding_dim),
        "provider_type": provider.get_provider_name(),
        "total_chunks": str(len(df)),
        "generated_at": datetime.now().isoformat(),
    }

    # Save to Parquet with metadata
    df.to_parquet(
        output_path,
        index=False,
        compression="snappy",
        engine="pyarrow",
        # Embed metadata in Parquet schema
        # Note: PyArrow stores metadata as bytes, so we encode strings
        metadata_collector=None,  # We'll add metadata via pyarrow directly
    )

    # Add metadata to Parquet file using pyarrow
    import pyarrow.parquet as pq
    import pyarrow as pa

    # Read back the file
    table = pq.read_table(output_path)

    # Add metadata to schema
    metadata_bytes = {k.encode(): v.encode() for k, v in metadata.items()}
    new_schema = table.schema.with_metadata(metadata_bytes)
    new_table = table.cast(new_schema)

    # Write back with metadata
    pq.write_table(new_table, output_path, compression="snappy")

    console.print(f"[green]✅ Saved embeddings to {output_path}[/green]")
    console.print(f"[dim]   Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB[/dim]")
    console.print(f"[dim]   Chunks: {len(df)}[/dim]")
    console.print(f"[dim]   Dimension: {embedding_dim}[/dim]")


@app.command()
def generate(
    input: Annotated[Path, typer.Option(
        ...,
        help="Input directory containing chunk JSON files",
        exists=True,
        file_okay=False,
        dir_okay=True,
    )],
    output: Annotated[Path, typer.Option(
        ...,
        help="Output Parquet file path",
    )],
    provider: Annotated[str, typer.Option(
        "local",
        help="Embedding provider: local, openrouter, aliyun",
    )],
    model: Annotated[str, typer.Option(
        "Qwen/Qwen3-Embedding-0.6B",
        help="Model name/identifier",
    )],
    device: Annotated[str, typer.Option(
        "mps",
        help="Device for local provider: mps, cuda, cpu",
    )],
    batch_size: Annotated[int, typer.Option(
        16,
        help="Batch size for embedding generation",
    )],
) -> None:
    """
    Generate embeddings for all chunks and save to Parquet file.

    This is Stage 1 of the two-stage embedding pipeline:
    1. Generate embeddings → Save to Parquet (this command)
    2. Load Parquet → Ingest to DB (separate command)

    Examples:
        # Generate with local Qwen3 model
        python -m src.embeddings.generate_embeddings \\
            --input data/chunking_final \\
            --output data/embeddings.parquet

        # Generate with OpenRouter API
        python -m src.embeddings.generate_embeddings \\
            --input data/chunking_final \\
            --output data/embeddings.parquet \\
            --provider openrouter

        # Generate with custom batch size
        python -m src.embeddings.generate_embeddings \\
            --input data/chunking_final \\
            --output data/embeddings.parquet \\
            --batch-size 32
    """
    try:
        console.print(Panel.fit(
            "[bold cyan]Stage 1: Generate Embeddings[/bold cyan]\n\n"
            f"Input: {input}\n"
            f"Output: {output}\n"
            f"Provider: {provider}\n"
            f"Model: {model}\n"
            f"Batch size: {batch_size}",
            border_style="cyan"
        ))

        # Load chunks
        chunks = load_chunks_from_directory(input)

        # Load settings for API keys (if needed)
        settings = Settings()

        # Create provider with explicit parameters
        embedding_provider = create_embedding_provider(
            provider_type=provider,
            embedding_model=model,
            device=device,
            openai_api_key=settings.openai_api_key,
            aliyun_api_key=settings.aliyun_api_key
        )

        console.print(f"[cyan]🤖 Provider: {embedding_provider.get_provider_name()}[/cyan]")
        console.print(f"[cyan]📏 Dimension: {embedding_provider.get_embedding_dimension()}[/cyan]")

        # Generate embeddings
        df = generate_embeddings_batch(chunks, embedding_provider, batch_size)

        # Save to Parquet
        save_to_parquet(df, output, embedding_provider, model)

        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold green]✅ Stage 1 Complete![/bold green]")
        console.print("=" * 60)

        summary_table = Table(show_header=False, box=None)
        summary_table.add_row("📂 Input chunks:", str(len(chunks)))
        summary_table.add_row("📊 Embeddings generated:", str(len(df)))
        summary_table.add_row("💾 Output file:", str(output))
        summary_table.add_row("📏 Embedding dimension:", str(embedding_provider.get_embedding_dimension()))

        console.print(summary_table)
        console.print("\n[cyan]Next step: Ingest to database[/cyan]")
        console.print(f"[dim]  python -m src.embeddings.ingest_embeddings --input {output}[/dim]")

    except AssertionError as e:
        console.print(f"[red]❌ Validation error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Fatal error during embedding generation")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
