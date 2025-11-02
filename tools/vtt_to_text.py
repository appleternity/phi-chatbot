"""
VTT to Text Converter

Converts WebVTT subtitle files to plain text paragraphs.
Supports single file or batch directory processing.
"""

from pathlib import Path
from typing import Annotated

import typer
from tqdm import tqdm


def extract_text_from_vtt(vtt_path: Path) -> str:
    """
    Extract text content from a VTT file.

    Args:
        vtt_path: Path to the VTT file

    Returns:
        Merged text content as a single paragraph
    """
    text_lines = []

    with open(vtt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip WEBVTT header
            if line.startswith("WEBVTT"):
                continue

            # Skip timestamp lines (contains -->)
            if "-->" in line:
                continue

            # Collect text content
            text_lines.append(line)

    # Merge all text with spaces and normalize whitespace
    merged_text = " ".join(text_lines)

    # Normalize multiple spaces to single space
    while "  " in merged_text:
        merged_text = merged_text.replace("  ", " ")

    return merged_text.strip()


def convert_vtt_file(vtt_path: Path, output_dir: Path) -> bool:
    """
    Convert a single VTT file to text.

    Args:
        vtt_path: Path to the VTT file
        output_dir: Directory to save the output text file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract text
        text = extract_text_from_vtt(vtt_path)

        # Create output path with .txt extension
        output_path = output_dir / f"{vtt_path.stem}.txt"

        # Write text file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        return True
    except Exception as e:
        typer.echo(f"Error processing {vtt_path.name}: {e}", err=True)
        return False


def main(
    input: Annotated[Path, typer.Option(help="Path to VTT file or directory containing VTT files")],
    output_dir: Annotated[Path, typer.Option(help="Output directory for converted text files")],
):
    """
    Convert WebVTT subtitle files to plain text paragraphs.

    Supports single file or batch directory processing with progress bars.
    """
    # Validate input path
    if not input.exists():
        typer.echo(f"Error: Input path does not exist: {input}", err=True)
        raise typer.Exit(code=1)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine if input is file or directory
    if input.is_file():
        # Single file processing
        if not input.suffix == ".vtt":
            typer.echo(f"Error: Input file must be a .vtt file: {input}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Converting: {input.name}")
        success = convert_vtt_file(input, output_dir)

        if success:
            typer.echo(f"✓ Saved to: {output_dir / input.stem}.txt")
        else:
            typer.echo("✗ Conversion failed", err=True)
            raise typer.Exit(code=1)

    elif input.is_dir():
        # Batch directory processing
        vtt_files = sorted(input.glob("*.vtt"))

        if not vtt_files:
            typer.echo(f"Error: No .vtt files found in directory: {input}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Found {len(vtt_files)} VTT files in {input}")
        typer.echo(f"Output directory: {output_dir}")
        typer.echo("")

        # Process all files with progress bar
        success_count = 0
        for vtt_file in tqdm(vtt_files, desc="Converting VTT files"):
            if convert_vtt_file(vtt_file, output_dir):
                success_count += 1

        # Summary
        typer.echo("")
        typer.echo(f"Conversion complete: {success_count}/{len(vtt_files)} files successful")

        if success_count < len(vtt_files):
            typer.echo(f"⚠ {len(vtt_files) - success_count} files failed", err=True)

    else:
        typer.echo(f"Error: Input path is neither a file nor a directory: {input}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
