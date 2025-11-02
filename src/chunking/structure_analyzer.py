"""
Structure analyzer for Phase 1: Document structure identification with word boundaries.

This module analyzes document hierarchy using LLM to identify chapters,
sections, and subsections with word-based boundary markers (start_words/end_words)
for improved chunk extraction accuracy.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from .llm_provider import LLMProvider
from .models import Document, Structure, Section, StructureAnalysisError


# ============================================================================
# Prompt Template (7-column TSV with start_words/end_words/is_table)
# ============================================================================

STRUCTURE_ANALYSIS_PROMPT = """You are analyzing a document to identify its hierarchical semantic structure and segment it into meaningful chunks.

Your task: Segment this document into semantically coherent sections that can be used for chunking. Each segment should be ≤ {max_chunk_tokens} tokens and represent a meaningful, self-contained unit of information.

SEGMENTATION STRATEGY:
- Follow natural section boundaries where they exist
- **TABLES**: Each table should be identified as a separate segment with its own entry
- Each segment should be semantically coherent and self-contained
- Sections are organized hierarchically (subsections subdivide their parent sections)
- **CRITICAL**: Segments must NOT overlap - each word belongs to exactly one section
- If a section has subsections, its content is the union of its children's content
- If it is a header-only section, it should have no content. Let's only include its subsections only
- Parent sections are subdivided by their child sections (the parent's content is the union of its children)
- Aim for segments ≤ {max_chunk_tokens} tokens, but prioritize semantic coherence over strict size limits
- If a natural section is too large, identify meaningful subsections to subdivide it

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 7 columns:
title	level	parent_title	summary	start_words	end_words	is_table

Column definitions:
- title: Section heading/title (required, no tabs allowed). For tables, use descriptive title like "Table: [Description]"
- level: Hierarchy level as integer (1=section, 2=subsection, 3=subsubsection)
- parent_title: Parent section title, or "ROOT" for top-level sections
- summary: Brief summary of section content (10-50 words, helps locate content later)
- start_words: First 3-8 words of section CONTENT (not title), used for fuzzy boundary matching. Use "[EMPTY]" if section is title-only (no body content).
- end_words: Last 3-8 words of section content, used for fuzzy boundary matching. Use "[EMPTY]" if section is title-only (no body content).
- is_table: "true" if this segment is a table, "false" otherwise

EXAMPLE OUTPUT:
Introduction to Testing	1	ROOT	Overview of software testing fundamentals and importance in development	Software testing is a critical	quality and reliability in production	false
Why Test?	2	Introduction to Testing	Explains benefits of early bug detection and cost savings	Early detection of bugs	reduces maintenance costs significantly	false
Table: Test Coverage Metrics	2	Introduction to Testing	Table showing different coverage types and their target percentages	| Coverage Type | Target	95% | Good |	false
Types of Testing	2	Introduction to Testing	Covers unit, integration, and end-to-end testing approaches	[EMPTY]	[EMPTY]	false
Testing Methodologies	1	ROOT	Different methodologies for organizing and conducting tests	Modern testing approaches emphasize	automation and continuous integration	false

Note: Line 3 is a table segment - it will be extracted as markdown table format.
Unit Testing	2	Testing Methodologies	Testing individual components in isolation with examples	Unit tests focus on	ensuring correctness at component level	false
Integration Testing	2	Testing Methodologies	Testing component interactions and data flow	Integration tests verify that	components work together correctly	false

CRITICAL RULES FOR start_words AND end_words:
1. If section is TITLE-ONLY (header with no body content before subsections), output "[EMPTY]" for BOTH start_words and end_words
   - Use the exact text: [EMPTY] (including square brackets)
   - This makes empty fields explicit and visible
2. For tables: Use the first/last words from the table content (including headers/data)
3. Otherwise, extract 3-8 consecutive words that ACTUALLY APPEAR in the section content
4. DO NOT include the section title in start_words - use the first content words AFTER the title
5. These are for FUZZY MATCHING, not exact quotes:
   - Minor paraphrasing for better formatting is acceptable (e.g., "software\ntesting" vs "software testing")
   - Capitalization differences are acceptable
   - Small punctuation variations are acceptable
6. For end_words, avoid pure punctuation or filler words - include text up to 3-8 meaningful content words

GENERAL TSV RULES:
1. Output ONLY the TSV data, no explanations or markdown code blocks (no ``` )
2. Each line must have exactly 7 tab-separated values
3. No empty lines between data rows
4. Levels must be 1, 2, or 3 only
5. Parent titles must match exactly (case-sensitive)
6. Summaries should be concise (10-50 words) and descriptive
7. Each segment should be ≤ {max_chunk_tokens} tokens when possible
8. is_table must be exactly "true" or "false" (lowercase)
9. Exclude any content that is not part of the main document (e.g., references, transcripts, footnotes)

DOCUMENT TO ANALYZE:
{document_text}

OUTPUT (TSV format):"""


# ============================================================================
# Structure Analyzer
# ============================================================================


class StructureAnalyzer:
    """Phase 1: Analyze document structure using LLM with word-based boundaries"""

    def __init__(
        self,
        llm_client: LLMProvider,
        model: str = "openai/gpt-4o",
        max_chunk_tokens: int = 1000,
        output_dir: Path = None
    ):
        """
        Initialize structure analyzer V2.

        Args:
            llm_client: LLM provider for making API calls
            model: LLM model identifier (default: openai/gpt-4o)
            max_chunk_tokens: Maximum tokens per chunk (default: 1000)
            output_dir: Base output directory for checking existing structure files
        """
        self.llm_client = llm_client
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.output_dir = Path(output_dir) if output_dir else None

    def analyze(self, document: Document, redo: bool = False) -> Dict[str, Any]:
        """
        Analyze document structure with word-based boundaries (V2).

        Args:
            document: Input document to analyze
            redo: If True, force reprocessing even if output file exists (default: False)

        Returns:
            Dict with:
                - structure: Structure object with hierarchical organization
                - tokens_consumed: Token count from LLM API call (0 if loaded from file)
                - cache_hit: Whether result was loaded from existing output file

        Raises:
            StructureAnalysisError: If LLM fails or returns invalid structure
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check if structure file already exists (unless redo flag is set)
        if self.output_dir and not redo:
            structure_file = self.output_dir / document.document_id / f"{document.document_id}_structure.json"
            if structure_file.exists():
                try:
                    logger.info(f"Structure file exists, loading from: {structure_file}")

                    # Load and validate structure file
                    with open(structure_file, 'r') as f:
                        structure_data = json.load(f)

                    # Reconstruct Structure from file
                    sections = [Section(**section_data) for section_data in structure_data["sections"]]
                    structure = Structure(
                        document_id=structure_data["document_id"],
                        chapter_title=structure_data["chapter_title"],
                        chapter_number=structure_data.get("chapter_number"),
                        sections=sections,
                        metadata={**structure_data.get("metadata", {}), "cache_hit": True},
                        analysis_model=structure_data["analysis_model"]
                    )

                    # Return loaded result with zero tokens consumed
                    return {
                        "structure": structure,
                        "tokens_consumed": 0,
                        "cache_hit": True
                    }
                except Exception as e:
                    # File corrupted or invalid, proceed with fresh analysis
                    logger.warning(f"Failed to load structure file, will regenerate: {e}")

        # No existing file or redo=True, perform fresh analysis
        # Format prompt with document content and max_chunk_tokens
        prompt = STRUCTURE_ANALYSIS_PROMPT.format(
            document_text=document.content,
            max_chunk_tokens=self.max_chunk_tokens
        )

        # Call LLM
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  # Lower temperature for structured output
            )
        except Exception as e:
            raise StructureAnalysisError(
                f"LLM API call failed during structure analysis (V2): {str(e)}"
            ) from e

        # Extract token usage from response
        try:
            usage = response.get("usage", {})
            tokens_consumed = usage.get("total_tokens", 0)
        except Exception:
            # Token tracking is optional, don't fail if unavailable
            pass

        # Extract response content
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise StructureAnalysisError(
                f"Invalid LLM response format: {str(e)}"
            ) from e

        # Validate response format
        self._validate_llm_response(content)

        # Parse TSV response (6 columns for V2)
        sections = self._parse_structure_response(content)

        # Extract chapter information (use first top-level section as chapter)
        chapter_title = self._extract_chapter_title(sections)

        # Create Structure object
        structure = Structure(
            document_id=document.document_id,
            chapter_title=chapter_title,
            chapter_number=None,  # Can be extracted from title if needed
            sections=sections,
            metadata={
                "cache_hit": False,
                "version": "v2",  # Mark as V2 structure
                "has_word_boundaries": True
            },
            analysis_model=self.model
        )

        # Return result with token consumption
        return {
            "structure": structure,
            "tokens_consumed": tokens_consumed,
            "cache_hit": False
        }

    def _validate_llm_response(self, response: str) -> None:
        """
        Validate LLM response before parsing.

        Args:
            response: Raw LLM response content

        Raises:
            StructureAnalysisError: If response format is invalid
        """
        if not response or not response.strip():
            raise StructureAnalysisError("LLM returned empty response")

        # Check for common LLM mistakes
        if response.strip().startswith("```"):
            raise StructureAnalysisError(
                "LLM returned markdown code block. "
                "Expected plain TSV output without formatting."
            )

        if response.strip().lower().startswith("here is") or \
           response.strip().lower().startswith("here are"):
            raise StructureAnalysisError(
                "LLM added preamble. Expected direct TSV output only."
            )

    def _parse_structure_response(self, response_text: str) -> List[Section]:
        """
        Parse LLM's TSV response into Section objects (7 columns).

        Args:
            response_text: Raw TSV response from LLM

        Returns:
            List of Section objects

        Raises:
            StructureAnalysisError: If parsing fails
        """
        sections = []
        lines = response_text.strip().split('\n')

        # Clean up common LLM formatting issues
        cleaned_lines = []
        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip markdown code block delimiters
            if line.startswith('```'):
                continue

            # Skip TSV header lines (case-insensitive check for header keywords)
            line_lower = line.lower()
            if ('title' in line_lower and 'level' in line_lower and
                'parent' in line_lower and 'summary' in line_lower):
                # This looks like a header line, skip it
                continue

            cleaned_lines.append(line)

        # Parse cleaned lines
        for line_num, line in enumerate(cleaned_lines, 1):
            parts = line.split('\t')
            if len(parts) != 7:
                raise StructureAnalysisError(
                    f"Line {line_num}: Expected 7 columns (V2 format with is_table), got {len(parts)}. "
                    f"Line content: '{line}'"
                )

            title, level_str, parent, summary, start_words, end_words, is_table_str = parts

            # Convert [EMPTY] sentinel to empty string
            start_words_clean = "" if start_words.strip() == "[EMPTY]" else start_words.strip()
            end_words_clean = "" if end_words.strip() == "[EMPTY]" else end_words.strip()
            
            # Parse is_table boolean
            is_table = is_table_str.strip().lower() == "true"

            try:
                sections.append(Section(
                    title=title.strip(),
                    level=int(level_str.strip()),
                    parent_section=None if parent.strip() == "ROOT" else parent.strip(),
                    summary=summary.strip(),
                    start_words=start_words_clean,
                    end_words=end_words_clean,
                    is_table=is_table
                ))
            except ValueError as e:
                raise StructureAnalysisError(
                    f"Line {line_num}: Invalid data - {e}. Line: '{line}'"
                ) from e

        if not sections:
            raise StructureAnalysisError(
                "No valid sections found in LLM response"
            )

        return sections

    def _extract_chapter_title(self, sections: List[Section]) -> str:
        """
        Extract chapter title from sections.

        Args:
            sections: List of sections

        Returns:
            Chapter title (first top-level section title or "Unknown Chapter")
        """
        # Find first level-1 section
        for section in sections:
            if section.level == 1:
                return section.title

        # Fallback: use first section title
        if sections:
            return sections[0].title

        return "Unknown Chapter"
