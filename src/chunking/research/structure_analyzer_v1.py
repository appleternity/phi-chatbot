"""
Structure analyzer for Phase 1: Document structure identification.

This module analyzes document hierarchy using LLM to identify chapters,
sections, and subsections with character-level boundaries.
"""

import hashlib
from typing import Dict, Any, List

from .cache_store import CacheStore
from .llm_provider import LLMProvider
from .models import Document, Structure, Section, StructureAnalysisError


# ============================================================================
# Prompt Template
# ============================================================================

STRUCTURE_ANALYSIS_PROMPT = """You are analyzing a document to identify its hierarchical semantic structure and segment it into meaningful chunks.

Your task: Segment this document into semantically coherent sections that can be used for chunking. Each segment should be ≤ {max_chunk_tokens} tokens and represent a meaningful, self-contained unit of information.

SEGMENTATION STRATEGY:
- Follow natural section boundaries where they exist
- Each segment should be semantically coherent and self-contained
- Segments can be nested (subsections within sections)
- Aim for segments ≤ {max_chunk_tokens} tokens, but prioritize semantic coherence over strict size limits
- If a natural section is too large, identify meaningful subsections within it

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 4 columns:
title	level	parent_title	summary

Column definitions:
- title: Section heading/title (required, no tabs allowed)
- level: Hierarchy level as integer (1=section, 2=subsection, 3=subsubsection)
- parent_title: Parent section title, or "ROOT" for top-level sections
- summary: Brief summary of section content (10-50 words, helps locate content later)

EXAMPLE OUTPUT:
Introduction to Testing	1	ROOT	Overview of software testing fundamentals and importance in development
Why Test?	2	Introduction to Testing	Explains benefits of early bug detection and cost savings
Types of Testing	2	Introduction to Testing	Covers unit, integration, and end-to-end testing approaches
Testing Methodologies	1	ROOT	Different methodologies for organizing and conducting tests
Unit Testing	2	Testing Methodologies	Testing individual components in isolation with examples
Integration Testing	2	Testing Methodologies	Testing component interactions and data flow

IMPORTANT RULES:
1. Output ONLY the TSV data, no explanations or markdown
2. Each line must have exactly 4 tab-separated values
3. No empty lines between data rows
4. Levels must be 1, 2, or 3 only
5. Parent titles must match exactly (case-sensitive)
6. Summaries should be concise (10-50 words) and descriptive
7. Each segment should be ≤ {max_chunk_tokens} tokens when possible
8. Exclude any content that is not part of the main document (e.g., references, transcripts)

DOCUMENT TO ANALYZE:
{document_text}

OUTPUT (TSV format):"""


# ============================================================================
# Structure Analyzer
# ============================================================================


class StructureAnalyzer:
    """Phase 1: Analyze document structure using LLM"""

    def __init__(
        self,
        llm_client: LLMProvider,
        cache_store: CacheStore,
        model: str = "openai/gpt-4o",
        max_chunk_tokens: int = 1000
    ):
        """
        Initialize structure analyzer.

        Args:
            llm_client: LLM provider for making API calls
            cache_store: Cache for storing/retrieving structure analyses
            model: LLM model identifier (default: openai/gpt-4o)
            max_chunk_tokens: Maximum tokens per chunk (default: 1000)
        """
        self.llm_client = llm_client
        self.cache_store = cache_store
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens

    @staticmethod
    def generate_cache_key(content: str, prefix: str = "structure") -> str:
        """
        Generate cache key from content hash.

        Args:
            content: Content to hash
            prefix: Cache key prefix (default: "structure")

        Returns:
            Cache key string (e.g., "structure_abc123...")
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"{prefix}_{content_hash}"

    def generate_llm_response_key(self, content: str, model: str, operation: str) -> str:
        """
        Generate cache key for raw LLM response.

        Args:
            content: Document content
            model: Model identifier
            operation: Operation type (e.g., "structure_analysis")

        Returns:
            Cache key for LLM response
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        model_hash = hashlib.sha256(model.encode()).hexdigest()[:8]
        return f"llm_{operation}_{content_hash}_{model_hash}"

    def analyze(self, document: Document, redo: bool = False) -> Dict[str, Any]:
        """
        Analyze document structure.

        Args:
            document: Input document to analyze
            redo: If True, bypass cache and force reprocessing (default: False)

        Returns:
            Dict with:
                - structure: Structure object with hierarchical organization
                - tokens_consumed: Token count from LLM API call
                - cache_hit: Whether result was from cache
                - llm_response: Raw LLM response text (if available)
                - llm_response_cached: Whether LLM response was from cache

        Raises:
            StructureAnalysisError: If LLM fails or returns invalid structure
        """
        # Generate cache key from document content
        cache_key = self.generate_cache_key(document.content, prefix="structure")

        # Check cache first (unless redo flag is set)
        cached_result = None if redo else self.cache_store.get(cache_key)
        if cached_result is not None:
            try:
                # Reconstruct Structure from cached data
                sections = [Section(**section_data) for section_data in cached_result["sections"]]
                structure = Structure(
                    document_id=cached_result["document_id"],
                    chapter_title=cached_result["chapter_title"],
                    chapter_number=cached_result.get("chapter_number"),
                    sections=sections,
                    metadata={**cached_result.get("metadata", {}), "cache_hit": True},
                    analysis_model=cached_result["analysis_model"]
                )

                # Try to get cached LLM response
                llm_cache_key = self.generate_llm_response_key(
                    document.content, self.model, "structure_analysis"
                )
                cached_llm_response = self.cache_store.get_llm_response(llm_cache_key)

                # Return cached result with zero tokens consumed
                return {
                    "structure": structure,
                    "tokens_consumed": 0,
                    "cache_hit": True,
                    "llm_response": cached_llm_response,
                    "llm_response_cached": cached_llm_response is not None
                }
            except Exception:
                # Cache data corrupted, proceed with fresh analysis
                pass

        # Generate LLM response cache key
        llm_cache_key = self.generate_llm_response_key(
            document.content, self.model, "structure_analysis"
        )

        # Check for cached LLM response (unless redo flag is set)
        content = None
        tokens_consumed = 0
        llm_response_cached = False

        if not redo:
            content = self.cache_store.get_llm_response(llm_cache_key)
            if content is not None:
                llm_response_cached = True

        # If no cached response, call LLM
        if content is None:
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
                    f"LLM API call failed during structure analysis: {str(e)}"
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

            # Cache raw LLM response
            self.cache_store.set_llm_response(llm_cache_key, content)

        # Validate response format
        self._validate_llm_response(content)

        # Parse TSV response
        sections = self._parse_structure_response(content)

        # Extract chapter information (use first top-level section as chapter)
        chapter_title = self._extract_chapter_title(sections)

        # Create Structure object
        structure = Structure(
            document_id=document.document_id,
            chapter_title=chapter_title,
            chapter_number=None,  # Can be extracted from title if needed
            sections=sections,
            metadata={"cache_hit": False},
            analysis_model=self.model
        )

        # Cache result using content-based cache key
        self._cache_structure(cache_key, structure)

        # Return result with token consumption and raw LLM response
        return {
            "structure": structure,
            "tokens_consumed": tokens_consumed,
            "cache_hit": False,
            "llm_response": content,
            "llm_response_cached": llm_response_cached
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
        Parse LLM's TSV response into Section objects.

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
            if len(parts) != 4:
                raise StructureAnalysisError(
                    f"Line {line_num}: Expected 4 columns, got {len(parts)}. "
                    f"Line content: '{line}'"
                )

            title, level_str, parent, summary = parts

            try:
                sections.append(Section(
                    title=title.strip(),
                    level=int(level_str.strip()),
                    parent_section=None if parent.strip() == "ROOT" else parent.strip(),
                    summary=summary.strip()
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

    def _cache_structure(self, cache_key: str, structure: Structure) -> None:
        """
        Cache structure analysis result.

        Args:
            cache_key: Cache key (generated from content hash)
            structure: Structure to cache
        """
        cache_data = {
            "document_id": structure.document_id,
            "chapter_title": structure.chapter_title,
            "chapter_number": structure.chapter_number,
            "sections": [
                {
                    "title": section.title,
                    "level": section.level,
                    "parent_section": section.parent_section,
                    "summary": section.summary
                }
                for section in structure.sections
            ],
            "metadata": structure.metadata,
            "analysis_model": structure.analysis_model
        }

        try:
            self.cache_store.set(cache_key, cache_data)
        except Exception:
            # Caching is optional, don't fail if it errors
            pass
