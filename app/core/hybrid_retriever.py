"""Hybrid retriever combining FAISS vector search with BM25 keyword search.

This module implements a production-ready hybrid retrieval system that combines:
- FAISS vector similarity search for semantic understanding
- BM25 keyword search for exact term matching
- Weighted score combination with normalization
- Parent-child document retrieval support
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
import logging

from app.core.retriever import DocumentRetriever, Document

logger = logging.getLogger(__name__)


class HybridRetriever(DocumentRetriever):
    """Hybrid retrieval combining vector search and keyword search.

    This retriever implements a sophisticated hybrid approach that:
    1. Performs parallel vector and keyword searches
    2. Normalizes scores to [0, 1] range for fair comparison
    3. Combines scores using weighted average (alpha parameter)
    4. Supports parent-child document relationships
    5. Provides incremental index updates

    Architecture:
        - FAISS (vector): Semantic similarity via embeddings
        - BM25 (keyword): Statistical term matching via TF-IDF
        - Score fusion: Weighted linear combination
        - Parent retrieval: Search children, return parents

    Attributes:
        _faiss_retriever: FAISSRetriever instance for vector search
        _documents: List of all documents in the index
        _bm25_index: BM25Okapi index for keyword search
        _tokenized_corpus: Tokenized documents for BM25
        _alpha: Weight for vector vs keyword scores (0=BM25 only, 1=FAISS only)
        _doc_id_to_idx: Mapping from document IDs to indices
    """

    def __init__(
        self,
        faiss_retriever: DocumentRetriever,
        documents: List[Document],
        alpha: float = 0.5
    ) -> None:
        """Initialize hybrid retriever with FAISS and BM25 indices.

        Args:
            faiss_retriever: Pre-configured FAISSRetriever instance
            documents: Initial list of documents to index
            alpha: Weight for combining scores (default 0.5 for equal weighting)
                  - alpha=0.0: BM25 only (pure keyword search)
                  - alpha=0.5: Equal combination (balanced hybrid)
                  - alpha=1.0: FAISS only (pure semantic search)

        Raises:
            ValueError: If alpha not in [0, 1] range
            ValueError: If documents list is empty
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")

        if not documents:
            raise ValueError("documents list cannot be empty")

        self._faiss_retriever = faiss_retriever
        self._documents = documents
        self._alpha = alpha

        # Build document ID to index mapping for fast lookups
        self._doc_id_to_idx: Dict[str, int] = {}
        for idx, doc in enumerate(documents):
            if doc.id:
                self._doc_id_to_idx[doc.id] = idx

        # Build BM25 index
        self._tokenized_corpus = self._tokenize_documents(documents)
        self._bm25_index = BM25Okapi(self._tokenized_corpus)

        logger.info(
            f"Initialized HybridRetriever with {len(documents)} documents "
            f"(alpha={alpha:.2f}, FAISS weight={alpha:.2f}, BM25 weight={1-alpha:.2f})"
        )

    def _tokenize_documents(self, docs: List[Document]) -> List[List[str]]:
        """Tokenize documents for BM25 indexing.

        Simple whitespace tokenization with lowercasing. For production,
        consider more sophisticated tokenization:
        - Stemming/lemmatization
        - Stop word removal
        - N-gram generation
        - Domain-specific tokenization

        Args:
            docs: List of documents to tokenize

        Returns:
            List of tokenized documents (each document is a list of tokens)
        """
        tokenized = []
        for doc in docs:
            # Simple tokenization: lowercase and split on whitespace
            tokens = doc.content.lower().split()
            tokenized.append(tokens)
        return tokenized

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search using hybrid approach combining vector and keyword search.

        Search process:
        1. Perform FAISS vector search (semantic similarity)
        2. Perform BM25 keyword search (term matching)
        3. Normalize both score sets to [0, 1]
        4. Combine scores: combined = alpha * vector + (1-alpha) * keyword
        5. Sort by combined scores and return top_k documents
        6. If parent_id exists, return parent documents instead

        Args:
            query: Search query string
            top_k: Number of top results to return (default 3)

        Returns:
            List of top_k most relevant documents sorted by combined score

        Note:
            - Returns empty list if no documents indexed
            - Handles parent-child relationships automatically
            - Deduplicates results when parents are returned
        """
        if not self._documents:
            logger.warning("Search called on empty index")
            return []

        # Adjust top_k to available documents
        effective_top_k = min(top_k, len(self._documents))

        # Perform FAISS vector search (get more candidates for better fusion)
        candidate_k = min(effective_top_k * 3, len(self._documents))
        vector_docs = await self._faiss_retriever.search(query, top_k=candidate_k)

        # Perform BM25 keyword search
        bm25_scores = self._bm25_search(query, top_k=candidate_k)

        # Get vector scores from FAISS results
        vector_scores = {
            id(doc): 1.0 / (idx + 1)  # Reciprocal rank scoring
            for idx, doc in enumerate(vector_docs)
        }

        # Normalize scores to [0, 1]
        vector_scores_norm = self._normalize_scores(vector_scores)
        bm25_scores_norm = self._normalize_scores(bm25_scores)

        # Combine scores with weighted average
        combined_scores = self._combine_scores(vector_scores_norm, bm25_scores_norm)

        # Sort by combined score (descending)
        sorted_doc_ids = sorted(
            combined_scores.keys(),
            key=lambda doc_id: combined_scores[doc_id],
            reverse=True
        )

        # Get top_k documents
        result_docs = []
        seen_parent_ids = set()

        for doc_id in sorted_doc_ids:
            if len(result_docs) >= effective_top_k:
                break

            # Find the document by object id
            doc = next((d for d in self._documents if id(d) == doc_id), None)
            if doc is None:
                continue

            # Handle parent-child relationships
            if "parent_id" in doc.metadata and doc.metadata["parent_id"]:
                parent_id = doc.metadata["parent_id"]

                # Skip if we've already included this parent
                if parent_id in seen_parent_ids:
                    continue

                # Find and return parent document
                parent_doc = self._get_parent_document(parent_id)
                if parent_doc:
                    result_docs.append(parent_doc)
                    seen_parent_ids.add(parent_id)
                else:
                    # Fallback to child if parent not found
                    result_docs.append(doc)
            else:
                result_docs.append(doc)

        logger.info(
            f"Hybrid search returned {len(result_docs)} documents "
            f"(vector_weight={self._alpha:.2f}, bm25_weight={1-self._alpha:.2f})"
        )

        return result_docs

    def _bm25_search(self, query: str, top_k: int) -> Dict[int, float]:
        """Perform BM25 keyword search.

        Args:
            query: Search query string
            top_k: Number of top results to consider

        Returns:
            Dictionary mapping document object IDs to BM25 scores
        """
        # Tokenize query
        query_tokens = query.lower().split()

        # Get BM25 scores for all documents
        scores = self._bm25_index.get_scores(query_tokens)

        # Map scores to document object IDs
        score_dict = {}
        for idx, score in enumerate(scores):
            if idx < len(self._documents):
                doc_id = id(self._documents[idx])
                score_dict[doc_id] = float(score)

        return score_dict

    def _normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Normalize scores to [0, 1] range using min-max normalization.

        Normalization formula: (score - min) / (max - min)

        Args:
            scores: Dictionary mapping document IDs to raw scores

        Returns:
            Dictionary with normalized scores in [0, 1] range

        Note:
            - Returns all zeros if all scores are identical
            - Handles empty score dictionary gracefully
        """
        if not scores:
            return {}

        score_values = list(scores.values())
        min_score = min(score_values)
        max_score = max(score_values)

        # Handle case where all scores are identical
        if max_score == min_score:
            return {doc_id: 0.5 for doc_id in scores}

        # Min-max normalization
        normalized = {}
        for doc_id, score in scores.items():
            normalized[doc_id] = (score - min_score) / (max_score - min_score)

        return normalized

    def _combine_scores(
        self,
        vector_scores: Dict[int, float],
        bm25_scores: Dict[int, float]
    ) -> Dict[int, float]:
        """Combine vector and BM25 scores using weighted average.

        Combination formula:
            combined_score = alpha * vector_score + (1 - alpha) * bm25_score

        Where:
            - alpha is the weight parameter (0 to 1)
            - vector_score is normalized FAISS similarity
            - bm25_score is normalized BM25 relevance

        Args:
            vector_scores: Normalized vector similarity scores
            bm25_scores: Normalized BM25 keyword scores

        Returns:
            Dictionary with combined scores for all documents

        Note:
            - Documents not in vector_scores get score 0 for vector component
            - Documents not in bm25_scores get score 0 for BM25 component
            - This allows graceful handling of partial results
        """
        # Get all unique document IDs from both score sets
        all_doc_ids = set(vector_scores.keys()) | set(bm25_scores.keys())

        combined = {}
        for doc_id in all_doc_ids:
            vector_score = vector_scores.get(doc_id, 0.0)
            bm25_score = bm25_scores.get(doc_id, 0.0)

            # Weighted combination
            combined[doc_id] = (
                self._alpha * vector_score +
                (1 - self._alpha) * bm25_score
            )

        return combined

    def _get_parent_document(self, parent_id: str) -> Optional[Document]:
        """Retrieve parent document by ID.

        Args:
            parent_id: Parent document ID to retrieve

        Returns:
            Parent document if found, None otherwise
        """
        idx = self._doc_id_to_idx.get(parent_id)
        if idx is not None and 0 <= idx < len(self._documents):
            return self._documents[idx]

        # Fallback: linear search if ID mapping failed
        for doc in self._documents:
            if doc.id == parent_id:
                return doc

        logger.warning(f"Parent document not found: {parent_id}")
        return None

    async def add_documents(self, docs: List[Document]) -> None:
        """Add new documents to both FAISS and BM25 indices.

        This method performs incremental updates to maintain index consistency:
        1. Updates FAISS vector index with new embeddings
        2. Rebuilds BM25 index with expanded corpus
        3. Updates document ID mappings
        4. Maintains document list

        Args:
            docs: List of new documents to add to the indices

        Note:
            - BM25 index is rebuilt from scratch (no incremental update)
            - FAISS index supports true incremental updates
            - Consider periodic full reindexing for optimal BM25 performance
        """
        if not docs:
            logger.warning("add_documents called with empty list")
            return

        # Add to FAISS index (incremental)
        await self._faiss_retriever.add_documents(docs)

        # Update document list
        start_idx = len(self._documents)
        self._documents.extend(docs)

        # Update document ID mapping
        for idx, doc in enumerate(docs, start=start_idx):
            if doc.id:
                self._doc_id_to_idx[doc.id] = idx

        # Rebuild BM25 index with all documents
        # Note: BM25Okapi doesn't support incremental updates,
        # so we rebuild the entire index
        self._tokenized_corpus = self._tokenize_documents(self._documents)
        self._bm25_index = BM25Okapi(self._tokenized_corpus)

        logger.info(
            f"Added {len(docs)} documents to hybrid index "
            f"(total documents: {len(self._documents)})"
        )

    def get_stats(self) -> Dict[str, any]:
        """Get retriever statistics for monitoring and debugging.

        Returns:
            Dictionary containing:
                - total_documents: Total number of indexed documents
                - alpha: Current weight parameter
                - faiss_weight: Effective FAISS weight
                - bm25_weight: Effective BM25 weight
                - indexed_doc_ids: Number of documents with IDs
        """
        return {
            "total_documents": len(self._documents),
            "alpha": self._alpha,
            "faiss_weight": self._alpha,
            "bm25_weight": 1 - self._alpha,
            "indexed_doc_ids": len(self._doc_id_to_idx),
        }

    def set_alpha(self, alpha: float) -> None:
        """Update the alpha weight parameter dynamically.

        This allows runtime adjustment of the balance between
        semantic (FAISS) and keyword (BM25) search.

        Args:
            alpha: New weight value in [0, 1] range

        Raises:
            ValueError: If alpha not in [0, 1] range

        Examples:
            >>> retriever.set_alpha(0.0)  # Pure BM25 keyword search
            >>> retriever.set_alpha(0.5)  # Balanced hybrid
            >>> retriever.set_alpha(1.0)  # Pure FAISS semantic search
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")

        old_alpha = self._alpha
        self._alpha = alpha

        logger.info(
            f"Updated alpha: {old_alpha:.2f} -> {alpha:.2f} "
            f"(FAISS weight: {alpha:.2f}, BM25 weight: {1-alpha:.2f})"
        )
