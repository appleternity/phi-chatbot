"""
Chunk extraction component V2 with word-based boundary guidance.

This module implements Phase 2 of the chunking pipeline: extracting chunks
from documents based on semantic structure with word-based boundary hints
for improved extraction accuracy.
"""

from typing import Dict, Any

from .llm_provider import LLMProvider
from .metadata_validator import MetadataValidator
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
# Prompt Templates V2 (with start_words/end_words guidance)
# ============================================================================


TEXT_EXTRACTION_PROMPT_V2 = """You are extracting a specific section of text from a document for chunking purposes.

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

DOCUMENT TEXT:
{document_text}

OUTPUT (extracted section text):"""


METADATA_GENERATION_PROMPT = """You are generating metadata for a document chunk in a RAG pipeline.

Your task: Create metadata that helps users find and understand this chunk.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 4 columns:
chapter_title\tsection_title\tsubsection_title\tsummary

Column definitions:
- chapter_title: Main chapter title (required, same as context)
- section_title: Section within chapter (required, same as context)
- subsection_title: Subsection if applicable, or "NONE" if not applicable
- summary: Brief summary of chunk content (20-100 words, no tabs)

EXAMPLE OUTPUT:
Introduction to Testing\tWhy Test?\tNONE\tExplains the importance of software testing in preventing bugs and improving code quality through systematic verification
Testing Methodologies\tUnit Testing\tBest Practices\tDescribes best practices for writing effective unit tests including test isolation, meaningful assertions, and comprehensive coverage

IMPORTANT RULES:
1. Output ONLY the TSV data (single line), no explanations
2. Exactly 4 tab-separated values
3. Use "NONE" for subsection_title if not applicable
4. Summary must be actionable and descriptive (not just "summary of content")
5. No tabs or newlines within any field

CHUNK TEXT:
{chunk_text}

OUTPUT (TSV format):"""


CONTEXTUAL_PREFIX_PROMPT = """You are generating a contextual prefix for a document chunk to improve RAG retrieval.

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

OUTPUT:"""


# ============================================================================
# ChunkExtractor V2 Implementation
# ============================================================================


class ChunkExtractorV2:
    """Chunk extractor V2 with word-based boundary guidance for Phase 2"""

    def __init__(
        self,
        llm_client: LLMProvider,
        token_counter: TokenCounter,
        metadata_validator: MetadataValidator,
        model: str = "google/gemini-2.0-flash-exp",
        max_chunk_tokens: int = 1000,
        cache_store=None
    ):
        """
        Initialize chunk extractor V2.

        Args:
            llm_client: LLM provider for text extraction and metadata generation
            token_counter: Token counting utility
            metadata_validator: Validator for chunk metadata
            model: Model identifier for LLM calls
            max_chunk_tokens: Maximum tokens per chunk (default: 1000)
            cache_store: Optional cache store for LLM responses
        """
        self.llm_client = llm_client
        self.token_counter = token_counter
        self.metadata_validator = metadata_validator
        self.model = model
        self.max_chunk_tokens = max_chunk_tokens
        self.cache_store = cache_store

    def generate_llm_response_key(
        self, content: str, model: str, operation: str, section_info: str = ""
    ) -> str:
        """
        Generate cache key for raw LLM response.

        Args:
            content: Input content (document or chunk text)
            model: Model identifier
            operation: Operation type (e.g., "extract_text_v2", "generate_metadata")
            section_info: Optional section-specific info (title + summary + boundaries)

        Returns:
            Cache key for LLM response
        """
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
        Extract chunks from document based on semantic structure with word boundaries (V2).

        Args:
            document: Source document
            structure: Document structure from Phase 1 (must contain SectionV2 with word boundaries)

        Returns:
            Dict with:
                - chunks: List of chunks with contextual prefix and metadata
                - tokens_consumed: Total tokens consumed in LLM calls
                - llm_responses: Dict mapping section titles to their LLM responses
                  (includes: extraction, metadata, prefix for each section)

        Raises:
            ChunkExtractionError: If extraction or metadata generation fails
            MetadataValidationError: If any chunk has invalid metadata

        Behavior:
            1. For each section in structure:
               a. Use LLM to extract full text for section (guided by start_words/end_words)
               b. Generate metadata via TSV format
               c. Generate contextual prefix as plain text
               d. Prepend contextual prefix to extracted text
               e. Count tokens in chunk
               f. Create Chunk object
               g. Validate token count ≤ max_chunk_tokens
            2. Return all chunks with token consumption and raw LLM responses
        """
        # Validate inputs
        if not structure.sections:
            raise ChunkExtractionError("No sections provided for extraction")

        # Check if structure contains word boundaries (V2 format)
        first_section = structure.sections[0]
        if not hasattr(first_section, 'start_words') or not hasattr(first_section, 'end_words'):
            raise ChunkExtractionError(
                "Structure does not contain word boundaries (start_words/end_words). "
                "Use StructureAnalyzerV2 to generate V2-compatible structures."
            )

        chunks = []
        total_tokens_consumed = 0
        llm_responses = {}  # Store all LLM responses by section

        # Extract chunk for each section
        for i, section in enumerate(structure.sections):
            try:
                # Step 1: Check if section is title-only (empty start_words and end_words)
                is_title_only = not section.start_words and not section.end_words

                if is_title_only:
                    # Title-only section: no body content to extract
                    # Skip this section entirely (no chunk generated)
                    continue

                # Step 1b: Extract text for this section using LLM with boundary guidance
                extraction_result = self._extract_section_text_v2(
                    document,
                    section.title,
                    section.summary,
                    section.start_words,
                    section.end_words,
                    self.max_chunk_tokens
                )
                extracted_text = extraction_result["extracted_text"]
                total_tokens_consumed += extraction_result.get("tokens_consumed", 0)

                # Step 2: Generate metadata using LLM
                metadata_result = self._generate_metadata(
                    document.document_id,
                    structure.chapter_title,
                    section.title,
                    extracted_text
                )
                metadata = metadata_result["metadata"]
                total_tokens_consumed += metadata_result.get("tokens_consumed", 0)

                # Validate metadata
                self.metadata_validator.validate_metadata(metadata)

                # Step 3: Generate contextual prefix using LLM
                prefix_result = self._generate_contextual_prefix(
                    document.document_id,
                    metadata.chapter_title,
                    metadata.section_title,
                    metadata.subsection_title,
                    extracted_text
                )
                contextual_prefix = prefix_result["prefix"]
                total_tokens_consumed += prefix_result.get("tokens_consumed", 0)

                # Collect LLM responses for this section
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

                # Step 6: Create chunk ID
                chunk_id = f"{document.document_id}_chunk_{i+1:03d}"

                # Step 7: Create processing metadata
                cache_hit = structure.metadata.get("cache_hit", False)

                processing_metadata = ProcessingMetadata(
                    phase_1_model=structure.analysis_model,
                    phase_2_model=self.model,
                    cache_hit=cache_hit
                )

                # Step 8: Create Chunk object
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

                # Step 9: Validate chunk
                self.metadata_validator.validate_chunk(chunk)

                chunks.append(chunk)

            except Exception as e:
                # Fail fast on any error
                if isinstance(e, (ChunkExtractionError, ValueError)):
                    raise
                raise ChunkExtractionError(
                    f"Failed to extract chunk for section '{section.title}': {str(e)}"
                ) from e

        # Return chunks with token consumption and raw LLM responses
        return {
            "chunks": chunks,
            "tokens_consumed": total_tokens_consumed,
            "llm_responses": llm_responses
        }

    def _extract_section_text_v2(
        self,
        document: Document,
        section_title: str,
        section_summary: str,
        start_words: str,
        end_words: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        Extract text for a specific section using LLM with word-based boundary guidance (V2).

        Args:
            document: Source document
            section_title: Title of section to extract
            section_summary: Summary of section content (helps LLM locate it)
            start_words: First few words of section content (boundary hint)
            end_words: Last few words of section content (boundary hint)
            max_tokens: Maximum tokens for extracted text

        Returns:
            Dict with:
                - extracted_text: Extracted and formatted text
                - tokens_consumed: Tokens used in LLM call
                - llm_response: Raw LLM response
                - llm_response_cached: Whether response was from cache

        Raises:
            ChunkExtractionError: If LLM call fails or extraction fails
        """
        # Generate cache key for this extraction (include boundaries in key)
        section_info = f"{section_title}_{section_summary}_{start_words}_{end_words}"
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                document.content, self.model, "extract_text_v2", section_info
            )

            # Check cache first
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                # Use cached response
                extracted_text = cached_response.strip()
                return {
                    "extracted_text": extracted_text,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt with boundary hints
        prompt = TEXT_EXTRACTION_PROMPT_V2.format(
            section_title=section_title,
            section_summary=section_summary,
            max_tokens=max_tokens,
            start_words=start_words,
            end_words=end_words,
            document_text=document.content
        )

        # Make LLM call
        try:
            response = self.llm_client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  # Lower temperature for accurate extraction
            )

            # Extract token usage
            tokens_consumed = 0
            try:
                usage = response.get("usage", {})
                tokens_consumed = usage.get("total_tokens", 0)
            except Exception:
                # Token tracking is optional
                pass

            extracted_text = response["choices"][0]["message"]["content"].strip()

            # Validate extraction
            if not extracted_text:
                raise ChunkExtractionError(
                    f"LLM returned empty text for section '{section_title}'"
                )

            if len(extracted_text) < 10:
                raise ChunkExtractionError(
                    f"LLM returned suspiciously short text ({len(extracted_text)} chars) "
                    f"for section '{section_title}'"
                )

            # Cache the raw response
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
        chunk_text: str
    ) -> Dict[str, Any]:
        """
        Generate metadata for chunk using LLM.

        Args:
            document_id: Document identifier
            chapter_title: Chapter title
            section_title: Section title
            chunk_text: Text content of chunk

        Returns:
            Dict with:
                - metadata: ChunkMetadata instance
                - tokens_consumed: Tokens used in LLM call
                - llm_response: Raw LLM response
                - llm_response_cached: Whether response was from cache

        Raises:
            ChunkExtractionError: If LLM call fails or response is malformed
        """
        # Generate cache key for this metadata generation
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_metadata"
            )

            # Check cache first
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                # Validate and parse cached response
                self._validate_llm_response(cached_response)
                metadata = self._parse_metadata_response(cached_response)
                return {
                    "metadata": metadata,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        prompt = METADATA_GENERATION_PROMPT.format(
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
                temperature=0.3  # Lower temperature for structured output
            )

            # Extract token usage
            tokens_consumed = 0
            try:
                usage = response.get("usage", {})
                tokens_consumed = usage.get("total_tokens", 0)
            except Exception:
                # Token tracking is optional
                pass

            response_text = response["choices"][0]["message"]["content"]

            # Validate response format
            self._validate_llm_response(response_text)

            # Parse TSV response
            metadata = self._parse_metadata_response(response_text)

            # Cache the raw response
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
        chunk_text: str
    ) -> Dict[str, Any]:
        """
        Generate contextual prefix for chunk using LLM.

        Args:
            document_id: Document identifier
            chapter_title: Chapter title
            section_title: Section title
            subsection_title: Subsection title (optional)
            chunk_text: Text content of chunk

        Returns:
            Dict with:
                - prefix: Contextual prefix string
                - tokens_consumed: Tokens used in LLM call
                - llm_response: Raw LLM response
                - llm_response_cached: Whether response was from cache

        Raises:
            ChunkExtractionError: If LLM call fails or response is malformed
        """
        # Generate cache key for this prefix generation
        cache_key = None
        if self.cache_store:
            cache_key = self.generate_llm_response_key(
                chunk_text, self.model, "generate_prefix"
            )

            # Check cache first
            cached_response = self.cache_store.get_llm_response(cache_key)
            if cached_response:
                # Validate and parse cached response
                prefix = self._parse_contextual_prefix(cached_response)
                return {
                    "prefix": prefix,
                    "tokens_consumed": 0,
                    "llm_response": cached_response,
                    "llm_response_cached": True
                }

        # Format prompt
        subsection_display = subsection_title or "no subsection"
        prompt = CONTEXTUAL_PREFIX_PROMPT.format(
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
                temperature=0.3  # Lower temperature for structured output
            )

            # Extract token usage
            tokens_consumed = 0
            try:
                usage = response.get("usage", {})
                tokens_consumed = usage.get("total_tokens", 0)
            except Exception:
                # Token tracking is optional
                pass

            response_text = response["choices"][0]["message"]["content"]

            # Validate and parse contextual prefix
            prefix = self._parse_contextual_prefix(response_text)

            # Cache the raw response
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

    def _validate_llm_response(self, response: str) -> None:
        """
        Validate LLM response before parsing.

        Args:
            response: Raw LLM response

        Raises:
            ChunkExtractionError: If response is invalid
        """
        if not response or not response.strip():
            raise ChunkExtractionError("LLM returned empty response")

        # Check for common LLM mistakes
        if response.strip().startswith("```"):
            raise ChunkExtractionError(
                "LLM returned markdown code block. "
                "Expected plain TSV output without formatting."
            )

        if response.strip().lower().startswith("here is") or \
           response.strip().lower().startswith("here are"):
            raise ChunkExtractionError(
                "LLM added preamble. Expected direct TSV output only."
            )

    def _parse_metadata_response(self, response_text: str) -> ChunkMetadata:
        """
        Parse LLM's TSV response into ChunkMetadata.

        Args:
            response_text: Raw TSV response from LLM

        Returns:
            ChunkMetadata instance

        Raises:
            ChunkExtractionError: If response is malformed
        """
        line = response_text.strip()
        parts = line.split('\t')

        if len(parts) != 4:
            raise ChunkExtractionError(
                f"Expected 4 columns in metadata TSV, got {len(parts)}. "
                f"Response: '{line}'"
            )

        chapter, section, subsection, summary = parts

        return ChunkMetadata(
            chapter_title=chapter.strip(),
            section_title=section.strip(),
            subsection_title=None if subsection.strip().upper() == "NONE" else subsection.strip(),
            summary=summary.strip()
        )

    def _parse_contextual_prefix(self, response_text: str) -> str:
        """
        Parse contextual prefix from LLM response.

        Args:
            response_text: Raw response from LLM

        Returns:
            Contextual prefix string

        Raises:
            ChunkExtractionError: If response is malformed
        """
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
