"""Data loading utilities for medical documents."""

import json
from pathlib import Path
from typing import List
from app.core.retriever import Document


async def load_medical_documents() -> List[Document]:
    """Load mental health medication documents from JSON file.

    Returns:
        List of Document objects ready for indexing
    """
    # Get path to data file
    data_path = Path(__file__).parent.parent.parent / "data" / "mental_health_meds.json"

    # Load JSON data
    with open(data_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Convert to Document objects
    documents = []
    for item in raw_data:
        # Create searchable content combining all fields
        content = f"""
Medication: {item['name']}
Class: {item['class']}

Uses and Indications:
{item['uses']}

Dosage Information:
{item['dosage']}

Common Side Effects:
{item['side_effects']}

Important Warnings:
{item['warnings']}

Drug Interactions:
{item['interactions']}
        """.strip()

        # Create document with metadata
        doc = Document(
            id=item['id'],
            content=content,
            metadata=item
        )
        documents.append(doc)

    return documents
