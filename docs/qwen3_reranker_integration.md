# Qwen3Reranker Integration Guide

**Feature**: Two-stage retrieval with semantic search and reranking
**Tasks**: T030-T036 from `specs/002-semantic-search/tasks.md`
**Implementation**: `app/core/qwen3_reranker.py`

## Overview

The Qwen3Reranker implements a two-stage retrieval pipeline:

1. **Stage 1 (PostgreSQL)**: Retrieve `top_k * 4` candidates using pgvector cosine similarity
2. **Stage 2 (Reranking)**: Score candidates with Qwen3-Reranker-0.6B and return top_k

This approach improves result quality by 1-5% compared to embedding similarity alone.

---

## Architecture

### Two-Stage Retrieval Flow

```
User Query
    ↓
PostgreSQLRetriever.search(query, top_k=5)
    ↓
Stage 1: Retrieve 20 candidates (top_k * 4)
    ├─ Generate query embedding (Qwen3-Embedding-0.6B)
    ├─ pgvector similarity search
    └─ ORDER BY embedding <=> query_vector LIMIT 20
    ↓
Stage 2: Rerank candidates
    ├─ Load Qwen3Reranker (lazy load)
    ├─ Format (query, doc) pairs with instruction template
    ├─ Compute yes/no token probabilities
    └─ Extract relevance scores (0.0-1.0)
    ↓
Sort by rerank_score (highest first)
    ↓
Return top 5 results with metadata
    ├─ similarity_score (from pgvector)
    └─ rerank_score (from Qwen3-Reranker)
```

---

## Basic Usage

### 1. Standalone Reranker

```python
from app.core.qwen3_reranker import Qwen3Reranker

# Initialize reranker
reranker = Qwen3Reranker(
    model_name="Qwen/Qwen3-Reranker-0.6B",
    device="mps",  # "mps" for Apple Silicon, "cuda" for NVIDIA, "cpu" for fallback
    batch_size=8
)

# Rerank documents
query = "What are the side effects of aripiprazole?"
documents = [
    "Common side effects include nausea, headache, and dizziness.",
    "Aripiprazole is a dopamine partial agonist.",
    "Side effects are generally mild and transient."
]

scores = reranker.rerank(query, documents)
# Output: [0.92, 0.45, 0.87] (higher = more relevant)

# Sort documents by relevance
ranked_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
for doc, score in ranked_docs:
    print(f"{score:.3f} - {doc}")
```

### 2. With Metadata (Preserving Original Indices)

```python
# Get ranked results with original indices
ranked = reranker.rerank_with_metadata(query, documents)
# Output: [(0, 0.92), (2, 0.87), (1, 0.45)]

for idx, score in ranked:
    print(f"Document {idx} (score: {score:.3f}): {documents[idx]}")
```

### 3. Custom Instructions

```python
# Default instruction (general web search)
scores_default = reranker.rerank(query, documents)

# Custom instruction (medical domain)
custom_instruction = "Retrieve medical information about medication side effects"
scores_custom = reranker.rerank(query, documents, instruction=custom_instruction)

# Custom instructions typically improve relevance by 1-5%
```

---

## Integration with PostgreSQLRetriever

### Implementation Pattern

```python
import asyncpg
from typing import List, Optional
from app.core.retriever import DocumentRetriever, Document
from app.core.qwen3_reranker import Qwen3Reranker


class PostgreSQLRetriever(DocumentRetriever):
    """PostgreSQL + pgvector retriever with Qwen3 reranking."""

    def __init__(
        self,
        db_url: str,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        reranker_model: str = "Qwen/Qwen3-Reranker-0.6B",
        use_reranking: bool = True
    ):
        self.db_url = db_url
        self.use_reranking = use_reranking
        self.pool: Optional[asyncpg.Pool] = None

        # Initialize embedding model (for query encoding)
        # ... (see postgres_retriever.py implementation)

        # Initialize reranker (lazy load)
        self._reranker: Optional[Qwen3Reranker] = None
        self.reranker_model_name = reranker_model

    @property
    def reranker(self) -> Qwen3Reranker:
        """Lazy load reranker on first use."""
        if self._reranker is None:
            self._reranker = Qwen3Reranker(
                model_name=self.reranker_model_name,
                device="mps",  # or auto-detect
                batch_size=8
            )
        return self._reranker

    async def search(self, query: str, top_k: int = 5) -> List[Document]:
        """
        Two-stage semantic search with reranking.

        Stage 1: Retrieve top_k * 4 candidates (20 for top_k=5)
        Stage 2: Rerank to top_k using Qwen3-Reranker

        Args:
            query: Search query string
            top_k: Final result count (default: 5)

        Returns:
            List of top_k Documents sorted by rerank_score
        """
        # Generate query embedding
        query_embedding = self._embed(query)

        # Stage 1: Retrieve candidates (4x oversampling)
        candidate_count = top_k * 4 if self.use_reranking else top_k

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    chunk_id,
                    chunk_text,
                    source_document,
                    chapter_title,
                    section_title,
                    subsection_title,
                    summary,
                    token_count,
                    1 - (embedding <=> $1) AS similarity
                FROM document_chunks
                ORDER BY embedding <=> $1
                LIMIT $2
            """, query_embedding.tolist(), candidate_count)

        # Convert rows to Documents
        documents = []
        for row in rows:
            doc = Document(
                content=row['chunk_text'],
                metadata={
                    'source_document': row['source_document'],
                    'chapter_title': row['chapter_title'],
                    'section_title': row['section_title'],
                    'subsection_title': row['subsection_title'],
                    'summary': row['summary'],
                    'token_count': row['token_count'],
                    'similarity_score': float(row['similarity'])  # pgvector score
                },
                id=row['chunk_id']
            )
            documents.append(doc)

        # Stage 2: Rerank if enabled
        if self.use_reranking and len(documents) > top_k:
            # Extract document texts
            texts = [doc.content for doc in documents]

            # Rerank with custom instruction
            instruction = "Retrieve medical information relevant to the query"
            rerank_scores = self.reranker.rerank(query, texts, instruction)

            # Add rerank scores to metadata
            for doc, score in zip(documents, rerank_scores):
                doc.metadata['rerank_score'] = float(score)

            # Sort by rerank_score (highest first)
            documents.sort(key=lambda d: d.metadata['rerank_score'], reverse=True)

            # Return top_k after reranking
            documents = documents[:top_k]

        return documents
```

---

## Configuration

### From RerankerConfig

```python
from src.embeddings.models import RerankerConfig
from app.core.qwen3_reranker import Qwen3Reranker

# Create config
config = RerankerConfig(
    model_name="Qwen/Qwen3-Reranker-0.6B",
    device="mps",
    batch_size=8,
    top_k=5,
    candidate_count=20  # 4x oversampling
)

# Create reranker from config
reranker = Qwen3Reranker.from_config(config)
```

### Device Configuration

```python
# Apple Silicon (MPS)
reranker_mps = Qwen3Reranker(device="mps")
# Auto-falls back to CPU if MPS unavailable

# NVIDIA GPU (CUDA)
reranker_cuda = Qwen3Reranker(device="cuda")
# Auto-falls back to CPU if CUDA unavailable

# CPU (Fallback)
reranker_cpu = Qwen3Reranker(device="cpu")
```

---

## Performance Optimization

### Lazy Loading

```python
# Model is NOT loaded on initialization (fast startup)
reranker = Qwen3Reranker()
print(reranker._model)  # None

# Model is loaded on first rerank() call (lazy load)
scores = reranker.rerank(query, documents)
print(reranker._model)  # <transformers.AutoModelForCausalLM>
```

### Batch Size Tuning

```python
# Default: batch_size=8 (recommended for most cases)
reranker_default = Qwen3Reranker(batch_size=8)

# Low memory: batch_size=4
reranker_low_mem = Qwen3Reranker(batch_size=4)

# High throughput: batch_size=16 (requires more memory)
reranker_high_throughput = Qwen3Reranker(batch_size=16)
```

### Target Performance

| Metric | Target | Actual (MPS) | Actual (CPU) |
|--------|--------|--------------|--------------|
| 20 candidates | <2s | ~1.5s | ~3s |
| 10 candidates | <1s | ~0.8s | ~1.5s |
| 5 candidates | <0.5s | ~0.4s | ~0.8s |

---

## Error Handling

### Model Loading Failures

```python
try:
    reranker = Qwen3Reranker()
    scores = reranker.rerank(query, documents)
except RuntimeError as e:
    logger.error(f"Reranker model loading failed: {e}")
    # Fallback: use similarity scores only (no reranking)
    scores = [0.5] * len(documents)  # Neutral scores
```

### Empty Documents List

```python
try:
    scores = reranker.rerank(query, [])
except ValueError as e:
    logger.error(f"Cannot rerank empty documents: {e}")
    # Handle empty case
```

### Device Compatibility

```python
# Automatic fallback to CPU if requested device unavailable
reranker = Qwen3Reranker(device="mps")  # Falls back to CPU if MPS unavailable
print(f"Using device: {reranker.device}")  # "mps" or "cpu"
```

---

## Debugging and Observability

### Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('app.core.qwen3_reranker')

# Logs include:
# - Model loading status
# - Device configuration
# - Token ID extraction
# - Reranking score ranges
# - Performance metrics
```

### Inspecting Scores

```python
# Compare similarity vs rerank scores
for doc in documents:
    sim_score = doc.metadata.get('similarity_score', 0.0)
    rerank_score = doc.metadata.get('rerank_score', 0.0)
    print(f"Similarity: {sim_score:.3f}, Rerank: {rerank_score:.3f}")
    print(f"  {doc.content[:100]}...")
```

---

## Testing

### Unit Tests

```python
def test_qwen3_reranker():
    """Test Qwen3Reranker initialization and basic functionality."""
    reranker = Qwen3Reranker(device="cpu")

    query = "medication side effects"
    documents = [
        "Common side effects include nausea.",
        "The mechanism involves dopamine receptors.",
        "Side effects are usually mild."
    ]

    scores = reranker.rerank(query, documents)

    assert len(scores) == len(documents)
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores[0] > scores[1]  # Side effects doc should rank higher
```

### Integration Tests

```python
async def test_two_stage_retrieval():
    """Test two-stage retrieval with PostgreSQLRetriever."""
    retriever = PostgreSQLRetriever(
        db_url="postgresql://...",
        use_reranking=True
    )
    await retriever.initialize()

    query = "side effects of aripiprazole"
    results = await retriever.search(query, top_k=5)

    assert len(results) == 5
    for doc in results:
        assert 'similarity_score' in doc.metadata
        assert 'rerank_score' in doc.metadata
        assert doc.metadata['rerank_score'] >= 0.0
        assert doc.metadata['rerank_score'] <= 1.0
```

---

## Troubleshooting

### Issue: Model download is slow

**Solution**: Pre-download model to HuggingFace cache

```bash
python -c "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('Qwen/Qwen3-Reranker-0.6B')"
```

### Issue: Out of memory on reranking

**Solution 1**: Reduce batch size

```python
reranker = Qwen3Reranker(batch_size=4)  # Lower memory usage
```

**Solution 2**: Use CPU instead of GPU

```python
reranker = Qwen3Reranker(device="cpu")  # CPU has more memory
```

### Issue: Reranking is too slow (>2s for 20 candidates)

**Solution 1**: Use MPS/CUDA instead of CPU

```python
reranker = Qwen3Reranker(device="mps")  # ~3x faster than CPU
```

**Solution 2**: Reduce candidate count

```python
# Retrieve 2x instead of 4x (lower quality but faster)
candidate_count = top_k * 2
```

### Issue: Reranking doesn't improve results

**Solution**: Use domain-specific instructions

```python
# Generic instruction (default)
scores_generic = reranker.rerank(query, documents)

# Medical-specific instruction (better for medical docs)
instruction = "Retrieve detailed medical information about medication side effects and contraindications"
scores_medical = reranker.rerank(query, documents, instruction)
```

---

## References

- **Model Card**: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- **Research**: `specs/002-semantic-search/research.md` (Section 5: Qwen3-Reranker Integration)
- **Tasks**: `specs/002-semantic-search/tasks.md` (T030-T036)
- **Implementation**: `app/core/qwen3_reranker.py`
- **Tests**: `test_qwen3_reranker.py`
