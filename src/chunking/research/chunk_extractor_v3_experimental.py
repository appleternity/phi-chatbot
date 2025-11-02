"""
Experimental chunk extraction V3: Cache-optimized with tag-based parsing (metadata-free).

This module contains 2 experimental versions optimized for LLM caching by placing
static content (document text) at the beginning of prompts. Metadata is derived
from Phase 1 structure analysis (no redundant LLM calls).

Key Improvements over V2:
    - Eliminates redundant metadata generation (uses Phase 1 metadata)
    - 33-50% fewer LLM calls (2-3 → 1-2 per section)
    - Perfect consistency (single source of truth from Phase 1)
    - Simpler debugging (fewer moving parts)

Versions:
    V3A: 2 LLM calls (extract, prefix) - CONSERVATIVE
    V3B: 1 LLM call (extract + prefix merged) - AGGRESSIVE

Cache Efficiency:
    V3A: ~50-60% (document cached, reused 2x per section)
    V3B: ~80-90% (document cached, reused for all sections)
"""

import json
from typing import Dict, Any, List

from tqdm import tqdm

from .llm_provider import LLMProvider
from .metadata_validator import MetadataValidator
from .tag_parser import parse_tagged_output, validate_tagged_format, TagParsingError
from .models import (
    Chunk,
    ChunkMetadata,
    Document,
    ProcessingMetadata,
    ChunkExtractionError,
    Structure,
    SectionV2,
    TokenCounter,
)


# ============================================================================
# Metadata Derivation (No LLM Needed!)
# ============================================================================

def derive_metadata_from_structure(
    structure: Structure,
    section: SectionV2
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

EXTRACTION_INSTRUCTIONS_V3 = """You are extracting a specific section of text from the above document for chunking purposes.

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


PREFIX_INSTRUCTIONS_V3 = """You are generating a contextual prefix for a document chunk to improve RAG retrieval.

Your task: Write a concise sentence that situates this chunk within the overall document.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}
- Subsections: {subsection_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Plain text (single sentence, ideally 20-50 words, no special formatting)

EXAMPLE OUTPUT:
This chunk is from the Introduction chapter, Section "Why Test?", discussing the importance of software testing in preventing bugs and improving code quality.

GUIDELINES:
1. Output ONLY the contextual sentence, no explanations
2. Ideally start with "This chunk is from..."
3. Include chapter, section, and main topic
4. Be specific but concise (aim for 20-50 words)
5. Do not include the full chunk text in the prefix

OUTPUT (contextual prefix):"""


MERGED_INSTRUCTIONS_V3 = """You are processing a document chunk for a RAG pipeline. Your task: extract the section text AND create a contextual prefix - both in one operation.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Target Section: {section_title}
- Section Summary: {section_summary}
- Is Table: {is_table}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"
- Section ENDS near: "{end_words}"

Note: These boundary hints are approximate guides, not exact quotes. Use them to locate the general boundaries, then extract the complete section content.

OUTPUT FORMAT: Tagged structure with exactly 2 fields:

[CHUNK_TEXT]
The complete extracted text for the target section goes here.
Extract EXACTLY as it appears in the document, preserving all content.

**TABLE HANDLING:**
- If Is Table = true: Extract ONLY the table as clean markdown format. Exclude surrounding text.
- If Is Table = false: Extract textual content and EXCLUDE any tables (they are separate segments).

You MAY clean up formatting (normalize whitespace, fix typos, add markdown structure).
Do NOT summarize, condense, or skip any content.
[/CHUNK_TEXT]

[CONTEXTUAL_PREFIX]Concise sentence situating chunk in document (ideally 20-50 words, typically starts with "This chunk is from..."). For tables, mention it contains a table.[/CONTEXTUAL_PREFIX]

IMPORTANT RULES:
1. Use EXACT tag names as shown above (case-sensitive)
2. Include both opening [TAG] and closing [/TAG] for each field
3. CHUNK_TEXT must be complete - do NOT summarize or truncate
4. For tables: Focus on markdown table format only
5. For non-tables: Exclude any table content
6. Prefix should ideally start with "This chunk is from..." (but not required)
7. Output ALL 2 fields in the order shown
8. Output ONLY the tagged structure, no explanations or preambles

OUTPUT (tagged extraction + prefix):"""


# ============================================================================
# Version V3A: Separate Calls (Conservative)
# ============================================================================

class ChunkExtractorV3A:
    """
    Version V3A: Separate calls (Conservative).

    Architecture:
        - 2 LLM calls per section: extract → prefix
        - Both calls start with document text for cache efficiency
        - Metadata derived from Phase 1 structure (no LLM call)
        - Plain text output for both operations

    Cache Efficiency: ~50-60% (document cached, reused 2x per section)

    Pros:
        ✅ Clear separation of concerns
        ✅ Easy to debug individual operations
        ✅ No redundant metadata generation
        ✅ Perfect consistency with Phase 1

    Cons:
        ❌ 2 LLM calls per section = moderate latency
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.5-flash",
        max_chunk_tokens: int = 1000,
        cache_store=None,
        output_dir=None
    ):
        """Initialize V3A chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store
        self.output_dir = output_dir

    def generate_llm_response_key(
        self, content: str, model: str, operation: str, section_info: str = ""
    ) -> str:
        """Generate cache key for raw LLM response."""
        import hashlib
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        model_hash = hashlib.sha256(model.encode()).hexdigest()[:8]
        section_hash = hashlib.sha256(section_info.encode()).hexdigest()[:8] if section_info else ""
        if section_hash:
            return f"llm_{operation}_{content_hash}_{section_hash}_{model_hash}"
        return f"llm_{operation}_{content_hash}_{model_hash}"

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
        structure: Structure
    ) -> Dict[str, Any]:
        """
        Extract chunks from document using V3A strategy (2 calls + derived metadata).

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
                "Use StructureAnalyzerV2 to generate V2-compatible structures."
            )

        chunks = []
        total_tokens_consumed = 0

        import logging
        logger = logging.getLogger(__name__)

        # Count total sections to process (skip title-only)
        sections_to_process = [s for s in structure.sections if s.start_words or s.end_words]

        # Progress bar
        pbar = tqdm(sections_to_process, desc="Extracting chunks (V3A)", unit="section")

        # Extract chunk for each section
        for i, section in enumerate(pbar):
            try:
                # Update progress bar description
                pbar.set_postfix_str(f"{section.title[:40]}...")

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
                self.metadata_validator.validate_metadata(metadata)

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

                # Validate chunk
                self.metadata_validator.validate_chunk(chunk)
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
        logger.info(f"V3A: {len(chunks)} chunks, {total_tokens_consumed:,} tokens")

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
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}_{is_table}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_text_v3a", section_info
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                return {
                    "extracted_text": cached_response.strip(),
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True,
                    "cache_discount": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cache_status": "local_hit"
                }

        # Build instructions with dynamic params
        instructions = EXTRACTION_INSTRUCTIONS_V3.format(
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

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, extracted_text)

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
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_prefix_v3a"
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                prefix = self._parse_contextual_prefix(cached_response)
                return {
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True,
                    "cache_discount": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cache_status": "local_hit"
                }

        # Format subsection titles for display
        if subsection_title:
            subsection_display = ", ".join(subsection_title)
        else:
            subsection_display = "no subsections"

        # Build instructions
        instructions = PREFIX_INSTRUCTIONS_V3.format(
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

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, response_text)

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


# ============================================================================
# Version V3B: Merged Call (Aggressive)
# ============================================================================

class ChunkExtractorV3B:
    """
    Version V3B: Merged call (Aggressive).

    Architecture:
        - 1 LLM call per section: extract + prefix together
        - Tagged output format for robust parsing
        - Metadata derived from Phase 1 structure (no LLM call)
        - Maximum cache efficiency for multi-section documents

    Cache Efficiency: ~80-90% (first section misses, all subsequent sections hit)

    Pros:
        ✅ 50% fewer LLM calls than V3A (2 → 1) = fastest + cheapest
        ✅ All extraction context in one place = most coherent output
        ✅ Maximum cache hit potential for subsequent sections
        ✅ Tagged format handles dirty text robustly
        ✅ No redundant metadata generation

    Cons:
        ⚠️ More complex output parsing (2 tags)
        ⚠️ If one part fails, entire call fails
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.5-flash",
        max_chunk_tokens: int = 1000,
        cache_store=None,
        output_dir=None
    ):
        """Initialize V3B chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store
        self.output_dir = output_dir

    def generate_llm_response_key(
        self, content: str, model: str, operation: str, section_info: str = ""
    ) -> str:
        """Generate cache key for raw LLM response."""
        import hashlib
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        model_hash = hashlib.sha256(model.encode()).hexdigest()[:8]
        section_hash = hashlib.sha256(section_info.encode()).hexdigest()[:8] if section_info else ""
        if section_hash:
            return f"llm_{operation}_{content_hash}_{section_hash}_{model_hash}"
        return f"llm_{operation}_{content_hash}_{model_hash}"

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
        structure: Structure
    ) -> Dict[str, Any]:
        """
        Extract chunks from document using V3B strategy (1 call + derived metadata).

        Returns dict with chunks, tokens_consumed, and llm_responses.
        """
        # Validate inputs
        if not structure.sections:
            raise ChunkExtractionError("No sections provided for extraction")

        # Check for V2 format
        first_section = structure.sections[0]
        if not hasattr(first_section, 'start_words') or not hasattr(first_section, 'end_words'):
            raise ChunkExtractionError(
                "Structure does not contain word boundaries (start_words/end_words). "
                "Use StructureAnalyzerV2 to generate V2-compatible structures."
            )

        chunks = []
        total_tokens_consumed = 0

        import logging
        logger = logging.getLogger(__name__)

        # Count total sections to process (skip title-only)
        sections_to_process = [s for s in structure.sections if s.start_words or s.end_words]

        # Progress bar
        pbar = tqdm(sections_to_process, desc="Extracting chunks (V3B)", unit="section")

        for i, section in enumerate(pbar):
            try:
                # Update progress bar description
                pbar.set_postfix_str(f"{section.title[:40]}...")

                # Get is_table flag (default to False for backward compatibility)
                is_table = getattr(section, 'is_table', False)

                # Single call: extract + prefix together
                merged_result = self._extract_and_generate_prefix(
                    document,
                    structure.chapter_title,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens,
                    is_table=is_table
                )

                extracted_text = merged_result["extracted_text"]
                contextual_prefix = merged_result["prefix"]
                total_tokens_consumed += merged_result.get("tokens_consumed", 0)

                # Derive metadata from Phase 1 (no LLM call!)
                metadata = derive_metadata_from_structure(structure, section)
                self.metadata_validator.validate_metadata(metadata)

                # Combine and create chunk
                chunk_text = f"{contextual_prefix}\n\n{extracted_text}"
                token_count = self.token_counter.count_tokens(chunk_text, self.model)

                # Warn if token limit exceeded
                if token_count > self.max_chunk_tokens * 3:
                    logger.debug(f"Chunk '{section.title}' has {token_count} tokens (>{self.max_chunk_tokens*3})")

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

                self.metadata_validator.validate_chunk(chunk)
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
        logger.info(f"V3B: {len(chunks)} chunks, {total_tokens_consumed:,} tokens")

        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed
        }

    def _extract_and_generate_prefix(
        self,
        document: Document,
        chapter_title: str,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int,
        is_table: bool = False
    ) -> Dict[str, Any]:
        """Extract text + generate prefix in single LLM call."""
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}_{is_table}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_prefix_v3b", section_info
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                extracted_text, prefix = self._parse_merged_tags(cached_response)
                return {
                    "extracted_text": extracted_text,
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True,
                    "cache_discount": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cache_status": "local_hit"
                }

        # Build instructions
        instructions = MERGED_INSTRUCTIONS_V3.format(
            document_id=document.document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words,
            is_table=is_table
        )

        # Build cached message
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
            response_text = response["choices"][0]["message"]["content"]

            # Parse both tags
            extracted_text, prefix = self._parse_merged_tags(response_text)

            # Validate extracted text
            if not extracted_text or len(extracted_text) < 10:
                raise ChunkExtractionError(
                    f"LLM returned insufficient text for section '{section_title}'"
                )

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, response_text)

            return {
                "extracted_text": extracted_text,
                "prefix": prefix,
                "tokens_consumed": tokens_consumed
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to extract and generate prefix for section '{section_title}': {str(e)}"
            ) from e

    def _parse_merged_tags(self, response_text: str) -> tuple[str, str]:
        """Parse merged output (2 tags) into extracted_text and prefix (no validation)."""
        try:
            expected_tags = ["CHUNK_TEXT", "CONTEXTUAL_PREFIX"]
            validate_tagged_format(response_text, expected_tags)

            parsed = parse_tagged_output(response_text, expected_tags)

            # Extract text and prefix
            extracted_text = parsed["CHUNK_TEXT"]
            prefix = parsed["CONTEXTUAL_PREFIX"]

            # No validation - store as-is for analysis
            return extracted_text, prefix

        except TagParsingError as e:
            raise ChunkExtractionError(
                f"Failed to parse merged tags: {str(e)}\n"
                f"Response: {response_text[:200]}..."
            ) from e


# ============================================================================
# CLI for V3 Experimental Extractors
# ============================================================================

def _create_cli():
    """Create CLI application for V3 experimental extractors."""
    import os
    from pathlib import Path
    from typing import Annotated

    import typer
    from dotenv import load_dotenv
    from rich.console import Console

    console = Console()
    app = typer.Typer(
        name="v3-experimental",
        help="V3 Experimental chunk extractors with prompt caching (80-90% cost savings)",
        no_args_is_help=True
    )

    def _setup_environment() -> str:
        """Load environment and get API key."""
        load_dotenv()
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            console.print("[red]Error:[/red] OPENROUTER_API_KEY not found in environment")
            raise typer.Exit(2)
        return api_key

    def _setup_components(api_key: str, log_level: str):
        """Initialize logger, cache store, and LLM provider."""
        from .logger import setup_logging
        from .llm_provider import OpenRouterProvider
        from .cache_store import FileCacheStore

        logger = setup_logging(log_level, use_context=False)
        cache_store = FileCacheStore()
        llm_provider = OpenRouterProvider(api_key=api_key)
        return logger, cache_store, llm_provider


    @app.command("extract-v3a")
    def extract_v3a(
        input_path: Annotated[
            Path,
            typer.Option("--input", "-i", help="Path to document file", exists=True, resolve_path=True)
        ],
        structure_path: Annotated[
            Path,
            typer.Option("--structure", "-s", help="Path to V2 structure JSON", exists=True, resolve_path=True)
        ],
        output_dir: Annotated[
            Path,
            typer.Option("--output", "-o", help="Output directory", resolve_path=True)
        ],
        model: Annotated[
            str,
            typer.Option("--model", "-m", help="Model for extraction")
        ] = "google/gemini-2.5-flash",
        max_tokens: Annotated[
            int,
            typer.Option("--max-tokens", help="Maximum tokens per chunk", min=100, max=2000)
        ] = 1000,
        redo: Annotated[
            bool,
            typer.Option("--redo", help="Bypass local cache and force reprocessing")
        ] = False,
        log_level: Annotated[
            str,
            typer.Option("--log-level", help="Logging level")
        ] = "INFO"
    ):
        """
        Extract chunks using V3A (Conservative: 2 calls per section).

        V3A makes 2 LLM calls per section (extract + prefix) with document caching.
        Expected cache efficiency: ~50-60% for multi-section documents.
        """
        # Setup
        api_key = _setup_environment()
        logger, cache_store, llm_provider = _setup_components(api_key, log_level)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear local cache if redo flag is set
        if redo:
            cleared = cache_store.clear()
            logger.info(f"Cleared {cleared} cached files (redo mode)")
            console.print(f"[yellow]Cache cleared: {cleared} files removed[/yellow]")

        # Load structure
        structure_data = json.loads(structure_path.read_text())
        sections = [SectionV2(**s) for s in structure_data["structure"]["sections"]]
        structure = Structure(
            document_id=structure_data["document_id"],
            chapter_title=structure_data["structure"]["chapter_title"],
            chapter_number=structure_data["structure"].get("chapter_number"),
            sections=sections,
            metadata=structure_data["structure"].get("metadata", {}),
            analysis_model=structure_data["structure"]["analysis_model"]
        )

        # Load document
        document = Document.from_file(input_path)

        # Initialize extractor with output directory for progressive writing
        token_counter = TokenCounter()
        metadata_validator = MetadataValidator()
        extractor = ChunkExtractorV3A(
            llm_client=llm_provider,
            token_counter=token_counter,
            metadata_validator=metadata_validator,
            model=model,
            max_chunk_tokens=max_tokens,
            cache_store=cache_store,
            output_dir=output_dir
        )

        # Extract chunks (files written progressively)
        console.print(f"[cyan]Extracting chunks with V3A from {input_path.name}...[/cyan]")
        console.print(f"[dim]Model: {model}, Max tokens: {max_tokens}[/dim]")
        console.print(f"[dim]Output: {output_dir}[/dim]\n")

        result = extractor.extract_chunks(document, structure)
        chunks = result["chunks"]
        tokens_consumed = result["tokens_consumed"]

        console.print(f"\n[green]✓[/green] Extracted {len(chunks)} chunks")
        console.print(f"[cyan]Tokens consumed:[/cyan] {tokens_consumed:,}")
        console.print(f"[cyan]Output directory:[/cyan] {output_dir}")

        logger.info(f"V3A extraction: {len(chunks)} chunks, {tokens_consumed} tokens")

    @app.command("extract-v3b")
    def extract_v3b(
        input_path: Annotated[
            Path,
            typer.Option("--input", "-i", help="Path to document file", exists=True, resolve_path=True)
        ],
        structure_path: Annotated[
            Path,
            typer.Option("--structure", "-s", help="Path to V2 structure JSON", exists=True, resolve_path=True)
        ],
        output_dir: Annotated[
            Path,
            typer.Option("--output", "-o", help="Output directory", resolve_path=True)
        ],
        model: Annotated[
            str,
            typer.Option("--model", "-m", help="Model for extraction")
        ] = "google/gemini-2.5-flash",
        max_tokens: Annotated[
            int,
            typer.Option("--max-tokens", help="Maximum tokens per chunk", min=100, max=2000)
        ] = 1000,
        redo: Annotated[
            bool,
            typer.Option("--redo", help="Bypass local cache and force reprocessing")
        ] = False,
        log_level: Annotated[
            str,
            typer.Option("--log-level", help="Logging level")
        ] = "INFO"
    ):
        """
        Extract chunks using V3B (Aggressive: 1 call per section).

        V3B makes 1 LLM call per section (extract + prefix merged) with document caching.
        Expected cache efficiency: ~80-90% for multi-section documents.
        """
        # Setup
        api_key = _setup_environment()
        logger, cache_store, llm_provider = _setup_components(api_key, log_level)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear local cache if redo flag is set
        if redo:
            cleared = cache_store.clear()
            logger.info(f"Cleared {cleared} cached files (redo mode)")
            console.print(f"[yellow]Cache cleared: {cleared} files removed[/yellow]")

        # Load structure
        structure_data = json.loads(structure_path.read_text())
        sections = [SectionV2(**s) for s in structure_data["structure"]["sections"]]
        structure = Structure(
            document_id=structure_data["document_id"],
            chapter_title=structure_data["structure"]["chapter_title"],
            chapter_number=structure_data["structure"].get("chapter_number"),
            sections=sections,
            metadata=structure_data["structure"].get("metadata", {}),
            analysis_model=structure_data["structure"]["analysis_model"]
        )

        # Load document
        document = Document.from_file(input_path)

        # Initialize extractor with output directory for progressive writing
        token_counter = TokenCounter()
        metadata_validator = MetadataValidator()
        extractor = ChunkExtractorV3B(
            llm_client=llm_provider,
            token_counter=token_counter,
            metadata_validator=metadata_validator,
            model=model,
            max_chunk_tokens=max_tokens,
            cache_store=cache_store,
            output_dir=output_dir
        )

        # Extract chunks (files written progressively)
        console.print(f"[cyan]Extracting chunks with V3B from {input_path.name}...[/cyan]")
        console.print(f"[dim]Model: {model}, Max tokens: {max_tokens}[/dim]")
        console.print(f"[dim]Output: {output_dir}[/dim]\n")

        result = extractor.extract_chunks(document, structure)
        chunks = result["chunks"]
        tokens_consumed = result["tokens_consumed"]

        console.print(f"\n[green]✓[/green] Extracted {len(chunks)} chunks")
        console.print(f"[cyan]Tokens consumed:[/cyan] {tokens_consumed:,}")
        console.print(f"[cyan]Output directory:[/cyan] {output_dir}")

        logger.info(f"V3B extraction: {len(chunks)} chunks, {tokens_consumed} tokens")

    return app


# Entry point
if __name__ == "__main__":
    import json
    from .models import Document, Structure, SectionV2, TokenCounter
    from .metadata_validator import MetadataValidator

    app = _create_cli()
    app()
