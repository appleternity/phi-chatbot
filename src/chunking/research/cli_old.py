"""
Command-line interface for document chunking system.

This module provides a Typer-based CLI for processing documents with the
contextual chunking pipeline and managing cache operations.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Annotated

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .cache_store import FileCacheStore
from .structure_analyzer import StructureAnalyzer
from .models import Document

# Initialize Rich console for colored output
console = Console()

# Initialize Typer app
app = typer.Typer(
    name="chunking",
    help="Document chunking system with contextual awareness",
    no_args_is_help=True
)


# ============================================================================
# Helper Functions
# ============================================================================


def _setup_environment() -> str:
    """
    Load environment variables and get API key.

    Returns:
        API key string

    Raises:
        typer.Exit: If API key not found
    """
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] OPENROUTER_API_KEY not found in environment")
        console.print("Please set it in your .env file or environment variables")
        raise typer.Exit(2)
    return api_key


def _setup_components(api_key: str, log_level: str) -> Tuple[Any, Any, Any]:
    """
    Initialize logger, cache store, and LLM provider.

    Args:
        api_key: OpenRouter API key
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Tuple of (logger, cache_store, llm_provider)

    Raises:
        typer.Exit: If imports fail
    """
    # Setup logging (use simple format for CLI)
    from .logger import setup_logging
    logger = setup_logging(log_level, use_context=False)

    # Import and initialize components
    try:
        from .llm_provider import OpenRouterProvider
        cache_store = FileCacheStore()
        llm_provider = OpenRouterProvider(api_key=api_key)
        return logger, cache_store, llm_provider
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to import required modules: {e}")
        raise typer.Exit(1)


def _discover_files(input_path: Path) -> List[Path]:
    """
    Discover files to process from input path.

    Args:
        input_path: Path to file or directory

    Returns:
        List of file paths to process

    Raises:
        typer.Exit: If no files found or invalid path
    """
    if input_path.is_file():
        console.print(f"[cyan]Processing single file:[/cyan] {input_path.name}")
        return [input_path]
    elif input_path.is_dir():
        files = list(input_path.glob("*.txt")) + list(input_path.glob("*.md"))
        if not files:
            console.print(f"[yellow]Warning:[/yellow] No .txt or .md files found in {input_path}")
            raise typer.Exit(0)
        console.print(f"[cyan]Processing folder:[/cyan] {len(files)} files found")
        return files
    else:
        console.print("[red]Error:[/red] Input path must be a file or directory")
        raise typer.Exit(2)


def _write_structure_output(
    structure_data: Dict[str, Any],
    output_path: Path,
    format: str,
    include_stats: bool = False
) -> None:
    """
    Write structure data to file in specified format.

    Args:
        structure_data: Structure dictionary to write
        output_path: Output file path
        format: Output format (json, jsonl, yaml)
        include_stats: Include processing statistics
    """
    if not include_stats and "stats" in structure_data:
        del structure_data["stats"]

    if format == "json":
        output_path.write_text(json.dumps(structure_data, indent=2, default=str))
    elif format == "jsonl":
        output_path.write_text(json.dumps(structure_data, default=str) + "\n")
    elif format == "yaml":
        output_path.write_text(yaml.dump(structure_data, default_flow_style=False))
    else:
        raise ValueError(f"Unsupported format: {format}")


# ============================================================================
# Process Command
# ============================================================================


@app.command()
def process(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to input file or folder containing documents",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for JSONL chunk files",
            resolve_path=True
        )
    ],
    structure_model: Annotated[
        str,
        typer.Option(
            "--structure-model",
            help="Model for Phase 1 structure analysis"
        )
    ] = "openai/gpt-4o",
    extraction_model: Annotated[
        str,
        typer.Option(
            "--extraction-model",
            help="Model for Phase 2 chunk extraction"
        )
    ] = "google/gemini-2.0-flash-exp",
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
            help="Bypass cache and force reprocessing"
        )
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
) -> None:
    """
    Process documents through the chunking pipeline.

    Accepts either a single file or a folder of documents. Output is written
    as JSONL files (one per document) with contextual chunks ready for RAG.
    """
    # Setup environment and components
    api_key = _setup_environment()
    logger, cache_store, llm_provider = _setup_components(api_key, log_level)

    # Validate and create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot create output directory: {e}")
        raise typer.Exit(2)

    # Import pipeline components
    try:
        from .chunking_pipeline import ChunkingPipeline
        from .models import Document
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to import required modules: {e}")
        raise typer.Exit(1)

    # Initialize pipeline
    pipeline = ChunkingPipeline(
        llm_provider=llm_provider,
        cache_store=cache_store,
        structure_model=structure_model,
        extraction_model=extraction_model,
        max_chunk_tokens=max_tokens
    )

    # Discover files to process
    files_to_process = _discover_files(input_path)

    # Process files with progress bar
    total_chunks = 0
    total_errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(
            f"Processing {len(files_to_process)} file(s)...",
            total=len(files_to_process)
        )

        for file_path in files_to_process:
            try:
                progress.update(task, description=f"Processing {file_path.name}...")

                # Load and process document
                document = Document.from_file(file_path)
                result = pipeline.process_document(document, redo=redo)

                # Write output as JSONL (one chunk per line)
                output_file = output_dir / f"{file_path.stem}_chunks.jsonl"
                with output_file.open("w") as f:
                    for chunk in result.chunks:
                        # Convert chunk to dict and write as JSON line
                        f.write(json.dumps(chunk.dict(), default=str) + "\n")

                total_chunks += len(result.chunks)
                logger.info(
                    f"Processed {file_path.name}: {len(result.chunks)} chunks, "
                    f"coverage: {result.text_coverage_ratio:.2%}"
                )

            except Exception as e:
                total_errors += 1
                console.print(f"[red]Error processing {file_path.name}:[/red] {e}")
                logger.error(f"Failed to process {file_path.name}: {e}", exc_info=True)

            progress.advance(task)

    # Summary
    console.print("\n[bold green]Processing complete![/bold green]")
    console.print(f"Files processed: {len(files_to_process) - total_errors}/{len(files_to_process)}")
    if total_errors > 0:
        console.print(f"[yellow]Errors:[/yellow] {total_errors}")
    if total_chunks > 0:
        console.print(f"Total chunks created: {total_chunks}")
    console.print(f"Output directory: {output_dir}")

    # Exit with appropriate code
    if total_errors > 0:
        raise typer.Exit(1)
    raise typer.Exit(0)


# ============================================================================
# Analyze Command (Phase 1 Only)
# ============================================================================


@app.command()
def analyze(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to input file or folder",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for structure JSON files",
            resolve_path=True
        )
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model for structure analysis"
        )
    ] = "openai/gpt-4o",
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
            help="Bypass cache and force reprocessing"
        )
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format (json, jsonl, yaml)"
        )
    ] = "json",
    include_stats: Annotated[
        bool,
        typer.Option(
            "--stats",
            help="Include processing statistics in output"
        )
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
) -> None:
    """
    Analyze document structure (Phase 1 only).

    Outputs hierarchical structure with sections and summaries.
    Results are cached automatically for reuse.
    """
    # Setup environment and components
    api_key = _setup_environment()
    logger, cache_store, llm_provider = _setup_components(api_key, log_level)

    # Validate and create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot create output directory: {e}")
        raise typer.Exit(2)


    # Initialize structure analyzer
    analyzer = StructureAnalyzer(
        llm_client=llm_provider,
        cache_store=cache_store,
        model=model,
        max_chunk_tokens=max_tokens
    )

    # Discover files to process
    files_to_process = _discover_files(input_path)

    # Process files with progress bar
    total_analyzed = 0
    total_errors = 0
    total_tokens = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(
            f"Analyzing {len(files_to_process)} file(s)...",
            total=len(files_to_process)
        )

        for file_path in files_to_process:
            try:
                progress.update(task, description=f"Analyzing {file_path.name}...")

                # Load document
                document = Document.from_file(file_path)

                # Analyze structure
                result = analyzer.analyze(document, redo=redo)

                # Prepare output data
                structure = result["structure"]
                structure_data = {
                    "document_id": structure.document_id,
                    "file_path": str(file_path),
                    "file_hash": document.file_hash,
                    "structure": {
                        "chapter_title": structure.chapter_title,
                        "chapter_number": structure.chapter_number,
                        "sections": [
                            {
                                "title": s.title,
                                "level": s.level,
                                "parent_section": s.parent_section,
                                "summary": s.summary
                            }
                            for s in structure.sections
                        ],
                        "metadata": structure.metadata,
                        "analysis_model": structure.analysis_model,
                        "analyzed_at": structure.analyzed_at.isoformat()
                    }
                }

                # Add stats if requested
                if include_stats:
                    structure_data["stats"] = {
                        "tokens_consumed": result["tokens_consumed"],
                        "cache_hit": result["cache_hit"],
                        "section_count": len(structure.sections),
                        "max_chunk_tokens": max_tokens
                    }

                # Write output
                ext = {"json": ".json", "jsonl": ".jsonl", "yaml": ".yaml"}[format]
                output_path = output_dir / f"{file_path.stem}_structure{ext}"
                _write_structure_output(structure_data, output_path, format, include_stats)

                # Save raw LLM response if available
                llm_response = result.get("llm_response")
                if llm_response:
                    llm_response_path = output_dir / f"{file_path.stem}_structure_llm_response.txt"
                    llm_response_path.write_text(llm_response, encoding="utf-8")
                    cached_label = " (cached)" if result.get("llm_response_cached") else ""
                    logger.info(f"Saved LLM response{cached_label}: {llm_response_path.name}")

                total_analyzed += 1
                total_tokens += result["tokens_consumed"]
                logger.info(
                    f"Analyzed {file_path.name}: {len(structure.sections)} sections, "
                    f"tokens: {result['tokens_consumed']}, cache_hit: {result['cache_hit']}"
                )

            except Exception as e:
                total_errors += 1
                console.print(f"[red]Error analyzing {file_path.name}:[/red] {e}")
                logger.error(f"Failed to analyze {file_path.name}: {e}", exc_info=True)

            progress.advance(task)

    # Summary
    console.print("\n[bold green]Analysis complete![/bold green]")
    console.print(f"Files analyzed: {total_analyzed}/{len(files_to_process)}")
    if total_errors > 0:
        console.print(f"[yellow]Errors:[/yellow] {total_errors}")
    console.print(f"Total tokens consumed: {total_tokens:,}")
    console.print(f"Output directory: {output_dir}")

    # Exit with appropriate code
    if total_errors > 0:
        raise typer.Exit(1)
    raise typer.Exit(0)


# ============================================================================
# Analyze V2 Command (Phase 1 Only with word boundaries)
# ============================================================================


@app.command()
def analyze_v2(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to input file or folder",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for structure JSON files",
            resolve_path=True
        )
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model for structure analysis"
        )
    ] = "openai/gpt-4o",
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
            help="Bypass cache and force reprocessing"
        )
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format (json, jsonl, yaml)"
        )
    ] = "json",
    include_stats: Annotated[
        bool,
        typer.Option(
            "--stats",
            help="Include processing statistics in output"
        )
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
) -> None:
    """
    Analyze document structure with word-based boundaries (V2).

    Outputs hierarchical structure with sections, summaries, and word-based
    boundary markers (start_words/end_words) for improved chunk extraction.
    Results are cached automatically for reuse.
    """
    # Setup environment and components
    api_key = _setup_environment()
    logger, cache_store, llm_provider = _setup_components(api_key, log_level)

    # Validate and create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot create output directory: {e}")
        raise typer.Exit(2)

    # Initialize structure analyzer V2
    from .structure_analyzer_v2 import StructureAnalyzerV2

    analyzer = StructureAnalyzerV2(
        llm_client=llm_provider,
        cache_store=cache_store,
        model=model,
        max_chunk_tokens=max_tokens
    )

    # Discover files to process
    files_to_process = _discover_files(input_path)

    # Process files with progress bar
    total_analyzed = 0
    total_errors = 0
    total_tokens = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(
            f"Analyzing {len(files_to_process)} file(s) with V2...",
            total=len(files_to_process)
        )

        for file_path in files_to_process:
            try:
                progress.update(task, description=f"Analyzing {file_path.name} (V2)...")

                # Load document
                document = Document.from_file(file_path)

                # Analyze structure with V2
                result = analyzer.analyze(document, redo=redo)

                # Prepare output data
                structure = result["structure"]
                structure_data = {
                    "document_id": structure.document_id,
                    "file_path": str(file_path),
                    "file_hash": document.file_hash,
                    "structure": {
                        "chapter_title": structure.chapter_title,
                        "chapter_number": structure.chapter_number,
                        "sections": [
                            {
                                "title": s.title,
                                "level": s.level,
                                "parent_section": s.parent_section,
                                "summary": s.summary,
                                "start_words": s.start_words,
                                "end_words": s.end_words,
                                "is_table": s.is_table
                            }
                            for s in structure.sections
                        ],
                        "metadata": structure.metadata,
                        "analysis_model": structure.analysis_model,
                        "analyzed_at": structure.analyzed_at.isoformat()
                    }
                }

                # Add stats if requested
                if include_stats:
                    structure_data["stats"] = {
                        "tokens_consumed": result["tokens_consumed"],
                        "cache_hit": result["cache_hit"],
                        "section_count": len(structure.sections),
                        "max_chunk_tokens": max_tokens,
                        "version": "v2"
                    }

                # Write output
                ext = {"json": ".json", "jsonl": ".jsonl", "yaml": ".yaml"}[format]
                output_path = output_dir / f"{file_path.stem}_structure_v2{ext}"
                _write_structure_output(structure_data, output_path, format, include_stats)

                # Save raw LLM response if available
                llm_response = result.get("llm_response")
                if llm_response:
                    llm_response_path = output_dir / f"{file_path.stem}_structure_v2_llm_response.txt"
                    llm_response_path.write_text(llm_response, encoding="utf-8")
                    cached_label = " (cached)" if result.get("llm_response_cached") else ""
                    logger.info(f"Saved V2 LLM response{cached_label}: {llm_response_path.name}")

                total_analyzed += 1
                total_tokens += result["tokens_consumed"]
                logger.info(
                    f"Analyzed (V2) {file_path.name}: {len(structure.sections)} sections, "
                    f"tokens: {result['tokens_consumed']}, cache_hit: {result['cache_hit']}"
                )

            except Exception as e:
                total_errors += 1
                console.print(f"[red]Error analyzing {file_path.name} (V2):[/red] {e}")
                logger.error(f"Failed to analyze {file_path.name} (V2): {e}", exc_info=True)

            progress.advance(task)

    # Summary
    console.print("\n[bold green]V2 Analysis complete![/bold green]")
    console.print(f"Files analyzed: {total_analyzed}/{len(files_to_process)}")
    if total_errors > 0:
        console.print(f"[yellow]Errors:[/yellow] {total_errors}")
    console.print(f"Total tokens consumed: {total_tokens:,}")
    console.print(f"Output directory: {output_dir}")

    # Exit with appropriate code
    if total_errors > 0:
        raise typer.Exit(1)
    raise typer.Exit(0)


# ============================================================================
# Extract Command (Phase 2 Only)
# ============================================================================


@app.command()
def extract(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to document file",
            exists=True,
            resolve_path=True
        )
    ],
    structure_path: Annotated[
        Path,
        typer.Option(
            "--structure",
            "-s",
            help="Path to structure JSON from analyze command",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for chunk files",
            resolve_path=True
        )
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model for chunk extraction"
        )
    ] = "google/gemini-2.0-flash-exp",
    max_tokens: Annotated[
        int,
        typer.Option(
            "--max-tokens",
            help="Maximum tokens per chunk",
            min=100,
            max=2000
        )
    ] = 1000,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate",
            help="Validate text coverage after extraction"
        )
    ] = True,
    min_coverage: Annotated[
        float,
        typer.Option(
            "--min-coverage",
            help="Minimum text coverage required",
            min=0.9,
            max=1.0
        )
    ] = 0.99,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
) -> None:
    """
    Extract chunks using pre-analyzed structure (Phase 2 only).

    Requires structure JSON from 'analyze' command.
    Generates contextual chunks with metadata.
    """
    # Setup environment and components
    api_key = _setup_environment()
    logger, cache_store, llm_provider = _setup_components(api_key, log_level)

    # Validate and create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot create output directory: {e}")
        raise typer.Exit(2)

    # Import components
    try:
        from .chunk_extractor import ChunkExtractor
        from .text_aligner import TextAligner
        from .metadata_validator import MetadataValidator
        from .models import Document, Structure, Section, TokenCounter
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to import required modules: {e}")
        raise typer.Exit(1)

    # Load structure from JSON
    try:
        structure_data = json.loads(structure_path.read_text())
        sections = [Section(**s) for s in structure_data["structure"]["sections"]]
        structure = Structure(
            document_id=structure_data["document_id"],
            chapter_title=structure_data["structure"]["chapter_title"],
            chapter_number=structure_data["structure"].get("chapter_number"),
            sections=sections,
            metadata=structure_data["structure"].get("metadata", {}),
            analysis_model=structure_data["structure"]["analysis_model"]
        )
        console.print(f"[cyan]Loaded structure:[/cyan] {len(sections)} sections")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load structure from {structure_path}: {e}")
        raise typer.Exit(2)

    # Load document
    try:
        document = Document.from_file(input_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load document from {input_path}: {e}")
        raise typer.Exit(2)

    # Initialize extractor
    token_counter = TokenCounter()
    metadata_validator = MetadataValidator()
    extractor = ChunkExtractor(
        llm_client=llm_provider,
        token_counter=token_counter,
        metadata_validator=metadata_validator,
        model=model,
        max_chunk_tokens=max_tokens,
        cache_store=cache_store
    )

    # Extract chunks
    console.print(f"[cyan]Extracting chunks from {input_path.name}...[/cyan]")
    try:
        result = extractor.extract_chunks(document, structure)
        chunks = result["chunks"]
        tokens_consumed = result["tokens_consumed"]

        console.print(f"[green]✓[/green] Extracted {len(chunks)} chunks")
        console.print(f"[cyan]Tokens consumed:[/cyan] {tokens_consumed:,}")

        # Validate coverage if requested
        if validate:
            console.print("[cyan]Validating text coverage...[/cyan]")
            coverage_ratio, missing_segments = TextAligner.verify_coverage(
                original_text=document.content,
                chunks=chunks,
                min_coverage=min_coverage
            )
            console.print(f"[green]✓[/green] Coverage: {coverage_ratio:.2%}")

            if coverage_ratio < min_coverage:
                console.print(f"[red]Error:[/red] Coverage {coverage_ratio:.2%} below minimum {min_coverage:.2%}")
                console.print(f"[yellow]Missing segments:[/yellow] {len(missing_segments)}")
                for segment in missing_segments[:5]:  # Show first 5
                    console.print(f"  - {segment[:100]}...")
                raise typer.Exit(3)

        # Write chunks as JSONL
        output_file = output_dir / f"{input_path.stem}_chunks.jsonl"
        with output_file.open("w") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.dict(), default=str) + "\n")

        # Save raw LLM responses if available
        llm_responses = result.get("llm_responses", {})
        if llm_responses:
            llm_responses_dir = output_dir / f"{input_path.stem}_llm_responses"
            llm_responses_dir.mkdir(exist_ok=True)

            for section_title, responses in llm_responses.items():
                # Sanitize section title for filename
                safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in section_title)
                safe_title = safe_title.replace(' ', '_')[:100]  # Limit length

                # Save extraction response
                if responses["extraction"]["response"]:
                    extraction_file = llm_responses_dir / f"{safe_title}_extraction.txt"
                    extraction_file.write_text(responses["extraction"]["response"], encoding="utf-8")

                # Save metadata response
                if responses["metadata"]["response"]:
                    metadata_file = llm_responses_dir / f"{safe_title}_metadata.txt"
                    metadata_file.write_text(responses["metadata"]["response"], encoding="utf-8")

                # Save prefix response
                if responses["prefix"]["response"]:
                    prefix_file = llm_responses_dir / f"{safe_title}_prefix.txt"
                    prefix_file.write_text(responses["prefix"]["response"], encoding="utf-8")

            logger.info(f"Saved LLM responses to: {llm_responses_dir}")

        console.print("\n[bold green]Extraction complete![/bold green]")
        console.print(f"Chunks: {len(chunks)}")
        console.print(f"Output file: {output_file}")
        if llm_responses:
            console.print(f"LLM responses saved to: {llm_responses_dir.name}/")

        logger.info(
            f"Extracted {len(chunks)} chunks from {input_path.name}, "
            f"tokens: {tokens_consumed}, coverage: {coverage_ratio:.2%}"
        )

        raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error extracting chunks:[/red] {e}")
        logger.error(f"Failed to extract chunks: {e}", exc_info=True)
        raise typer.Exit(1)


# ============================================================================
# Extract V2 Command (Phase 2 Only with word-based guidance)
# ============================================================================


@app.command()
def extract_v2(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to document file",
            exists=True,
            resolve_path=True
        )
    ],
    structure_path: Annotated[
        Path,
        typer.Option(
            "--structure",
            "-s",
            help="Path to V2 structure JSON from analyze-v2 command",
            exists=True,
            resolve_path=True
        )
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for chunk files",
            resolve_path=True
        )
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model for chunk extraction"
        )
    ] = "google/gemini-2.0-flash-exp",
    max_tokens: Annotated[
        int,
        typer.Option(
            "--max-tokens",
            help="Maximum tokens per chunk",
            min=100,
            max=2000
        )
    ] = 1000,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate",
            help="Validate text coverage after extraction"
        )
    ] = True,
    min_coverage: Annotated[
        float,
        typer.Option(
            "--min-coverage",
            help="Minimum text coverage required",
            min=0.9,
            max=1.0
        )
    ] = 0.99,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO"
) -> None:
    """
    Extract chunks using V2 structure with word-based boundaries.

    Requires V2 structure JSON from 'analyze-v2' command (with start_words/end_words).
    Generates contextual chunks with improved boundary detection.
    """
    # Setup environment and components
    api_key = _setup_environment()
    logger, cache_store, llm_provider = _setup_components(api_key, log_level)

    # Validate and create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot create output directory: {e}")
        raise typer.Exit(2)

    # Import components
    try:
        from .chunk_extractor_v2 import ChunkExtractorV2
        from .text_aligner import TextAligner
        from .metadata_validator import MetadataValidator
        from .models import Document, Structure, SectionV2, TokenCounter
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to import required modules: {e}")
        raise typer.Exit(1)

    # Load structure from JSON (V2 format with word boundaries)
    try:
        structure_data = json.loads(structure_path.read_text())

        # Check if this is V2 structure (has start_words/end_words)
        first_section = structure_data["structure"]["sections"][0]
        if "start_words" not in first_section or "end_words" not in first_section:
            console.print(
                f"[red]Error:[/red] Structure file does not contain word boundaries (start_words/end_words).\n"
                f"This command requires V2 structure. Please use 'analyze-v2' command to generate V2 structure."
            )
            raise typer.Exit(2)

        sections = [SectionV2(**s) for s in structure_data["structure"]["sections"]]
        structure = Structure(
            document_id=structure_data["document_id"],
            chapter_title=structure_data["structure"]["chapter_title"],
            chapter_number=structure_data["structure"].get("chapter_number"),
            sections=sections,
            metadata=structure_data["structure"].get("metadata", {}),
            analysis_model=structure_data["structure"]["analysis_model"]
        )
        console.print(f"[cyan]Loaded V2 structure:[/cyan] {len(sections)} sections with word boundaries")
    except KeyError as e:
        console.print(f"[red]Error:[/red] Invalid structure format: missing field {e}")
        raise typer.Exit(2)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load structure from {structure_path}: {e}")
        raise typer.Exit(2)

    # Load document
    try:
        document = Document.from_file(input_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load document from {input_path}: {e}")
        raise typer.Exit(2)

    # Initialize V2 extractor
    token_counter = TokenCounter()
    metadata_validator = MetadataValidator()
    extractor = ChunkExtractorV2(
        llm_client=llm_provider,
        token_counter=token_counter,
        metadata_validator=metadata_validator,
        model=model,
        max_chunk_tokens=max_tokens,
        cache_store=cache_store
    )

    # Extract chunks
    console.print(f"[cyan]Extracting chunks from {input_path.name} using V2...[/cyan]")
    try:
        result = extractor.extract_chunks(document, structure)
        chunks = result["chunks"]
        tokens_consumed = result["tokens_consumed"]

        console.print(f"[green]✓[/green] Extracted {len(chunks)} chunks (V2)")
        console.print(f"[cyan]Tokens consumed:[/cyan] {tokens_consumed:,}")

        # Validate coverage if requested
        if validate:
            console.print("[cyan]Validating text coverage...[/cyan]")
            coverage_ratio, missing_segments = TextAligner.verify_coverage(
                original_text=document.content,
                chunks=chunks,
                min_coverage=min_coverage
            )
            console.print(f"[green]✓[/green] Coverage: {coverage_ratio:.2%}")

            if coverage_ratio < min_coverage:
                console.print(f"[red]Error:[/red] Coverage {coverage_ratio:.2%} below minimum {min_coverage:.2%}")
                console.print(f"[yellow]Missing segments:[/yellow] {len(missing_segments)}")
                for segment in missing_segments[:5]:  # Show first 5
                    console.print(f"  - {segment[:100]}...")
                raise typer.Exit(3)

        # Write chunks as JSONL
        output_file = output_dir / f"{input_path.stem}_chunks_v2.jsonl"
        with output_file.open("w") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.dict(), default=str) + "\n")

        # Save raw LLM responses if available
        llm_responses = result.get("llm_responses", {})
        if llm_responses:
            llm_responses_dir = output_dir / f"{input_path.stem}_llm_responses_v2"
            llm_responses_dir.mkdir(exist_ok=True)

            for section_title, responses in llm_responses.items():
                # Sanitize section title for filename
                safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in section_title)
                safe_title = safe_title.replace(' ', '_')[:100]  # Limit length

                # Save extraction response
                if responses["extraction"]["response"]:
                    extraction_file = llm_responses_dir / f"{safe_title}_extraction.txt"
                    extraction_file.write_text(responses["extraction"]["response"], encoding="utf-8")

                # Save metadata response
                if responses["metadata"]["response"]:
                    metadata_file = llm_responses_dir / f"{safe_title}_metadata.txt"
                    metadata_file.write_text(responses["metadata"]["response"], encoding="utf-8")

                # Save prefix response
                if responses["prefix"]["response"]:
                    prefix_file = llm_responses_dir / f"{safe_title}_prefix.txt"
                    prefix_file.write_text(responses["prefix"]["response"], encoding="utf-8")

            logger.info(f"Saved V2 LLM responses to: {llm_responses_dir}")

        console.print("\n[bold green]V2 Extraction complete![/bold green]")
        console.print(f"Chunks: {len(chunks)}")
        console.print(f"Output file: {output_file}")
        if llm_responses:
            console.print(f"LLM responses saved to: {llm_responses_dir.name}/")

        logger.info(
            f"Extracted (V2) {len(chunks)} chunks from {input_path.name}, "
            f"tokens: {tokens_consumed}, coverage: {coverage_ratio:.2%}"
        )

        raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error extracting chunks (V2):[/red] {e}")
        logger.error(f"Failed to extract chunks (V2): {e}", exc_info=True)
        raise typer.Exit(1)


# ============================================================================
# Validate Command
# ============================================================================


@app.command()
def validate(
    input_path: Annotated[
        Path,
        typer.Argument(help="Path to structure JSON or chunks JSONL"),
    ],
    type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Validation type (structure, chunks, auto)"
        )
    ] = "auto",
    document_path: Annotated[
        Optional[Path],
        typer.Option(
            "--document",
            "-d",
            help="Original document for coverage validation"
        )
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Fail on any validation warning"
        )
    ] = False
) -> None:
    """
    Validate structure or chunks for completeness and quality.

    Checks metadata, hierarchy, coverage, and token counts.
    """
    # Detect type if auto
    if type == "auto":
        if "structure" in input_path.name:
            type = "structure"
        elif "chunks" in input_path.name:
            type = "chunks"
        else:
            console.print("[yellow]Warning:[/yellow] Cannot auto-detect type, assuming chunks")
            type = "chunks"

    console.print(f"[cyan]Validating {type}:[/cyan] {input_path.name}")

    warnings = []
    errors = []

    if type == "structure":
        # Validate structure
        try:
            structure_data = json.loads(input_path.read_text())
            sections = structure_data["structure"]["sections"]

            # Check hierarchy
            section_titles = {s["title"] for s in sections}
            for section in sections:
                parent = section.get("parent_section")
                if parent and parent != "ROOT" and parent not in section_titles:
                    errors.append(f"Section '{section['title']}' references non-existent parent '{parent}'")

            # Check summaries
            for section in sections:
                if len(section.get("summary", "")) < 10:
                    warnings.append(f"Section '{section['title']}' has short summary")

            console.print(f"[green]✓[/green] Structure has {len(sections)} sections")

        except Exception as e:
            errors.append(f"Failed to load structure: {e}")

    elif type == "chunks":
        # Validate chunks
        try:
            chunks = []
            with input_path.open("r") as f:
                for line in f:
                    chunks.append(json.loads(line))

            # Check metadata completeness
            for i, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {})
                if not metadata.get("chapter_title"):
                    errors.append(f"Chunk {i+1} missing chapter_title")
                if not metadata.get("section_title"):
                    errors.append(f"Chunk {i+1} missing section_title")
                if not metadata.get("summary"):
                    warnings.append(f"Chunk {i+1} missing summary")

                # Check token count
                token_count = chunk.get("token_count", 0)
                if token_count > 1000:
                    errors.append(f"Chunk {i+1} exceeds token limit: {token_count}")

            console.print(f"[green]✓[/green] Found {len(chunks)} chunks")

            # Validate coverage if document provided
            if document_path:
                console.print("[cyan]Validating text coverage...[/cyan]")
                from .models import Document, Chunk
                from .text_aligner import TextAligner

                document = Document.from_file(document_path)
                chunk_objects = [Chunk(**c) for c in chunks]

                coverage_ratio, missing_segments = TextAligner.verify_coverage(
                    original_text=document.content,
                    chunks=chunk_objects,
                    min_coverage=0.99
                )

                console.print(f"[cyan]Coverage:[/cyan] {coverage_ratio:.2%}")

                if coverage_ratio < 0.99:
                    errors.append(f"Coverage {coverage_ratio:.2%} below 99%")
                    console.print(f"[yellow]Missing segments:[/yellow] {len(missing_segments)}")

        except Exception as e:
            errors.append(f"Failed to load chunks: {e}")

    # Display results
    console.print()
    if warnings:
        console.print(f"[yellow]Warnings:[/yellow] {len(warnings)}")
        for warning in warnings[:10]:
            console.print(f"  - {warning}")
        if len(warnings) > 10:
            console.print(f"  ... and {len(warnings)-10} more")

    if errors:
        console.print(f"[red]Errors:[/red] {len(errors)}")
        for error in errors[:10]:
            console.print(f"  - {error}")
        if len(errors) > 10:
            console.print(f"  ... and {len(errors)-10} more")

    # Summary
    if not errors and not warnings:
        console.print("[bold green]✓ Validation passed![/bold green]")
        raise typer.Exit(0)
    elif errors:
        console.print("\n[bold red]✗ Validation failed[/bold red]")
        raise typer.Exit(3)
    elif strict:
        console.print("\n[bold yellow]✗ Validation failed (strict mode)[/bold yellow]")
        raise typer.Exit(3)
    else:
        console.print("\n[bold yellow]⚠ Validation passed with warnings[/bold yellow]")
        raise typer.Exit(0)


# ============================================================================
# Cache Command
# ============================================================================


@app.command()
def cache(
    stats: Annotated[
        bool,
        typer.Option(
            "--stats",
            help="Display cache statistics"
        )
    ] = False,
    clear: Annotated[
        bool,
        typer.Option(
            "--clear",
            help="Clear all cached data"
        )
    ] = False
) -> None:
    """
    Manage cache operations for structure analysis.

    Use --stats to view cache statistics or --clear to remove all cached data.
    """
    cache_store = FileCacheStore()

    if not stats and not clear:
        console.print("[yellow]Please specify either --stats or --clear[/yellow]")
        console.print("Use: chunking cache --stats  OR  chunking cache --clear")
        raise typer.Exit(0)

    if stats:
        # Display cache statistics
        stats_data = cache_store.get_stats()

        console.print("\n[bold cyan]Cache Statistics[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Cache Directory", stats_data["cache_dir"])
        table.add_row("Structure Files", str(stats_data.get("structure_files", 0)))
        table.add_row("LLM Response Files", str(stats_data.get("llm_response_files", 0)))
        table.add_row(
            "Total Files",
            str(stats_data.get("structure_files", 0) + stats_data.get("llm_response_files", 0))
        )
        table.add_row(
            "Structure Size",
            f"{stats_data.get('structure_size_bytes', 0):,} bytes "
            f"({stats_data.get('structure_size_bytes', 0) / 1024:.2f} KB)"
        )
        table.add_row(
            "LLM Response Size",
            f"{stats_data.get('llm_response_size_bytes', 0):,} bytes "
            f"({stats_data.get('llm_response_size_bytes', 0) / 1024:.2f} KB)"
        )
        table.add_row(
            "Total Size",
            f"{stats_data['total_size_bytes']:,} bytes "
            f"({stats_data['total_size_bytes'] / 1024:.2f} KB)"
        )

        console.print(table)
        console.print()

    if clear:
        # Confirm and clear cache
        if typer.confirm("Are you sure you want to clear all cached data?"):
            deleted_count = cache_store.clear()
            console.print(f"[green]✓[/green] Cleared {deleted_count} cached file(s)")
        else:
            console.print("[yellow]Cache clear cancelled[/yellow]")

    raise typer.Exit(0)


# ============================================================================
# Entry Point
# ============================================================================


def main() -> None:
    """Entry point for CLI application"""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
