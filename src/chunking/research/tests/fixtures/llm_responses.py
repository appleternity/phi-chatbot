"""
Mock LLM response templates for testing.

This module provides realistic mock responses for all three phases of chunking.
"""

# Phase 1: Structure Analysis Mock Response (TSV format)
MOCK_STRUCTURE_TSV = """Introduction to Testing\t1\t0\t1500\tROOT
Why Test?\t2\t0\t750\tIntroduction to Testing
Benefits\t3\t50\t350\tWhy Test?
Common Pitfalls\t3\t350\t750\tWhy Test?
Types of Testing\t2\t750\t1500\tIntroduction to Testing"""

MOCK_STRUCTURE_RESPONSE = {
    "id": "chatcmpl-structure-test",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": MOCK_STRUCTURE_TSV
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600
    }
}

# Phase 2: Boundary Detection Mock Response (TSV format)
MOCK_BOUNDARIES_TSV = """0\tDOCUMENT_START\tBeginning of document
750\tSECTION_BREAK\tNew section 'Types of Testing' begins with distinct topic shift
1500\tDOCUMENT_END\tEnd of document"""

MOCK_BOUNDARIES_RESPONSE = {
    "id": "chatcmpl-boundaries-test",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": MOCK_BOUNDARIES_TSV
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 400,
        "completion_tokens": 80,
        "total_tokens": 480
    }
}

# Phase 3: Metadata Generation Mock Response (TSV format)
MOCK_METADATA_TSV = """Introduction to Testing\tWhy Test?\tBenefits\tDiscusses the key benefits of software testing including early bug detection and improved code quality"""

MOCK_METADATA_RESPONSE = {
    "id": "chatcmpl-metadata-test",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": MOCK_METADATA_TSV
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 300,
        "completion_tokens": 60,
        "total_tokens": 360
    }
}

# Phase 3: Contextual Prefix Generation Mock Response (plain text)
MOCK_CONTEXTUAL_PREFIX = "This chunk is from Chapter 'Introduction to Testing', Section 'Why Test?', discussing the benefits of software testing."

MOCK_PREFIX_RESPONSE = {
    "id": "chatcmpl-prefix-test",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": MOCK_CONTEXTUAL_PREFIX
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 200,
        "completion_tokens": 40,
        "total_tokens": 240
    }
}

# Sample test document
SAMPLE_DOCUMENT_TEXT = """# Introduction to Testing

Testing is a critical part of software development.

## Why Test?

### Benefits

Testing helps catch bugs early in the development process. It improves code quality and maintainability.

### Common Pitfalls

Many developers skip testing due to time constraints. This often leads to more time spent debugging later.

## Types of Testing

There are several types of testing including unit tests, integration tests, and end-to-end tests. Each serves a different purpose in ensuring software quality."""

# Expected structure for sample document
EXPECTED_STRUCTURE = {
    "document_id": "sample",
    "chapter_title": "Introduction to Testing",
    "chapter_number": None,
    "sections": [
        {
            "title": "Introduction to Testing",
            "level": 1,
            "start_char": 0,
            "end_char": 1500,
            "parent_section": None
        },
        {
            "title": "Why Test?",
            "level": 2,
            "start_char": 0,
            "end_char": 750,
            "parent_section": "Introduction to Testing"
        },
        {
            "title": "Types of Testing",
            "level": 2,
            "start_char": 750,
            "end_char": 1500,
            "parent_section": "Introduction to Testing"
        }
    ],
    "metadata": {},
    "analysis_model": "openai/gpt-4o"
}

# Mock responses by model
MOCK_RESPONSES_BY_MODEL = {
    "openai/gpt-4o": MOCK_STRUCTURE_RESPONSE,
    "google/gemini-2.0-flash-exp": MOCK_METADATA_RESPONSE,
}
