"""
Experimental chunk extraction implementations with tag-based output parsing.

This module contains 3 experimental versions of the chunk extractor, all optimized
for LLM caching by placing static content (document text) at the beginning of prompts.

Versions:
    V2A: 3 separate LLM calls (extract, metadata, prefix) - CONSERVATIVE
    V2B: 2 LLM calls (extract, then metadata+prefix merged) - MODERATE
    V2C: 1 LLM call (extract+metadata+prefix fully merged) - AGGRESSIVE

All versions use XML-style tags instead of TSV for robust parsing of dirty text
with tabs, newlines, and special characters.

Cache Efficiency:
    V2A: ~60-70% (document cached, reused 3x per section)
    V2B: ~50-60% (document cached, reused 2x per section)
    V2C: ~80-90% (document cached once, reused for all sections)
"""

from typing import Dict, Any

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
    TokenCounter,
)


# ============================================================================
# Shared Prompt Components (Document-First Structure)
# ============================================================================

DOCUMENT_SECTION = """DOCUMENT TEXT:
{document_text}

---"""


# ============================================================================
# Version V2A: Separate Calls + Document Context (Conservative)
# ============================================================================

TEXT_EXTRACTION_PROMPT_V2A = """DOCUMENT TEXT:
{document_text}

---

You are extracting a specific section of text from the above document for chunking purposes.

Your task: Extract and format the complete text for the section described below. Output EXACTLY as it appears in the document, preserving all content but with clean formatting.

TARGET SECTION:
- Title: {section_title}
- Summary: {section_summary}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"
- Section ENDS near: "{end_words}"

Note: These boundary hints are approximate guides, not exact quotes. The actual text may have minor variations in capitalization, punctuation, or word order. Use them to locate the general boundaries, then extract the complete section content.

EXTRACTION RULES:
1. Output the COMPLETE text for this section - do NOT summarize or paraphrase
2. Include ALL content from this section
3. Use the boundary hints to identify where this section starts and ends:
   - Find text that closely matches the start_words (allowing for minor variations)
   - Find text that closely matches the end_words (allowing for minor variations)
   - Extract everything between these boundaries
4. You MAY clean up formatting:
   - Normalize whitespace and line breaks
   - Fix obvious typos
   - Add markdown structure (headers, lists) if helpful
5. Do NOT:
   - Summarize or condense content
   - Skip any content from the target section
   - Add content not in the original section
   - Include content from other sections (respect the boundaries!)
6. Output ONLY the extracted text, no explanations or preamble

OUTPUT (extracted section text):"""


METADATA_GENERATION_PROMPT_V2A = """DOCUMENT TEXT:
{document_text}

---

You are generating metadata for a document chunk in a RAG pipeline.

Your task: Create metadata that helps users find and understand this chunk.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Tagged structure with exactly 4 fields:

[CHAPTER_TITLE]Same as context chapter title[/CHAPTER_TITLE]
[SECTION_TITLE]Same as context section title[/SECTION_TITLE]
[SUBSECTION_TITLE]Subsection if applicable, or NONE[/SUBSECTION_TITLE]
[SUMMARY]Brief summary of chunk content (20-100 words, no tabs)[/SUMMARY]

IMPORTANT RULES:
1. Use EXACT tag names as shown (case-sensitive)
2. Include both opening [TAG] and closing [/TAG] for each field
3. Use NONE for SUBSECTION_TITLE if not applicable
4. Summary must be actionable and descriptive (not just "summary of content")
5. No tabs or newlines within any field (except SUMMARY can have multiple sentences)
6. Output ONLY the tagged structure, no explanations

OUTPUT (tagged metadata):"""


CONTEXTUAL_PREFIX_PROMPT_V2A = """DOCUMENT TEXT:
{document_text}

---

You are generating a contextual prefix for a document chunk to improve RAG retrieval.

Your task: Write a concise sentence that situates this chunk within the overall document.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}
- Subsection: {subsection_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Plain text (single sentence, 20-50 words, no special formatting)

EXAMPLE OUTPUT:
This chunk is from the Introduction chapter, Section "Why Test?", discussing the importance of software testing in preventing bugs and improving code quality.

IMPORTANT RULES:
1. Output ONLY the contextual sentence, no explanations
2. Start with "This chunk is from..."
3. Include chapter, section, and main topic
4. Be specific but concise (20-50 words)
5. Do not include the full chunk text in the prefix

OUTPUT (contextual prefix):"""


class ChunkExtractorV2A:
    """
    Version V2A: Separate calls with document context (Conservative).

    Architecture:
        - 3 LLM calls per section: extract → metadata → prefix
        - All calls start with document text for cache efficiency
        - Metadata uses tagged output format for robustness
        - Extract and prefix use plain text format

    Cache Efficiency: ~60-70% (document cached, reused 3x per section)

    Pros:
        ✅ Maximum cache reuse across operation types
        ✅ Clear separation of concerns
        ✅ Easy to debug individual operations
        ✅ Validated output format per operation

    Cons:
        ❌ 3 LLM calls per section = higher latency
        ❌ More API calls = more overhead
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.0-flash-exp",
        max_chunk_tokens: int = 1000,
        cache_store=None
    ):
        """Initialize V2A chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store

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

    def extract_chunks(
        self,
        document: Document,
        structure: Structure
    ) -> Dict[str, Any]:
        """
        Extract chunks from document using V2A strategy (separate calls + tags).

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
        llm_responses = {}

        # Extract chunk for each section
        for i, section in enumerate(structure.sections):
            try:
                # Skip title-only sections (empty boundaries)
                is_title_only = not section.start_words and not section.end_words
                if is_title_only:
                    continue

                # Step 1: Extract text
                extraction_result = self._extract_section_text(
                    document,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens
                )
                extracted_text = extraction_result["extracted_text"]
                total_tokens_consumed += extraction_result.get("tokens_consumed", 0)

                # Step 2: Generate metadata using tags
                metadata_result = self._generate_metadata(
                    document.document_id,
                    structure.chapter_title,
                    section.title,
                    extracted_text,
                    document.content  # Pass document for caching
                )
                metadata = metadata_result["metadata"]
                total_tokens_consumed += metadata_result.get("tokens_consumed", 0)

                # Validate metadata
                self.metadata_validator.validate_metadata(metadata)

                # Step 3: Generate contextual prefix
                prefix_result = self._generate_contextual_prefix(
                    document.document_id,
                    metadata.chapter_title,
                    metadata.section_title,
                    metadata.subsection_title,
                    extracted_text,
                    document.content  # Pass document for caching
                )
                contextual_prefix = prefix_result["prefix"]
                total_tokens_consumed += prefix_result.get("tokens_consumed", 0)

                # Collect LLM responses
                llm_responses[section.title] = {
                    "extraction": {
                        "response": extraction_result.get("llm_response"),
                        "cached": extraction_result.get("llm_response_cached", False)
                    },
                    "metadata": {
                        "response": metadata_result.get("llm_response"),
                        "cached": metadata_result.get("llm_response_cached", False)
                    },
                    "prefix": {
                        "response": prefix_result.get("llm_response"),
                        "cached": prefix_result.get("llm_response_cached", False)
                    }
                }

                # Step 4: Combine prefix with extracted text
                chunk_text = f"{contextual_prefix}\n\n{extracted_text}"

                # Step 5: Count tokens
                token_count = self.token_counter.count_tokens(chunk_text, self.model)

                # Enforce token limit
                if token_count > self.max_chunk_tokens:
                    raise ChunkExtractionError(
                        f"Chunk '{section.title}' exceeds token limit: "
                        f"{token_count} > {self.max_chunk_tokens} tokens"
                    )

                # Step 6: Create chunk
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

            except Exception as e:
                if isinstance(e, (ChunkExtractionError, ValueError)):
                    raise
                raise ChunkExtractionError(
                    f"Failed to extract chunk for section '{section.title}': {str(e)}"
                ) from e

        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed,
            "llm_responses": llm_responses
        }

    def _extract_section_text(
        self,
        document: Document,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text for section using LLM (plain text output)."""
        # Generate cache key
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_text_v2a", section_info
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                return {
                    "extracted_text": cached_response.strip(),
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        prompt = TEXT_EXTRACTION_PROMPT_V2A.format(
            document_text=document.content,
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words
        )

        # Make LLM call
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            extracted_text = response["choices"][0]["message"]["content"].strip()

            # Validate extraction
            if not extracted_text or len(extracted_text) < 10:
                raise ChunkExtractionError(
                    f"LLM returned insufficient text for section '{section_title}'"
                )

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, extracted_text)

            return {
                "extracted_text": extracted_text,
                "tokens_consumed": tokens_consumed,
                "llm_response": extracted_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to extract text for section '{section_title}': {str(e)}"
            ) from e

    def _generate_metadata(
        self,
        document_id: str,
        chapter_title: str,
        section_title: str,
        chunk_text: str,
        document_text: str  # For caching
    ) -> Dict[str, Any]:
        """Generate metadata using tagged output format."""
        # Generate cache key
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_metadata_v2a"
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                metadata = self._parse_metadata_tags(cached_response)
                return {
                    "metadata": metadata,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        prompt = METADATA_GENERATION_PROMPT_V2A.format(
            document_text=document_text,
            document_id=document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            chunk_text=chunk_text
        )

        # Make LLM call
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            response_text = response["choices"][0]["message"]["content"]

            # Parse tagged output
            metadata = self._parse_metadata_tags(response_text)

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, response_text)

            return {
                "metadata": metadata,
                "tokens_consumed": tokens_consumed,
                "llm_response": response_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to generate metadata: {str(e)}"
            ) from e

    def _generate_contextual_prefix(
        self,
        document_id: str,
        chapter_title: str,
        section_title: str,
        subsection_title: str | None,
        chunk_text: str,
        document_text: str  # For caching
    ) -> Dict[str, Any]:
        """Generate contextual prefix (plain text output)."""
        # Generate cache key
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_prefix_v2a"
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                prefix = self._parse_contextual_prefix(cached_response)
                return {
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        subsection_display = subsection_title or "no subsection"
        prompt = CONTEXTUAL_PREFIX_PROMPT_V2A.format(
            document_text=document_text,
            document_id=document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            subsection_title=subsection_display,
            chunk_text=chunk_text
        )

        # Make LLM call
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            response_text = response["choices"][0]["message"]["content"]

            # Parse prefix
            prefix = self._parse_contextual_prefix(response_text)

            # Cache response
            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, response_text)

            return {
                "prefix": prefix,
                "tokens_consumed": tokens_consumed,
                "llm_response": response_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to generate contextual prefix: {str(e)}"
            ) from e

    def _parse_metadata_tags(self, response_text: str) -> ChunkMetadata:
        """Parse tagged metadata output into ChunkMetadata."""
        try:
            # Validate format first
            expected_tags = ["CHAPTER_TITLE", "SECTION_TITLE", "SUBSECTION_TITLE", "SUMMARY"]
            validate_tagged_format(response_text, expected_tags)

            # Parse tags
            parsed = parse_tagged_output(response_text, expected_tags)

            # Convert to ChunkMetadata
            return ChunkMetadata(
                chapter_title=parsed["CHAPTER_TITLE"],
                section_title=parsed["SECTION_TITLE"],
                subsection_title=None if parsed["SUBSECTION_TITLE"].upper() == "NONE"
                                      else parsed["SUBSECTION_TITLE"],
                summary=parsed["SUMMARY"]
            )

        except TagParsingError as e:
            raise ChunkExtractionError(
                f"Failed to parse metadata tags: {str(e)}\n"
                f"Response: {response_text[:200]}..."
            ) from e

    def _parse_contextual_prefix(self, response_text: str) -> str:
        """Parse and validate contextual prefix from plain text response."""
        prefix = response_text.strip()

        if len(prefix) < 20 or len(prefix) > 300:
            raise ChunkExtractionError(
                f"Contextual prefix must be 20-300 chars, got {len(prefix)}"
            )

        if not prefix.startswith("This chunk is from"):
            raise ChunkExtractionError(
                "Contextual prefix must start with 'This chunk is from'"
            )

        return prefix


# ============================================================================
# Version V2B: Merged Metadata + Prefix (Moderate)
# ============================================================================

METADATA_PREFIX_MERGED_PROMPT_V2B = """DOCUMENT TEXT:
{document_text}

---

You are generating metadata AND contextual prefix for a document chunk in a RAG pipeline.

Your task: Create both metadata and prefix that help users find and understand this chunk.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}

CHUNK TEXT:
{chunk_text}

OUTPUT FORMAT: Tagged structure with exactly 5 fields:

[CHAPTER_TITLE]Same as context chapter title[/CHAPTER_TITLE]
[SECTION_TITLE]Same as context section title[/SECTION_TITLE]
[SUBSECTION_TITLE]Subsection if applicable, or NONE[/SUBSECTION_TITLE]
[SUMMARY]Brief summary of chunk content (20-100 words)[/SUMMARY]
[CONTEXTUAL_PREFIX]Concise sentence situating chunk in document (20-50 words, starts with "This chunk is from...")[/CONTEXTUAL_PREFIX]

IMPORTANT RULES:
1. Use EXACT tag names as shown (case-sensitive)
2. Include both opening [TAG] and closing [/TAG] for each field
3. Use NONE for SUBSECTION_TITLE if not applicable
4. Summary must be actionable and descriptive
5. Prefix must start with "This chunk is from..."
6. Output ONLY the tagged structure, no explanations

OUTPUT (tagged metadata and prefix):"""


class ChunkExtractorV2B:
    """
    Version V2B: Merged metadata + prefix (Moderate).

    Architecture:
        - 2 LLM calls per section: extract → (metadata + prefix merged)
        - Extraction uses same prompt as V2A (document-first)
        - Metadata and prefix generated together with tagged output

    Cache Efficiency: ~50-60% (document cached, reused 2x per section)

    Pros:
        ✅ 33% fewer LLM calls than V2A (3 → 2)
        ✅ Metadata and prefix share context (more coherent)
        ✅ Still maintains extraction separation for quality
        ✅ Tagged format handles dirty text robustly

    Cons:
        ⚠️ More complex output parsing (5 tags vs 4)
        ⚠️ Harder to debug if one part fails
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.0-flash-exp",
        max_chunk_tokens: int = 1000,
        cache_store=None
    ):
        """Initialize V2B chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store

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

    def extract_chunks(
        self,
        document: Document,
        structure: Structure
    ) -> Dict[str, Any]:
        """
        Extract chunks from document using V2B strategy (merged metadata + prefix).

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
        llm_responses = {}

        for i, section in enumerate(structure.sections):
            try:
                # Skip title-only sections
                is_title_only = not section.start_words and not section.end_words
                if is_title_only:
                    continue

                # Step 1: Extract text (reuse V2A implementation)
                extraction_result = self._extract_section_text(
                    document,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens
                )
                extracted_text = extraction_result["extracted_text"]
                total_tokens_consumed += extraction_result.get("tokens_consumed", 0)

                # Step 2: Generate metadata + prefix together
                merged_result = self._generate_metadata_and_prefix(
                    document.document_id,
                    structure.chapter_title,
                    section.title,
                    extracted_text,
                    document.content
                )
                metadata = merged_result["metadata"]
                contextual_prefix = merged_result["prefix"]
                total_tokens_consumed += merged_result.get("tokens_consumed", 0)

                # Validate metadata
                self.metadata_validator.validate_metadata(metadata)

                # Collect LLM responses
                llm_responses[section.title] = {
                    "extraction": {
                        "response": extraction_result.get("llm_response"),
                        "cached": extraction_result.get("llm_response_cached", False)
                    },
                    "metadata_prefix": {
                        "response": merged_result.get("llm_response"),
                        "cached": merged_result.get("llm_response_cached", False)
                    }
                }

                # Step 3: Combine and create chunk
                chunk_text = f"{contextual_prefix}\n\n{extracted_text}"
                token_count = self.token_counter.count_tokens(chunk_text, self.model)

                if token_count > self.max_chunk_tokens:
                    raise ChunkExtractionError(
                        f"Chunk '{section.title}' exceeds token limit: "
                        f"{token_count} > {self.max_chunk_tokens} tokens"
                    )

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

            except Exception as e:
                if isinstance(e, (ChunkExtractionError, ValueError)):
                    raise
                raise ChunkExtractionError(
                    f"Failed to extract chunk for section '{section.title}': {str(e)}"
                ) from e

        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed,
            "llm_responses": llm_responses
        }

    def _extract_section_text(
        self,
        document: Document,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text for section (same as V2A)."""
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_text_v2b", section_info
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                return {
                    "extracted_text": cached_response.strip(),
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        prompt = TEXT_EXTRACTION_PROMPT_V2A.format(
            document_text=document.content,
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words
        )

        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            extracted_text = response["choices"][0]["message"]["content"].strip()

            if not extracted_text or len(extracted_text) < 10:
                raise ChunkExtractionError(
                    f"LLM returned insufficient text for section '{section_title}'"
                )

            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, extracted_text)

            return {
                "extracted_text": extracted_text,
                "tokens_consumed": tokens_consumed,
                "llm_response": extracted_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to extract text for section '{section_title}': {str(e)}"
            ) from e

    def _generate_metadata_and_prefix(
        self,
        document_id: str,
        chapter_title: str,
        section_title: str,
        chunk_text: str,
        document_text: str
    ) -> Dict[str, Any]:
        """Generate metadata and prefix together using tagged output."""
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_metadata_prefix_v2b"
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                metadata, prefix = self._parse_metadata_prefix_tags(cached_response)
                return {
                    "metadata": metadata,
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        prompt = METADATA_PREFIX_MERGED_PROMPT_V2B.format(
            document_text=document_text,
            document_id=document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            chunk_text=chunk_text
        )

        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            response_text = response["choices"][0]["message"]["content"]

            # Parse tagged output
            metadata, prefix = self._parse_metadata_prefix_tags(response_text)

            if self.cache_store and cache_key:
                self.cache_store.set_llm_response(cache_key, response_text)

            return {
                "metadata": metadata,
                "prefix": prefix,
                "tokens_consumed": tokens_consumed,
                "llm_response": response_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to generate metadata and prefix: {str(e)}"
            ) from e

    def _parse_metadata_prefix_tags(self, response_text: str) -> tuple[ChunkMetadata, str]:
        """Parse merged metadata + prefix tags into ChunkMetadata and prefix string."""
        try:
            expected_tags = [
                "CHAPTER_TITLE", "SECTION_TITLE", "SUBSECTION_TITLE",
                "SUMMARY", "CONTEXTUAL_PREFIX"
            ]
            validate_tagged_format(response_text, expected_tags)

            parsed = parse_tagged_output(response_text, expected_tags)

            # Extract metadata
            metadata = ChunkMetadata(
                chapter_title=parsed["CHAPTER_TITLE"],
                section_title=parsed["SECTION_TITLE"],
                subsection_title=None if parsed["SUBSECTION_TITLE"].upper() == "NONE"
                                      else parsed["SUBSECTION_TITLE"],
                summary=parsed["SUMMARY"]
            )

            # Extract and validate prefix
            prefix = parsed["CONTEXTUAL_PREFIX"]
            if len(prefix) < 20 or len(prefix) > 300:
                raise ChunkExtractionError(
                    f"Contextual prefix must be 20-300 chars, got {len(prefix)}"
                )
            if not prefix.startswith("This chunk is from"):
                raise ChunkExtractionError(
                    "Contextual prefix must start with 'This chunk is from'"
                )

            return metadata, prefix

        except TagParsingError as e:
            raise ChunkExtractionError(
                f"Failed to parse metadata/prefix tags: {str(e)}\n"
                f"Response: {response_text[:200]}..."
            ) from e


# ============================================================================
# Version V2C: Fully Merged (Aggressive)
# ============================================================================

FULLY_MERGED_PROMPT_V2C = """DOCUMENT TEXT:
{document_text}

---

You are processing a document chunk for a RAG pipeline. Your task: extract the section text AND generate metadata AND create a contextual prefix - all in one operation.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Target Section: {section_title}
- Section Summary: {section_summary}
- Maximum tokens: {max_tokens}

BOUNDARY HINTS (for locating the section):
- Section STARTS near: "{start_words}"
- Section ENDS near: "{end_words}"

Note: These boundary hints are approximate guides, not exact quotes. The actual text may have minor variations. Use them to locate the general boundaries, then extract the complete section content.

OUTPUT FORMAT: Tagged structure with exactly 6 fields:

[CHUNK_TEXT]
The complete extracted text for the target section goes here.
Extract EXACTLY as it appears in the document, preserving all content.
Include ALL content from this section.
You MAY clean up formatting (normalize whitespace, fix typos, add markdown structure).
Do NOT summarize, condense, or skip any content.
[/CHUNK_TEXT]

[CHAPTER_TITLE]Same as context chapter title[/CHAPTER_TITLE]
[SECTION_TITLE]Same as context section title[/SECTION_TITLE]
[SUBSECTION_TITLE]Subsection if applicable, or NONE[/SUBSECTION_TITLE]
[SUMMARY]Brief summary of chunk content (20-100 words, actionable and descriptive)[/SUMMARY]
[CONTEXTUAL_PREFIX]Concise sentence situating chunk in document (20-50 words, starts with "This chunk is from...")[/CONTEXTUAL_PREFIX]

IMPORTANT RULES:
1. Use EXACT tag names as shown above (case-sensitive)
2. Include both opening [TAG] and closing [/TAG] for each field
3. CHUNK_TEXT must be complete - do NOT summarize or truncate
4. Use NONE for SUBSECTION_TITLE if not applicable
5. Summary must be actionable and specific
6. Prefix must start with "This chunk is from..."
7. Output ALL 6 fields in the order shown
8. Output ONLY the tagged structure, no explanations or preambles

OUTPUT (tagged extraction + metadata + prefix):"""


class ChunkExtractorV2C:
    """
    Version V2C: Fully merged single call (Aggressive).

    Architecture:
        - 1 LLM call per section: extract + metadata + prefix all together
        - All operations combined with tagged output format
        - Maximum cache efficiency for multi-section documents

    Cache Efficiency: ~80-90% (first section misses, all subsequent sections hit)

    Pros:
        ✅ 66% fewer LLM calls than V2A (3 → 1) = fastest + cheapest
        ✅ All context in one place = most coherent output
        ✅ Maximum cache hit potential for subsequent sections
        ✅ Tagged format handles dirty text robustly

    Cons:
        ❌ Complex structured output (6 tags) = higher LLM failure risk
        ❌ Harder to validate individual components
        ❌ If one part fails, entire call fails
        ❌ Longer prompt = higher token cost per call
    """

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.0-flash-exp",
        max_chunk_tokens: int = 1000,
        cache_store=None
    ):
        """Initialize V2C chunk extractor."""
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store

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

    def extract_chunks(
        self,
        document: Document,
        structure: Structure
    ) -> Dict[str, Any]:
        """
        Extract chunks from document using V2C strategy (fully merged single call).

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
        llm_responses = {}

        for i, section in enumerate(structure.sections):
            try:
                # Skip title-only sections
                is_title_only = not section.start_words and not section.end_words
                if is_title_only:
                    continue

                # Single call: extract + metadata + prefix all together
                merged_result = self._extract_and_generate_all(
                    document,
                    structure.chapter_title,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens
                )

                extracted_text = merged_result["extracted_text"]
                metadata = merged_result["metadata"]
                contextual_prefix = merged_result["prefix"]
                total_tokens_consumed += merged_result.get("tokens_consumed", 0)

                # Validate metadata
                self.metadata_validator.validate_metadata(metadata)

                # Collect LLM response
                llm_responses[section.title] = {
                    "merged": {
                        "response": merged_result.get("llm_response"),
                        "cached": merged_result.get("llm_response_cached", False)
                    }
                }

                # Combine and create chunk
                chunk_text = f"{contextual_prefix}\n\n{extracted_text}"
                token_count = self.token_counter.count_tokens(chunk_text, self.model)

                if token_count > self.max_chunk_tokens:
                    raise ChunkExtractionError(
                        f"Chunk '{section.title}' exceeds token limit: "
                        f"{token_count} > {self.max_chunk_tokens} tokens"
                    )

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

            except Exception as e:
                if isinstance(e, (ChunkExtractionError, ValueError)):
                    raise
                raise ChunkExtractionError(
                    f"Failed to extract chunk for section '{section.title}': {str(e)}"
                ) from e

        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed,
            "llm_responses": llm_responses
        }

    def _extract_and_generate_all(
        self,
        document: Document,
        chapter_title: str,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Extract text + generate metadata + prefix in single LLM call."""
        # Generate cache key
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_all_v2c", section_info
            )
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                extracted_text, metadata, prefix = self._parse_fully_merged_tags(cached_response)
                return {
                    "extracted_text": extracted_text,
                    "metadata": metadata,
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        prompt = FULLY_MERGED_PROMPT_V2C.format(
            document_text=document.content,
            document_id=document.document_id,
            chapter_title=chapter_title,
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words
        )

        # Make LLM call
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            tokens_consumed = response.get("usage", {}).get("total_tokens", 0)
            response_text = response["choices"][0]["message"]["content"]

            # Parse all 6 tags
            extracted_text, metadata, prefix = self._parse_fully_merged_tags(response_text)

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
                "metadata": metadata,
                "prefix": prefix,
                "tokens_consumed": tokens_consumed,
                "llm_response": response_text,
                "llm_response_cached": False
            }

        except Exception as e:
            raise ChunkExtractionError(
                f"Failed to extract and generate all for section '{section_title}': {str(e)}"
            ) from e

    def _parse_fully_merged_tags(
        self,
        response_text: str
    ) -> tuple[str, ChunkMetadata, str]:
        """Parse fully merged output (6 tags) into extracted_text, metadata, and prefix."""
        try:
            expected_tags = [
                "CHUNK_TEXT", "CHAPTER_TITLE", "SECTION_TITLE",
                "SUBSECTION_TITLE", "SUMMARY", "CONTEXTUAL_PREFIX"
            ]
            validate_tagged_format(response_text, expected_tags)

            parsed = parse_tagged_output(response_text, expected_tags)

            # Extract text
            extracted_text = parsed["CHUNK_TEXT"]

            # Extract metadata
            metadata = ChunkMetadata(
                chapter_title=parsed["CHAPTER_TITLE"],
                section_title=parsed["SECTION_TITLE"],
                subsection_title=None if parsed["SUBSECTION_TITLE"].upper() == "NONE"
                                      else parsed["SUBSECTION_TITLE"],
                summary=parsed["SUMMARY"]
            )

            # Extract and validate prefix
            prefix = parsed["CONTEXTUAL_PREFIX"]
            if len(prefix) < 20 or len(prefix) > 300:
                raise ChunkExtractionError(
                    f"Contextual prefix must be 20-300 chars, got {len(prefix)}"
                )
            if not prefix.startswith("This chunk is from"):
                raise ChunkExtractionError(
                    "Contextual prefix must start with 'This chunk is from'"
                )

            return extracted_text, metadata, prefix

        except TagParsingError as e:
            raise ChunkExtractionError(
                f"Failed to parse fully merged tags: {str(e)}\n"
                f"Response: {response_text[:200]}..."
            ) from e
