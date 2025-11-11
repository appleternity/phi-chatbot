"""Unit tests for document retriever."""

import pytest
from app.core.retriever import FAISSRetriever, Document


@pytest.mark.asyncio
async def test_retriever_add_documents():
    """Test adding documents to retriever."""
    retriever = FAISSRetriever()
    docs = [
        Document(id="1", content="Test document about Sertraline", metadata={"name": "Sertraline"}),
        Document(id="2", content="Test document about Bupropion", metadata={"name": "Bupropion"}),
    ]

    await retriever.add_documents(docs)

    # Should be able to search now
    results = await retriever.search("Sertraline", top_k=1)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_retriever_search_relevance():
    """Test that search returns relevant results."""
    retriever = FAISSRetriever()
    docs = [
        Document(
            id="sertraline",
            content="Sertraline is an SSRI antidepressant used for depression and anxiety",
            metadata={"name": "Sertraline"},
        ),
        Document(
            id="bupropion",
            content="Bupropion is an NDRI antidepressant used for depression",
            metadata={"name": "Bupropion"},
        ),
    ]

    await retriever.add_documents(docs)

    # Search for SSRI should return Sertraline first
    results = await retriever.search("SSRI antidepressant", top_k=2)
    assert len(results) > 0
    assert results[0].id == "sertraline"


@pytest.mark.asyncio
async def test_retriever_empty():
    """Test searching empty retriever."""
    retriever = FAISSRetriever()
    results = await retriever.search("test query", top_k=3)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_retriever_top_k():
    """Test top_k parameter."""
    retriever = FAISSRetriever()
    docs = [
        Document(id=f"doc-{i}", content=f"Document {i} about medication", metadata={})
        for i in range(10)
    ]

    await retriever.add_documents(docs)

    # Request top 3
    results = await retriever.search("medication", top_k=3)
    assert len(results) == 3

    # Request top 5
    results = await retriever.search("medication", top_k=5)
    assert len(results) == 5
