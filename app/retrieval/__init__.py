"""Retrieval strategies for semantic search.

Three strategies available:
1. Simple: query → embedding → pgvector search → return top_k
2. Rerank: query → search top_k*4 → rerank → return top_k
3. Advanced: query → LLM expand → search all → merge → rerank → return top_k
"""

from app.retrieval.simple import SimpleRetriever
from app.retrieval.rerank import RerankRetriever
from app.retrieval.advanced import AdvancedRetriever
from app.retrieval.factory import get_retriever

__all__ = [
    "SimpleRetriever",
    "RerankRetriever",
    "AdvancedRetriever",
    "get_retriever",
]
