"""
Chunk extraction for Phase 2: Extract and enrich document chunks with context.

Architecture:
- 2 LLM calls per section: extract text → generate contextual prefix
- Metadata derived from Phase 1 structure (no LLM call needed)
- Document-first prompt structure for future caching optimization
- Skips title-only sections automatically
"""

import json
from typing import Dict, Any, List

from tqdm import tqdm

from .llm_provider import LLMProvider
from .models import (
    Chunk,
    ChunkMetadata,
    Document,
    ProcessingMetadata,
    ChunkExtractionError,
    Structure,
    Section,
    TokenCounter,
)


# ============================================================================
# Metadata Derivation (No LLM Needed!)
# ============================================================================

def derive_metadata_from_structure(
    structure: Structure,
    section: Section
) -> ChunkMetadata:
    """
    Derive chunk metadata from Phase 1 structure (no LLM call needed).

    This eliminates the redundant metadata generation step by reusing
    information already produced in Phase 1 structure analysis.

    Args:
        structure: Document structure from Phase 1
        section: Current section being processed

    Returns:
        ChunkMetadata with fields derived from Phase 1 data

    Derivation Logic:
        - chapter_title: From structure.chapter_title (already computed)
        - section_title: From section.title (already known)
        - subsection_title: From hierarchy (find ALL child sections)
        - summary: From section.summary (already generated in Phase 1!)
    """
    # Find ALL subsection titles from hierarchy
    subsection_titles = []

    # Collect all direct children (one level deeper)
    for s in structure.sections:
        if s.parent_section == section.title and s.level == section.level + 1:
            subsection_titles.append(s.title)

    return ChunkMetadata(
        chapter_title=structure.chapter_title,
        section_title=section.title,
        subsection_title=subsection_titles,  # ← List of all subsections!
        summary=section.summary  # ← Reuse Phase 1 summary!
    )


# ============================================================================
# Instruction Templates (No Document Text - For Cache Optimization)
# ============================================================================

# - Section ENDS near: "{end_words}" was removed cause it created confusion
EXTRACTION_INSTRUCTIONS = """You are extracting a specific section of text from the above document for chunking purposes.

Your task: Extract and format the complete text for the section described below. Output EXACTLY as it appears in the document, preserving all content but with clean formatting.

TARGET SECTION:
- Title: {section_title}
- Summary: {section_summary}
- Is Table: {is_table}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"

Note: These boundary hints are approximate guides, not exact quotes. The actual text may have minor variations in capitalization, punctuation, or word order. Use them to locate the general boundaries, then extract the complete section content.

EXTRACTION RULES:
1. Output the COMPLETE text for this section - do NOT summarize or paraphrase
2. Include ALL content from this section
3. Use the boundary hints to identify where this section starts and ends:
   - Find text that closely matches the start_words (allowing for minor variations)
   - Find text that closely matches the end_words (allowing for minor variations)
   - Extract everything between these boundaries

**TABLE HANDLING:**
- If Is Table = true: Focus ONLY on the table structure. Extract as clean markdown table format.
  - Include table headers and all rows
  - Preserve column alignment where possible
  - Exclude any surrounding text that is not part of the table
  - Format as proper markdown table with | separators
- If Is Table = false: Focus on textual content and EXCLUDE any tables found in this section.
  - Extract all prose, paragraphs, lists, etc.
  - Skip over any tables (they will be separate table segments)
  - Preserve formatting of non-table content

4. You MAY clean up formatting:
   - Normalize whitespace and line breaks
   - Fix obvious typos
   - Add markdown structure (headers, lists) if helpful
   - For tables: ensure proper markdown table syntax
5. Do NOT:
   - Summarize or condense content
   - Skip any content from the target section (unless it's a table in non-table segment)
   - Add content not in the original section
   - Include content from other sections (respect the boundaries!)
6. Output ONLY the extracted text, no explanations or preamble

OUTPUT (extracted section text):"""


PREFIX_INSTRUCTIONS = """Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk.
Answer only with the succinct context and nothing else.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}
- Subsections: {subsection_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Plain text (single sentence, ideally 30-100 words, no special formatting)

EXAMPLE CHUNK TEXT:
The company's revenue grew by 3% over the previous quarter.

EXAMPLE OUTPUT:
This chunk is from an SEC filing on ACME corp's performance in Q2 2023; the previous quarter's revenue was $314 million. The company's revenue grew by 3% over the previous quarter.

GUIDELINES:
1. Output ONLY the contextual sentence, no explanations
2. Be specific but concise (aim for 30-100 words)
3. Do not include the full chunk text in the prefix

OUTPUT (contextual prefix):"""


# ============================================================================
# Chunk Extractor
# ============================================================================

class ChunkExtractor:
    """
    Chunk extractor for Phase 2: Extract and enrich document chunks.

    Architecture:
        - 2 LLM calls per section: extract → prefix
        - Both calls start with document text for cache efficiency
        - Metadata derived from Phase 1 structure (no LLM call)
        - Plain text output for both operations
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        model: str = "anthropic/claude-haiku-4.5",
        max_chunk_tokens: int = 1000,
        output_dir=None,
        document_id: str = None
    ):
        """Initialize chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.output_dir = output_dir
        self.document_id = document_id

    def _build_cached_message(
        self,
        document_text: str,
        instructions: str
    ) -> list[dict[str, Any]]:
        """
        Build multipart message with cache_control for OpenRouter.

        Args:
            document_text: Full document content (STATIC - will be cached)
            instructions: Operation instructions with params (DYNAMIC - not cached)

        Returns:
            Message list with cache_control breakpoint

        Structure:
            Part 1: Document text with cache_control (CACHED after first call)
            Part 2: Instructions (NOT CACHED, changes per section)
        """
        return [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"DOCUMENT TEXT:\n{document_text}",
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": f"\n---\n\n{instructions}"
                }
            ]
        }]

    def extract_chunks(
        self,
        document: Document,
        structure: Structure,
        redo: bool = False
    ) -> Dict[str, Any]:
        """
        Extract chunks from document (2 calls + derived metadata).

        Args:
            document: Document to extract chunks from
            structure: Document structure from Phase 1
            redo: If True, force reprocessing even if chunk files exist (default: False)

        Returns dict with chunks, tokens_consumed, and llm_responses.
        """
        # Validate inputs
        if not structure.sections:
            raise ChunkExtractionError("No sections provided for extraction")

        # Check for V2 format (word boundaries)
        first_section = structure.sections[0]
        if not hasattr(first_section, 'start_words') or not hasattr(first_section, 'end_words'):
            raise ChunkExtractionError(
                "Structure does not contain word boundaries (start_words/end_words). "
                "Use StructureAnalyzer to generate compatible structures."
            )

        chunks = []
        total_tokens_consumed = 0

        import logging
        logger = logging.getLogger(__name__)

        # Count total sections to process (skip title-only)
        sections_to_process = [s for s in structure.sections if s.start_words or s.end_words]

        # Progress bar
        pbar = tqdm(sections_to_process, desc="Extracting chunks", unit="section")

        # Extract chunk for each section
        for i, section in enumerate(pbar):
            try:
                # Update progress bar description
                pbar.set_postfix_str(f"{section.title[:40]}...")

                # Check if chunk file already exists (unless redo flag is set)
                chunk_number = i + 1
                chunk_file = None
                if self.output_dir and not redo:
                    chunk_file = self.output_dir / f"{document.document_id}_chunk_{chunk_number:03d}.json"
                    if chunk_file.exists():
                        try:
                            # Validate file can be parsed
                            with open(chunk_file, 'r') as f:
                                chunk_data = json.load(f)
                            chunk = Chunk(**chunk_data)
                            logger.info(f"Chunk {chunk_number} exists and valid, skipping: {chunk_file}")
                            chunks.append(chunk)
                            continue
                        except Exception as e:
                            logger.warning(f"Chunk {chunk_number} exists but invalid, will regenerate: {e}")

                # Get is_table flag (default to False for backward compatibility)
                is_table = getattr(section, 'is_table', False)

                # Extract text
                extraction_result = self._extract_section_text(
                    document,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens,
                    is_table=is_table
                )
                extracted_text = extraction_result["extracted_text"]
                total_tokens_consumed += extraction_result.get("tokens_consumed", 0)

                # Derive metadata from Phase 1 (no LLM call!)
                metadata = derive_metadata_from_structure(structure, section)

                # Generate contextual prefix
                prefix_result = self._generate_contextual_prefix(
                    document.document_id,
                    metadata.chapter_title,
                    metadata.section_title,
                    metadata.subsection_title,
                    extracted_text,
                    document.content
                )
                contextual_prefix = prefix_result["prefix"]
                total_tokens_consumed += prefix_result.get("tokens_consumed", 0)

                # Combine prefix with extracted text
                chunk_text = f"{contextual_prefix}\n\n{extracted_text}"

                # Count tokens
                token_count = self.token_counter.count_tokens(chunk_text, self.model)

                # Warn if token limit exceeded
                if token_count > self.max_chunk_tokens * 3:
                    logger.debug(f"Chunk '{section.title}' has {token_count} tokens (>{self.max_chunk_tokens*3})")

                # Create chunk
                chunk_id = f"{document.document_id}_chunk_{i+1:03d}"
                cache_hit = structure.metadata.get("cache_hit", False)

                processing_metadata = ProcessingMetadata(
                    phase_1_model=structure.analysis_model,
                    phase_2_model=self.model,
                    cache_hit=cache_hit
                )

                chunk = Chunk(
                    chunk_id=chunk_id,
                    source_document=document.document_id,
                    chunk_text=chunk_text,
                    original_text=extracted_text,
                    contextual_prefix=contextual_prefix,
                    metadata=metadata,
                    token_count=token_count,
                    processing_metadata=processing_metadata
                )

                chunks.append(chunk)

                # Write chunk to file immediately (progressive output)
                if self.output_dir:
                    chunk_file = self.output_dir / f"{document.document_id}_chunk_{i+1:03d}.json"
                    chunk_file.write_text(json.dumps(chunk.dict(), default=str, indent=2))

            except Exception as e:
                if isinstance(e, (ChunkExtractionError, ValueError)):
                    raise
                raise ChunkExtractionError(
                    f"Failed to extract chunk for section '{section.title}': {str(e)}"
                ) from e

        pbar.close()
        logger.info(f"Extracted {len(chunks)} chunks, {total_tokens_consumed:,} tokens")

        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed
        }

    def _extract_section_text(
        self,
        document: Document,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int,
        is_table: bool = False
    ) -> Dict[str, Any]:
        """Extract text for section using LLM (plain text output)."""
        # Build instructions with dynamic params
        instructions = EXTRACTION_INSTRUCTIONS.format(
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words,
            is_table=is_table
        )

        # Build cached message (document + instructions)
        messages = self._build_cached_message(document.content, instructions)

        # Make LLM call with cache metrics enabled
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                extra_body={"usage": {"include": True}}  # Enable cache metrics
            )

            # Extract usage and response
            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            extracted_text = response["choices"][0]["message"]["content"].strip()

            return {
                "extracted_text": extracted_text,
                "tokens_consumed": tokens_consumed
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to extract text for section '{section_title}': {str(e)}"
            ) from e

    def _generate_contextual_prefix(
        self,
        document_id: str,
        chapter_title: str,
        section_title: str,
        subsection_title: List[str],
        chunk_text: str,
        document_text: str
    ) -> Dict[str, Any]:
        """Generate contextual prefix (plain text output)."""
        # Format subsection titles for display
        if subsection_title:
            subsection_display = ", ".join(subsection_title)
        else:
            subsection_display = "no subsections"

        # Build instructions
        instructions = PREFIX_INSTRUCTIONS.format(
            document_id=document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            subsection_title=subsection_display,
            chunk_text=chunk_text
        )

        # Build cached message
        messages = self._build_cached_message(document_text, instructions)

        # Make LLM call with cache metrics enabled
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                extra_body={"usage": {"include": True}}  # Enable cache metrics
            )

            # Extract usage and response
            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            response_text = response["choices"][0]["message"]["content"]

            # Parse prefix
            prefix = self._parse_contextual_prefix(response_text)

            return {
                "prefix": prefix,
                "tokens_consumed": tokens_consumed
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to generate contextual prefix: {str(e)}"
            ) from e

    def _parse_contextual_prefix(self, response_text: str) -> str:
        """Parse contextual prefix from plain text response (no validation)."""
        prefix = response_text.strip()
        # No length or format validation - store as-is for analysis
        return prefix
