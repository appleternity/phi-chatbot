"""Abstract document retriever interface and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
import json
import os
from pathlib import Path
from datetime import datetime
import logging
import torch

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document representation."""

    content: str
    metadata: dict
    id: Optional[str] = None


class DocumentRetriever(ABC):
    """Abstract interface for document retrieval."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of most relevant documents
        """
        pass

    @abstractmethod
    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to the index.

        Args:
            docs: List of documents to add
        """
        pass


class FAISSRetriever(DocumentRetriever):
    """FAISS-based vector similarity search implementation.

    This is a POC implementation using in-memory FAISS.
    For production, consider:
    - FAISS with disk persistence
    - Cloud vector databases (Pinecone, Weaviate, Qdrant)
    - Hybrid search with BM25
    """

    def __init__(self, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        """Initialize FAISS retriever.

        Args:
            embedding_model: Name of sentence-transformers model to use
        """
        # Detect and configure device (MPS for Apple Silicon, fallback to CPU)
        if torch.backends.mps.is_available():
            self._device = "mps"
            logger.info("Using device: mps for embeddings (Apple Metal Performance Shaders)")
        else:
            self._device = "cpu"
            logger.info("Using device: cpu for embeddings")

        # Initialize SentenceTransformer with the selected device
        self._model = SentenceTransformer(embedding_model, device=self._device)

        self._embedding_model = embedding_model
        self._documents: List[Document] = []
        self._embeddings: Optional[np.ndarray] = None
        self._index: Optional[object] = None  # FAISS index (lazy loaded)

    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to the index incrementally.

        Only encodes new documents, avoiding re-encoding of existing ones.

        Args:
            docs: List of new documents to add
        """
        if not docs:
            return

        # Track starting point for new documents
        num_existing_docs = len(self._documents)
        self._documents.extend(docs)

        # Only encode NEW documents (not re-encode existing)
        new_texts = [doc.content for doc in docs]
        new_embeddings = self._model.encode(
            new_texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )

        # Build or update embeddings array
        if self._embeddings is None:
            self._embeddings = new_embeddings
        else:
            # Concatenate new embeddings to existing ones
            self._embeddings = np.vstack([self._embeddings, new_embeddings])

        # Build or update FAISS index
        import faiss

        dimension = new_embeddings.shape[1]

        if self._index is None:
            # Initial index creation
            self._index = faiss.IndexFlatL2(dimension)
            self._index.add(new_embeddings.astype('float32'))
            logger.info(f"Created new FAISS index with {len(docs)} documents")
        else:
            # Incremental addition using FAISS add()
            self._index.add(new_embeddings.astype('float32'))
            logger.info(f"Added {len(docs)} documents to existing index (total: {len(self._documents)})")

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents using vector similarity."""
        if not self._documents or self._index is None:
            return []

        # Encode query
        query_embedding = self._model.encode([query], convert_to_numpy=True, show_progress_bar=False)

        # Search
        k = min(top_k, len(self._documents))
        distances, indices = self._index.search(query_embedding.astype('float32'), k)

        # Return documents
        results = []
        for idx in indices[0]:
            if idx < len(self._documents):
                results.append(self._documents[idx])

        return results

    async def save_index(self, path: str) -> None:
        """Save FAISS index, embeddings, and documents to disk.

        Args:
            path: Directory path where index artifacts will be saved

        Raises:
            ValueError: If index is empty or not initialized
            IOError: If unable to write to disk
        """
        if self._index is None or not self._documents:
            raise ValueError("Cannot save empty index. Add documents first.")

        try:
            # Create directory if it doesn't exist
            save_dir = Path(path)
            save_dir.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            index_path = save_dir / "faiss_index.pkl"
            with open(index_path, "wb") as f:
                pickle.dump(self._index, f)
            logger.info(f"Saved FAISS index to {index_path}")

            # Save documents
            docs_path = save_dir / "documents.pkl"
            with open(docs_path, "wb") as f:
                pickle.dump(self._documents, f)
            logger.info(f"Saved {len(self._documents)} documents to {docs_path}")

            # Save embeddings
            embeddings_path = save_dir / "embeddings.npy"
            np.save(embeddings_path, self._embeddings)
            logger.info(f"Saved embeddings to {embeddings_path}")

            # Save metadata
            metadata = {
                "model": self._embedding_model,
                "timestamp": datetime.now().isoformat(),
                "doc_count": len(self._documents),
                "embedding_dim": self._embeddings.shape[1] if self._embeddings is not None else 0,
            }
            metadata_path = save_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved metadata to {metadata_path}")

            logger.info(f"Successfully saved complete index to {path}")

        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise IOError(f"Failed to save index to {path}: {e}")

    @classmethod
    async def load_index(cls, path: str, embedding_model: str) -> "FAISSRetriever":
        """Load pre-computed FAISS index from disk.

        Args:
            path: Directory path containing saved index artifacts
            embedding_model: Name of embedding model (must match saved index)

        Returns:
            FAISSRetriever instance with loaded index

        Raises:
            FileNotFoundError: If index artifacts not found
            ValueError: If index validation fails
            IOError: If unable to read from disk
        """
        load_dir = Path(path)

        # Validate directory exists
        if not load_dir.exists():
            raise FileNotFoundError(f"Index directory not found: {path}")

        try:
            # Define file paths
            index_path = load_dir / "faiss_index.pkl"
            docs_path = load_dir / "documents.pkl"
            embeddings_path = load_dir / "embeddings.npy"
            metadata_path = load_dir / "metadata.json"

            # Validate all required files exist
            missing_files = []
            for file_path in [index_path, docs_path, embeddings_path, metadata_path]:
                if not file_path.exists():
                    missing_files.append(file_path.name)

            if missing_files:
                raise FileNotFoundError(
                    f"Missing index artifacts in {path}: {', '.join(missing_files)}"
                )

            # Load metadata first for validation
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            logger.info(f"Loading index from {path} (created: {metadata['timestamp']})")

            # Validate model compatibility
            if metadata["model"] != embedding_model:
                logger.warning(
                    f"Model mismatch: index was created with '{metadata['model']}', "
                    f"but loading with '{embedding_model}'. This may cause issues."
                )

            # Load FAISS index
            with open(index_path, "rb") as f:
                faiss_index = pickle.load(f)
            logger.info(f"Loaded FAISS index")

            # Load documents
            with open(docs_path, "rb") as f:
                documents = pickle.load(f)
            logger.info(f"Loaded {len(documents)} documents")

            # Load embeddings
            embeddings = np.load(embeddings_path)
            logger.info(f"Loaded embeddings with shape {embeddings.shape}")

            # Validate integrity
            if len(documents) != metadata["doc_count"]:
                raise ValueError(
                    f"Document count mismatch: expected {metadata['doc_count']}, "
                    f"got {len(documents)}"
                )

            if embeddings.shape[0] != len(documents):
                raise ValueError(
                    f"Embedding count mismatch: {embeddings.shape[0]} embeddings "
                    f"for {len(documents)} documents"
                )

            if embeddings.shape[1] != metadata["embedding_dim"]:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {metadata['embedding_dim']}, "
                    f"got {embeddings.shape[1]}"
                )

            # Create retriever instance with loaded data
            retriever = cls(embedding_model=embedding_model)
            retriever._documents = documents
            retriever._embeddings = embeddings
            retriever._index = faiss_index

            logger.info(
                f"Successfully loaded index with {len(documents)} documents "
                f"(embedding_dim: {embeddings.shape[1]})"
            )

            return retriever

        except FileNotFoundError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise IOError(f"Failed to load index from {path}: {e}")


class BM25Retriever(DocumentRetriever):
    """BM25 keyword-based retrieval implementation.

    Future implementation for keyword-based search.
    Good for exact matches and when semantic meaning is less important.
    """

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search using BM25 algorithm."""
        raise NotImplementedError("BM25Retriever not yet implemented")

    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to BM25 index."""
        raise NotImplementedError("BM25Retriever not yet implemented")


class HybridRetriever(DocumentRetriever):
    """Hybrid retrieval combining vector search and keyword search.

    Future implementation for best of both worlds:
    - Vector search for semantic similarity
    - BM25 for keyword matching
    - Reranking for final results
    """

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search using hybrid approach."""
        raise NotImplementedError("HybridRetriever not yet implemented")

    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to hybrid index."""
        raise NotImplementedError("HybridRetriever not yet implemented")
