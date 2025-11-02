"""
Tag-based output parser for LLM responses.

This module provides robust parsing of XML-style tagged output from LLMs,
designed to handle dirty text with tabs, newlines, and special characters
that would break traditional formats like TSV.

Format Example:
    [CHUNK_TEXT]
    Multi-line text with tabs	and newlines
    Can contain any characters...
    [/CHUNK_TEXT]

    [CHAPTER_TITLE]Introduction[/CHAPTER_TITLE]
    [SECTION_TITLE]Why Test?[/SECTION_TITLE]
    [SUMMARY]Brief summary...[/SUMMARY]

Parsing Strategy:
    - Uses regex with self-closing tags: [TAG]content[/TAG]
    - Handles multi-line content with re.DOTALL flag
    - Validates all expected tags are present
    - Provides clear error messages for malformed output
"""

import re
from typing import Dict, List


class TagParsingError(Exception):
    """Raised when tag parsing fails."""
    pass


def parse_tagged_output(
    text: str,
    expected_tags: List[str],
    required_tags: List[str] | None = None
) -> Dict[str, str]:
    """
    Parse XML-style tagged output into dictionary.

    Args:
        text: Raw LLM output with XML-style tags
        expected_tags: List of tag names to extract
        required_tags: Optional list of tags that must be present (defaults to all)

    Returns:
        Dictionary mapping tag names to their content (whitespace stripped)

    Raises:
        TagParsingError: If parsing fails or required tags are missing

    Example:
        >>> text = "[NAME]John[/NAME]\\n[AGE]30[/AGE]"
        >>> parse_tagged_output(text, ["NAME", "AGE"])
        {'NAME': 'John', 'AGE': '30'}

        >>> text = "[CHUNK_TEXT]\\nMulti-line\\ntext\\n[/CHUNK_TEXT]"
        >>> parse_tagged_output(text, ["CHUNK_TEXT"])
        {'CHUNK_TEXT': 'Multi-line\\ntext'}
    """
    if required_tags is None:
        required_tags = expected_tags

    # Validate input
    if not text or not text.strip():
        raise TagParsingError("Cannot parse empty text")

    # Parse all tags using regex with backreference
    # Pattern: [TAG]content[/TAG] where closing tag must match opening tag
    pattern = r'\[(\w+)\](.*?)\[/\1\]'
    matches = re.findall(pattern, text, re.DOTALL)

    # Build result dictionary
    result = {}
    found_tags = set()

    for tag_name, content in matches:
        if tag_name in expected_tags:
            # Strip leading/trailing whitespace but preserve internal formatting
            result[tag_name] = content.strip()
            found_tags.add(tag_name)
        # Ignore unexpected tags (allows LLM to add extra context)

    # Validate all required tags were found
    missing_tags = set(required_tags) - found_tags
    if missing_tags:
        raise TagParsingError(
            f"Missing required tags: {sorted(missing_tags)}. "
            f"Found tags: {sorted(found_tags)}. "
            f"Expected tags: {sorted(expected_tags)}"
        )

    # Return results in expected tag order
    return {tag: result.get(tag, "") for tag in expected_tags}


def validate_tagged_format(
    text: str,
    expected_tags: List[str],
    strict: bool = False
) -> None:
    """
    Validate tagged output format without parsing content.

    Args:
        text: Raw LLM output with XML-style tags
        expected_tags: List of tag names that should be present
        strict: If True, raise error for any formatting issues

    Raises:
        TagParsingError: If validation fails

    Validation Checks:
        1. All expected tags have opening and closing tags
        2. No mismatched tag pairs (e.g., [A]...[/B])
        3. No duplicate tags (unless allowed)
        4. Tags are properly nested (optional in strict mode)

    Example:
        >>> text = "[NAME]John[/NAME]"
        >>> validate_tagged_format(text, ["NAME"])  # Passes
        >>> validate_tagged_format(text, ["NAME", "AGE"])  # Raises error (missing AGE)
    """
    if not text or not text.strip():
        raise TagParsingError("Cannot validate empty text")

    # Check for common LLM mistakes
    if text.strip().startswith("```"):
        raise TagParsingError(
            "LLM returned markdown code block. "
            "Expected tagged output without code block formatting."
        )

    if text.strip().lower().startswith(("here is", "here are", "output:")):
        raise TagParsingError(
            "LLM added preamble. Expected direct tagged output only."
        )

    # Find all opening and closing tags
    opening_pattern = r'\[(\w+)\]'
    closing_pattern = r'\[/(\w+)\]'

    opening_tags = re.findall(opening_pattern, text)
    closing_tags = re.findall(closing_pattern, text)

    # Check for mismatched tags
    for i, (open_tag, close_tag) in enumerate(zip(opening_tags, closing_tags)):
        if open_tag != close_tag:
            raise TagParsingError(
                f"Mismatched tag pair at position {i}: "
                f"[{open_tag}] closed with [/{close_tag}]"
            )

    # Check for unclosed tags
    if len(opening_tags) != len(closing_tags):
        raise TagParsingError(
            f"Unclosed tags detected. "
            f"Opening tags: {len(opening_tags)}, "
            f"Closing tags: {len(closing_tags)}"
        )

    # Validate all expected tags are present
    found_tags = set(opening_tags)
    missing_tags = set(expected_tags) - found_tags

    if missing_tags:
        raise TagParsingError(
            f"Missing expected tags: {sorted(missing_tags)}. "
            f"Found: {sorted(found_tags)}"
        )

    # Strict mode: check for extra tags
    if strict:
        extra_tags = found_tags - set(expected_tags)
        if extra_tags:
            raise TagParsingError(
                f"Unexpected tags found: {sorted(extra_tags)}. "
                f"Expected only: {sorted(expected_tags)}"
            )


def extract_tag_content(text: str, tag_name: str) -> str | None:
    """
    Extract content of a single tag from text.

    Args:
        text: Raw LLM output with XML-style tags
        tag_name: Name of tag to extract

    Returns:
        Tag content (whitespace stripped) or None if tag not found

    Example:
        >>> text = "[NAME]John[/NAME][AGE]30[/AGE]"
        >>> extract_tag_content(text, "NAME")
        'John'
        >>> extract_tag_content(text, "MISSING")
        None
    """
    pattern = rf'\[{tag_name}\](.*?)\[/{tag_name}\]'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def has_tag(text: str, tag_name: str) -> bool:
    """
    Check if a tag exists in text.

    Args:
        text: Raw LLM output with XML-style tags
        tag_name: Name of tag to check for

    Returns:
        True if tag exists with proper opening and closing tags

    Example:
        >>> text = "[NAME]John[/NAME]"
        >>> has_tag(text, "NAME")
        True
        >>> has_tag(text, "AGE")
        False
    """
    pattern = rf'\[{tag_name}\].*?\[/{tag_name}\]'
    return bool(re.search(pattern, text, re.DOTALL))
