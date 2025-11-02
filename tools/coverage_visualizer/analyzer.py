#!/usr/bin/env python3
"""
Coverage Analyzer - Analyze LLM chunk extraction coverage

Compares original documents with extracted chunks to identify gaps
and generate visualization data for the Coverage Visualizer frontend.

Token-based matching: Uses word tokenization for accurate position detection
that naturally ignores punctuation and formatting differences.
"""

import argparse
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

# Try to import tqdm for progress bar, fallback if not available
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Fallback: simple progress indicator
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, **kwargs):
            self.iterable = iterable
            self.total = total
            self.desc = desc
            self.n = 0

        def __iter__(self):
            for item in self.iterable:
                yield item
                self.n += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, n=1):
            self.n += n

        def set_postfix_str(self, s):
            pass

# Import nltk for word tokenization (required - no fallback)
try:
    import nltk
    from nltk.tokenize import word_tokenize
    # Ensure punkt tokenizer is available
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("Downloading NLTK punkt tokenizer...")
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
except ImportError as e:
    print("❌ Error: NLTK is required but not installed.", file=sys.stderr)
    print("   Please install it with: pip install nltk", file=sys.stderr)
    sys.exit(1)


class CoverageAnalyzer:
    """Analyzes coverage of chunk extraction from original documents."""

    def __init__(self, threshold: float = 0.90):
        """
        Initialize the coverage analyzer.

        Args:
            threshold: Minimum similarity score (0.0-1.0) for successful match
        """
        self.threshold = threshold
        self.warnings: List[str] = []

    def analyze_coverage(
        self,
        document_path: Path,
        chunks_dir: Path,
        output_path: Path
    ) -> Dict:
        """
        Analyze coverage of chunk extraction.

        Args:
            document_path: Path to original document
            chunks_dir: Directory containing chunk JSON files
            output_path: Output path for coverage report JSON

        Returns:
            Coverage report dictionary
        """
        print(f"Reading document: {document_path.name}")
        document_text = self._read_document(document_path)
        print(f"Document length: {len(document_text)} characters\n")

        print("Scanning chunks directory...")
        chunks_data = self._read_chunks(chunks_dir)
        print(f"Found {len(chunks_data)} chunk files\n")

        print("\nPerforming fuzzy matching...")
        matched_chunks = self._match_chunks(document_text, chunks_data)

        print("\nAnalyzing coverage...")
        coverage_analysis = self._analyze_coverage_map(document_text, matched_chunks)

        print(f"Total characters: {len(document_text)}")
        print(f"Covered: {coverage_analysis['covered_chars']} characters ({coverage_analysis['coverage_percentage']:.2f}%)")
        print(f"Uncovered: {coverage_analysis['uncovered_chars']} characters ({100 - coverage_analysis['coverage_percentage']:.2f}%)\n")

        print(f"Identified {coverage_analysis['total_gaps']} gaps (including small gaps)")
        print(f"Significant gaps (>5 chars): {coverage_analysis['significant_gaps']}\n")

        # Generate final report
        report = self._generate_report(
            document_path,
            chunks_dir,
            document_text,
            matched_chunks,
            coverage_analysis
        )

        # Write output
        self._write_report(output_path, report)
        print(f"✅ Successfully generated JSON report: {output_path}")

        return report

    def _read_document(self, path: Path) -> str:
        """Read original document text."""
        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"❌ Error reading document: {e}", file=sys.stderr)
            sys.exit(1)

    def _read_chunks(self, chunks_dir: Path) -> List[Dict]:
        """Read all chunk JSON files from directory."""
        if not chunks_dir.exists():
            print(f"❌ Chunks directory does not exist: {chunks_dir}", file=sys.stderr)
            sys.exit(1)

        chunk_files = sorted(chunks_dir.glob("*.json"))
        if not chunk_files:
            print(f"⚠️  No chunk files found in {chunks_dir}", file=sys.stderr)
            self.warnings.append(f"No chunk files found in {chunks_dir}")
            return []

        chunks_data = []
        for chunk_file in chunk_files:
            try:
                chunk_json = json.loads(chunk_file.read_text(encoding='utf-8'))

                # Extract required fields
                if 'original_text' not in chunk_json:
                    warning = f"{chunk_file.name}: Missing 'original_text' field"
                    print(f"⚠️  {warning}")
                    self.warnings.append(warning)
                    continue

                chunks_data.append({
                    'file_name': chunk_file.name,
                    'chunk_id': chunk_json.get('chunk_id', chunk_file.stem),
                    'original_text': chunk_json['original_text'],
                    'contextual_prefix': chunk_json.get('contextual_prefix', ''),
                    'metadata': chunk_json.get('metadata', {})
                })

            except json.JSONDecodeError as e:
                warning = f"{chunk_file.name}: JSON parse error - {e}"
                print(f"⚠️  {warning}")
                self.warnings.append(warning)
            except Exception as e:
                warning = f"{chunk_file.name}: Error reading file - {e}"
                print(f"⚠️  {warning}")
                self.warnings.append(warning)

        return chunks_data

    def _match_chunks(self, document_text: str, chunks_data: List[Dict]) -> List[Dict]:
        """
        Match each chunk against the document using fuzzy matching.

        Returns list of matched chunks with positions and similarity scores.
        """
        matched_chunks = []

        # Use tqdm progress bar if available
        with tqdm(total=len(chunks_data), desc="Matching chunks",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  ncols=100) as pbar:
            for chunk in chunks_data:
                chunk_text = chunk['original_text']

                # Find best match position
                match_result = self._find_best_match(chunk_text, document_text)

                similarity_pct = match_result['similarity'] * 100
                status = '✓' if match_result['matched'] else '✗'

                # Update progress bar with status
                pbar.set_postfix_str(f"{status} {chunk['chunk_id']}: {similarity_pct:.1f}%")
                pbar.update(1)

                matched_chunks.append({
                    'chunk_id': chunk['chunk_id'],
                    'file_name': chunk['file_name'],
                    'match_start': match_result['match_start'],
                    'match_end': match_result['match_end'],
                    'similarity': match_result['similarity'],
                    'matched': match_result['matched'],
                    'extracted_text': chunk_text,
                    'contextual_prefix': chunk['contextual_prefix'],
                    'metadata': chunk['metadata']
                })

        # Sort by match_start for sequential display
        matched_chunks.sort(key=lambda x: x['match_start'])

        return matched_chunks

    def _tokenize_with_positions(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Tokenize text and track character positions using NLTK.

        Returns list of (token, start_pos, end_pos) tuples.
        Tokens are lowercased for case-insensitive matching.
        """
        tokens_with_pos = []

        # NLTK word_tokenize with position tracking
        tokens = word_tokenize(text.lower())

        # Find positions of tokens in original text
        search_pos = 0
        for token in tokens:
            # Find token in text (case-insensitive)
            token_lower = token.lower()
            # Look for the token pattern (word boundary)
            pattern = re.compile(re.escape(token_lower), re.IGNORECASE)
            match = pattern.search(text, search_pos)

            if match:
                start = match.start()
                end = match.end()
                tokens_with_pos.append((token_lower, start, end))
                search_pos = end

        return tokens_with_pos

    def _find_best_match(self, chunk_text: str, document_text: str) -> Dict:
        """
        Find best matching position for chunk_text in document_text.

        Token-based matching: Compares word sequences to naturally ignore
        punctuation and formatting differences. Maps token positions back
        to character positions for accurate highlighting.
        """
        if len(chunk_text) == 0:
            return {
                'match_start': 0,
                'match_end': 0,
                'similarity': 0.0,
                'matched': False
            }

        # Tokenize with position tracking
        chunk_tokens_with_pos = self._tokenize_with_positions(chunk_text)
        doc_tokens_with_pos = self._tokenize_with_positions(document_text)

        if not chunk_tokens_with_pos or not doc_tokens_with_pos:
            return {
                'match_start': 0,
                'match_end': len(chunk_text),
                'similarity': 0.0,
                'matched': False
            }

        # Extract just the tokens for matching
        chunk_tokens = [t[0] for t in chunk_tokens_with_pos]
        doc_tokens = [t[0] for t in doc_tokens_with_pos]

        chunk_token_count = len(chunk_tokens)
        doc_token_count = len(doc_tokens)

        # Determine step size based on chunk token count
        if chunk_token_count < 10:
            step = 1
        elif chunk_token_count < 50:
            step = 5
        else:
            step = 10

        best_similarity = 0.0
        best_token_start = 0
        best_token_end = chunk_token_count

        # Sliding window search at token level
        matcher = SequenceMatcher(None, chunk_tokens, [])

        for token_start in range(0, max(1, doc_token_count - chunk_token_count + 1), step):
            token_end = min(token_start + chunk_token_count, doc_token_count)
            window_tokens = doc_tokens[token_start:token_end]

            matcher.set_seq2(window_tokens)
            similarity = matcher.ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_token_start = token_start
                best_token_end = token_end

        # Refine search around best position
        refine_start = max(0, best_token_start - step)
        refine_end = min(doc_token_count - chunk_token_count + 1, best_token_start + step + 1)

        for token_start in range(refine_start, refine_end):
            token_end = min(token_start + chunk_token_count, doc_token_count)
            window_tokens = doc_tokens[token_start:token_end]

            matcher.set_seq2(window_tokens)
            similarity = matcher.ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_token_start = token_start
                best_token_end = token_end

        # Map token positions back to character positions
        # Start: beginning of first token
        # End: end of last token
        char_start = doc_tokens_with_pos[best_token_start][1] if best_token_start < len(doc_tokens_with_pos) else 0
        char_end = doc_tokens_with_pos[best_token_end - 1][2] if best_token_end > 0 and best_token_end <= len(doc_tokens_with_pos) else len(document_text)

        return {
            'match_start': char_start,
            'match_end': char_end,
            'similarity': best_similarity,
            'matched': best_similarity >= self.threshold
        }

    def _analyze_coverage_map(self, document_text: str, matched_chunks: List[Dict]) -> Dict:
        """
        Analyze coverage and identify gaps.

        Returns coverage statistics and gap information.
        """
        doc_len = len(document_text)
        covered = [False] * doc_len

        # Mark covered regions
        for chunk in matched_chunks:
            if chunk['matched']:
                start = chunk['match_start']
                end = chunk['match_end']
                for i in range(start, min(end, doc_len)):
                    covered[i] = True

        # Find gaps
        gaps = []
        gap_start = None

        for i in range(doc_len):
            if not covered[i]:
                if gap_start is None:
                    gap_start = i
            else:
                if gap_start is not None:
                    gaps.append({
                        'start': gap_start,
                        'end': i,
                        'length': i - gap_start
                    })
                    gap_start = None

        # Handle final gap
        if gap_start is not None:
            gaps.append({
                'start': gap_start,
                'end': doc_len,
                'length': doc_len - gap_start
            })

        # Separate significant gaps (length > 5)
        significant_gaps = [g for g in gaps if g['length'] > 5]

        # Add gap content
        for gap in significant_gaps:
            gap['content'] = document_text[gap['start']:gap['end']]

        # Calculate coverage
        covered_chars = sum(covered)
        coverage_percentage = (covered_chars / doc_len * 100) if doc_len > 0 else 0.0

        # Generate coverage map
        coverage_map = self._generate_coverage_map(document_text, matched_chunks, covered)

        return {
            'covered_chars': covered_chars,
            'uncovered_chars': doc_len - covered_chars,
            'coverage_percentage': coverage_percentage,
            'total_gaps': len(gaps),
            'significant_gaps': len(significant_gaps),
            'gaps': significant_gaps,
            'coverage_map': coverage_map
        }

    def _generate_coverage_map(
        self,
        document_text: str,
        matched_chunks: List[Dict],
        covered: List[bool]
    ) -> List[Dict]:
        """
        Generate sequential coverage map with one segment per chunk.

        Creates explicit segments for each matched chunk and fills gaps between them.
        This ensures each chunk is independently highlighted without merging.
        """
        coverage_map = []
        doc_len = len(document_text)

        if doc_len == 0:
            return coverage_map

        # Sort matched chunks by start position
        sorted_chunks = sorted(
            [c for c in matched_chunks if c['matched']],
            key=lambda x: x['match_start']
        )

        if not sorted_chunks:
            # No matched chunks - entire document is a gap
            coverage_map.append({
                'start': 0,
                'end': doc_len,
                'type': 'gap',
                'length': doc_len
            })
            return coverage_map

        # Build coverage map: gaps and chunks
        current_pos = 0

        for chunk in sorted_chunks:
            chunk_start = chunk['match_start']
            chunk_end = chunk['match_end']

            # Add gap before this chunk if exists
            if current_pos < chunk_start:
                coverage_map.append({
                    'start': current_pos,
                    'end': chunk_start,
                    'type': 'gap',
                    'length': chunk_start - current_pos
                })

            # Add chunk segment
            coverage_map.append({
                'start': chunk_start,
                'end': chunk_end,
                'type': 'covered',
                'chunk_id': chunk['chunk_id'],
                'similarity': chunk['similarity']
            })

            # Update position (handle overlaps by taking max)
            current_pos = max(current_pos, chunk_end)

        # Add final gap if exists
        if current_pos < doc_len:
            coverage_map.append({
                'start': current_pos,
                'end': doc_len,
                'type': 'gap',
                'length': doc_len - current_pos
            })

        return coverage_map

    def _generate_report(
        self,
        document_path: Path,
        chunks_dir: Path,
        document_text: str,
        matched_chunks: List[Dict],
        coverage_analysis: Dict
    ) -> Dict:
        """Generate final JSON report with all metadata and data."""
        matched_count = sum(1 for c in matched_chunks if c['matched'])
        unmatched_count = len(matched_chunks) - matched_count

        # Add gap IDs to significant gaps
        for idx, gap in enumerate(coverage_analysis['gaps'], 1):
            gap['gap_id'] = idx

        return {
            'metadata': {
                'document_name': document_path.name,
                'document_path': str(document_path.absolute()),
                'document_length': len(document_text),
                'chunks_directory': str(chunks_dir.absolute()),
                'total_chunks': len(matched_chunks),
                'matched_chunks': matched_count,
                'unmatched_chunks': unmatched_count,
                'coverage_percentage': round(coverage_analysis['coverage_percentage'], 2),
                'total_gaps': coverage_analysis['total_gaps'],
                'significant_gaps': coverage_analysis['significant_gaps'],
                'threshold': self.threshold,
                'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'warnings': self.warnings
            },
            'original_text': document_text,
            'chunks': matched_chunks,
            'gaps': coverage_analysis['gaps'],
            'coverage_map': coverage_analysis['coverage_map']
        }

    def _write_report(self, output_path: Path, report: Dict) -> None:
        """Write coverage report to JSON file."""
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """Command-line interface for coverage analyzer."""
    parser = argparse.ArgumentParser(
        description='Analyze LLM chunk extraction coverage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python analyzer.py \\
    --document data/test/chapter_04.md \\
    --chunks data/chunks/ \\
    --output viewer/data/report.json

  # Custom threshold
  python analyzer.py \\
    --document data/test/chapter_04.md \\
    --chunks data/chunks/ \\
    --output viewer/data/report.json \\
    --threshold 0.95
        """
    )

    parser.add_argument(
        '--document',
        type=Path,
        required=True,
        help='Path to original document (.md, .txt)'
    )

    parser.add_argument(
        '--chunks',
        type=Path,
        required=True,
        help='Directory containing chunk JSON files'
    )

    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output path for coverage report JSON'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.90,
        help='Similarity threshold (0.0-1.0, default: 0.90)'
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.document.exists():
        print(f"❌ Document file does not exist: {args.document}", file=sys.stderr)
        sys.exit(1)

    if not args.chunks.exists():
        print(f"❌ Chunks directory does not exist: {args.chunks}", file=sys.stderr)
        sys.exit(1)

    if not 0.0 <= args.threshold <= 1.0:
        print(f"❌ Threshold must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    analyzer = CoverageAnalyzer(threshold=args.threshold)
    analyzer.analyze_coverage(args.document, args.chunks, args.output)


if __name__ == '__main__':
    main()
