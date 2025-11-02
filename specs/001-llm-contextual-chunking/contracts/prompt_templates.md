# Prompt Templates: LLM-Based Contextual Document Chunking

**Feature**: 001-llm-contextual-chunking | **Date**: 2025-10-29

## Overview

This document defines the prompt templates used to guide LLM responses in each processing phase. All LLM outputs use **TSV (Tab-Separated Values) format** for reliability and easy parsing.

---

## Phase 1: Structure Analysis

**Purpose**: Identify document hierarchy (chapters, sections, subsections)

**Template**:
```python
STRUCTURE_ANALYSIS_PROMPT = """You are analyzing a document to identify its hierarchical structure.

Your task: Identify all sections, subsections, and their boundaries in the document.

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 5 columns:
title	level	start_char	end_char	parent_title

Column definitions:
- title: Section heading/title (required, no tabs allowed)
- level: Hierarchy level as integer (1=section, 2=subsection, 3=subsubsection)
- start_char: Character position where section starts (0-indexed)
- end_char: Character position where section ends (exclusive)
- parent_title: Parent section title, or "ROOT" for top-level sections

EXAMPLE OUTPUT:
Introduction to Testing	1	0	1500	ROOT
Why Test?	2	0	750	Introduction to Testing
Benefits of Testing	2	750	1500	Introduction to Testing
Testing Methodologies	1	1500	3000	ROOT
Unit Testing	2	1500	2250	Testing Methodologies
Integration Testing	2	2250	3000	Testing Methodologies

IMPORTANT RULES:
1. Output ONLY the TSV data, no explanations or markdown
2. Each line must have exactly 5 tab-separated values
3. No empty lines between data rows
4. Character positions must be accurate (start < end)
5. Levels must be 1, 2, or 3 only
6. Parent titles must match exactly (case-sensitive)

DOCUMENT TO ANALYZE:
{document_text}

OUTPUT (TSV format):"""

def format_structure_prompt(document_text: str) -> str:
    """Format structure analysis prompt with document text."""
    return STRUCTURE_ANALYSIS_PROMPT.format(document_text=document_text)
```

**Expected Response Format**:
```tsv
Chapter 1: Introduction	1	0	5000	ROOT
Section 1.1: Overview	2	0	2500	Chapter 1: Introduction
Section 1.2: Scope	2	2500	5000	Chapter 1: Introduction
```

**Parsing Code**:
```python
def parse_structure_response(response_text: str) -> List[Section]:
    """Parse LLM's TSV response into Section objects."""
    sections = []
    lines = response_text.strip().split('\n')

    for line_num, line in enumerate(lines, 1):
        if not line.strip():  # Skip empty lines
            continue

        parts = line.split('\t')
        if len(parts) != 5:
            raise StructureAnalysisError(
                f"Line {line_num}: Expected 5 columns, got {len(parts)}. "
                f"Line content: '{line}'"
            )

        title, level_str, start_str, end_str, parent = parts

        try:
            sections.append(Section(
                title=title.strip(),
                level=int(level_str.strip()),
                start_char=int(start_str.strip()),
                end_char=int(end_str.strip()),
                parent_section=None if parent.strip() == "ROOT" else parent.strip()
            ))
        except ValueError as e:
            raise StructureAnalysisError(
                f"Line {line_num}: Invalid data - {e}. Line: '{line}'"
            )

    return sections
```

---

## Phase 2: Boundary Detection

**Purpose**: Determine optimal chunk boundaries within sections

**Template**:
```python
BOUNDARY_DETECTION_PROMPT = """You are determining optimal chunk boundaries for semantic document chunking.

Your task: Identify where to split text into chunks, preserving semantic coherence.

CONTEXT:
- Document section: {section_title}
- Section text length: {text_length} characters
- Maximum chunk size: {max_tokens} tokens (approximately {max_chars} characters)

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 3 columns:
position	boundary_type	justification

Column definitions:
- position: Character position in document (integer, 0-indexed)
- boundary_type: One of: DOCUMENT_START, SECTION_BREAK, SEMANTIC_SHIFT, SIZE_CONSTRAINT, DOCUMENT_END
- justification: Brief explanation (50-200 chars, no tabs allowed)

EXAMPLE OUTPUT:
0	DOCUMENT_START	Beginning of document
567	SEMANTIC_SHIFT	Topic changes from benefits to challenges
1234	SIZE_CONSTRAINT	Approaching token limit, splitting at paragraph
2000	SECTION_BREAK	New section "Testing Types" begins
2500	DOCUMENT_END	End of document

IMPORTANT RULES:
1. Output ONLY the TSV data, no explanations or markdown
2. Each line must have exactly 3 tab-separated values
3. Positions must be in ascending order
4. First boundary must be DOCUMENT_START at position 0
5. Last boundary must be DOCUMENT_END at the section's end position
6. Justifications must be concise and meaningful

SECTION TEXT:
{section_text}

OUTPUT (TSV format):"""

def format_boundary_prompt(
    section_title: str,
    section_text: str,
    max_tokens: int
) -> str:
    """Format boundary detection prompt."""
    max_chars = max_tokens * 4  # Approximate conversion
    return BOUNDARY_DETECTION_PROMPT.format(
        section_title=section_title,
        section_text=section_text,
        text_length=len(section_text),
        max_tokens=max_tokens,
        max_chars=max_chars
    )
```

**Expected Response Format**:
```tsv
0	DOCUMENT_START	Beginning of section
1250	SEMANTIC_SHIFT	Transition from theory to practical examples
2500	DOCUMENT_END	End of section
```

**Parsing Code**:
```python
def parse_boundary_response(response_text: str) -> List[SegmentBoundary]:
    """Parse LLM's TSV response into SegmentBoundary objects."""
    boundaries = []
    lines = response_text.strip().split('\n')

    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue

        parts = line.split('\t')
        if len(parts) != 3:
            raise BoundaryDetectionError(
                f"Line {line_num}: Expected 3 columns, got {len(parts)}. "
                f"Line: '{line}'"
            )

        position_str, boundary_type_str, justification = parts

        try:
            boundaries.append(SegmentBoundary(
                boundary_id=f"boundary_{line_num:03d}",
                position=int(position_str.strip()),
                boundary_type=BoundaryType(boundary_type_str.strip()),
                justification=justification.strip(),
                section_context="",  # Filled by caller
                estimated_chunk_size=0  # Calculated by caller
            ))
        except (ValueError, KeyError) as e:
            raise BoundaryDetectionError(
                f"Line {line_num}: Invalid data - {e}. Line: '{line}'"
            )

    return boundaries
```

---

## Phase 3: Chunk Metadata Generation

**Purpose**: Generate metadata for each chunk

**Template**:
```python
METADATA_GENERATION_PROMPT = """You are generating metadata for a document chunk in a RAG pipeline.

Your task: Create metadata that helps users find and understand this chunk.

CONTEXT:
- Document: {document_id}
- Chapter: {chapter_title}
- Section: {section_title}

OUTPUT FORMAT: TSV (Tab-Separated Values) with exactly 4 columns:
chapter_title	section_title	subsection_title	summary

Column definitions:
- chapter_title: Main chapter title (required, same as context)
- section_title: Section within chapter (required, same as context)
- subsection_title: Subsection if applicable, or "NONE" if not applicable
- summary: Brief summary of chunk content (20-100 words, no tabs)

EXAMPLE OUTPUT:
Introduction to Testing	Why Test?	NONE	Explains the importance of software testing in preventing bugs and improving code quality through systematic verification
Testing Methodologies	Unit Testing	Best Practices	Describes best practices for writing effective unit tests including test isolation, meaningful assertions, and comprehensive coverage

IMPORTANT RULES:
1. Output ONLY the TSV data (single line), no explanations
2. Exactly 4 tab-separated values
3. Use "NONE" for subsection_title if not applicable
4. Summary must be actionable and descriptive (not just "summary of content")
5. No tabs or newlines within any field

CHUNK TEXT:
{chunk_text}

OUTPUT (TSV format):"""

def format_metadata_prompt(
    document_id: str,
    chapter_title: str,
    section_title: str,
    chunk_text: str
) -> str:
    """Format metadata generation prompt."""
    return METADATA_GENERATION_PROMPT.format(
        document_id=document_id,
        chapter_title=chapter_title,
        section_title=section_title,
        chunk_text=chunk_text
    )
```

**Expected Response Format**:
```tsv
Introduction	Testing Basics	NONE	Covers fundamental concepts of software testing including test types, coverage metrics, and quality assurance principles
```

**Parsing Code**:
```python
def parse_metadata_response(response_text: str) -> ChunkMetadata:
    """Parse LLM's TSV response into ChunkMetadata."""
    line = response_text.strip()
    parts = line.split('\t')

    if len(parts) != 4:
        raise MetadataValidationError(
            f"Expected 4 columns, got {len(parts)}. Response: '{line}'"
        )

    chapter, section, subsection, summary = parts

    return ChunkMetadata(
        chapter_title=chapter.strip(),
        section_title=section.strip(),
        subsection_title=None if subsection.strip() == "NONE" else subsection.strip(),
        summary=summary.strip()
    )
```

---

## Phase 3b: Contextual Prefix Generation

**Purpose**: Generate contextual prefix for chunk (Anthropic Contextual Retrieval approach)

**Template**:
```python
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

def format_contextual_prefix_prompt(
    document_id: str,
    chapter_title: str,
    section_title: str,
    subsection_title: Optional[str],
    chunk_text: str
) -> str:
    """Format contextual prefix generation prompt."""
    subsection_display = subsection_title or "no subsection"
    return CONTEXTUAL_PREFIX_PROMPT.format(
        document_id=document_id,
        chapter_title=chapter_title,
        section_title=section_title,
        subsection_title=subsection_display,
        chunk_text=chunk_text
    )
```

**Expected Response Format**:
```
This chunk is from Chapter 1 (Introduction to Testing), Section "Why Test?", explaining the benefits of systematic testing in software development.
```

**Parsing Code**:
```python
def parse_contextual_prefix(response_text: str) -> str:
    """Parse contextual prefix (no special parsing needed, just trim)."""
    prefix = response_text.strip()

    if len(prefix) < 20 or len(prefix) > 300:
        raise SegmentationError(
            f"Contextual prefix must be 20-300 chars, got {len(prefix)}"
        )

    if not prefix.startswith("This chunk is from"):
        raise SegmentationError(
            "Contextual prefix must start with 'This chunk is from'"
        )

    return prefix
```

---

## Error Handling for All Prompts

**Common Validation**:
```python
def validate_llm_response(response: str, expected_format: str) -> None:
    """Validate LLM response before parsing."""
    if not response or not response.strip():
        raise ChunkingError("LLM returned empty response")

    # Check for common LLM mistakes
    if response.strip().startswith("```"):
        raise ChunkingError(
            "LLM returned markdown code block. "
            "Expected plain TSV output without formatting."
        )

    if response.strip().lower().startswith("here is") or \
       response.strip().lower().startswith("here are"):
        raise ChunkingError(
            "LLM added preamble. Expected direct TSV output only."
        )
```

**Retry Strategy**:
- **No retries for Phase 1 & 2**: Fail fast on malformed output (user requirement)
- **Phase 3**: Can retry metadata/prefix generation once if parsing fails
- **All phases**: Log raw LLM response before raising error for debugging

---

## Prompt Caching Strategy

**Cache Key Components**:
- Prompt template version (change version when template changes)
- Document hash (for structure analysis)
- Section hash + max_tokens (for boundary detection)

**Cache Control Headers** (OpenRouter):
```python
def make_llm_call_with_cache(
    prompt: str,
    model: str,
    cache_key: str
) -> str:
    """Make LLM API call with prompt caching."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Cache-Control": "max-age=300"  # 5 minute cache
    }

    # Mark long prompt content as cacheable
    # (OpenRouter/Anthropic automatically cache prompt prefixes)

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3  # Lower for structured output
        }
    )

    return response.json()["choices"][0]["message"]["content"]
```

---

## Summary

**Prompt Templates**: 4 total
1. **Structure Analysis**: TSV with 5 columns (title, level, positions, parent)
2. **Boundary Detection**: TSV with 3 columns (position, type, justification)
3. **Metadata Generation**: TSV with 4 columns (chapter, section, subsection, summary)
4. **Contextual Prefix**: Plain text sentence (20-50 words)

**Key Principles**:
- Always include format examples in prompts
- Use TSV for structured data (reliable parsing)
- Use plain text for free-form content (contextual prefix)
- Validate column counts before parsing values
- Fail fast on malformed output with clear error messages
- Log raw LLM responses for debugging

All prompts ready for implementation.
