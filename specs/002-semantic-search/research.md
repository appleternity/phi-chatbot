# Technical Research: Semantic Search with PostgreSQL and pgvector

**Feature Branch**: `002-semantic-search`
**Research Date**: 2025-11-02
**Purpose**: Document technical decisions for implementing semantic search to replace FAISS-based in-memory retrieval

## Context

Implementing semantic search for 500+ medical document chunks using:
- **Embedding Model**: Qwen3-Embedding-0.6B (Apple MPS optimized)
- **Reranker Model**: Qwen3-Reranker-0.6B
- **Vector Database**: PostgreSQL + pgvector extension
- **Target Platform**: Apple Silicon (M1/M2/M3) with MPS acceleration

---

## 1. Qwen3-Embedding-0.6B Model Setup

### Decision: Use Hugging Face Transformers with AutoModel API and MPS Device

**Rationale**:
- **Official Support**: Qwen3-Embedding-0.6B is available on Hugging Face with transformers>=4.51.0
- **MPS Compatibility**: PyTorch transformers library has native MPS backend support since v1.12
- **Unified Memory Benefits**: Apple Silicon's unified memory architecture enables direct GPU access to full memory, ideal for ML workloads
- **Simple Integration**: Standard AutoModel/AutoTokenizer API provides consistent interface

**Implementation Details**:

```python
from transformers import AutoModel, AutoTokenizer
import torch

# Load model with MPS device
device = "mps" if torch.backends.mps.is_available() else "cpu"
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B")
model = AutoModel.from_pretrained(
    "Qwen/Qwen3-Embedding-0.6B",
    torch_dtype=torch.float32,  # MPS requires float32 (float16 not supported)
    device_map="auto"            # Automatic device placement
).to(device).eval()
```

**Model Specifications**:
- **Embedding Dimension**: 1024 (default output)
- **Context Window**: 32,768 tokens (far exceeds typical 1k token documents)
- **Sequence Length**: Sufficient for all medical chunks
- **MRL Support**: Yes (Matryoshka Representation Learning for flexible dimensions)
- **Instruction Awareness**: Yes (1-5% improvement with task-specific instructions)

**Required Libraries**:
```bash
pip install transformers>=4.51.0 torch>=2.0.0 sentence-transformers
```

**Alternatives Considered**:
- **sentence-transformers library**: Good abstraction but adds dependency layer; transformers library provides direct control
- **vLLM for inference**: Requires vLLM>=0.8.5, adds complexity for batch processing; not needed for indexing script
- **ONNX format**: Faster inference but requires conversion and testing; premature optimization

---

## 2. Batch Size and MPS Optimization

### Decision: Start with batch_size=16-32, monitor memory pressure

**Rationale**:
- **Memory Sensitivity**: Apple Silicon performance is highly sensitive to memory pressure; swap significantly degrades performance
- **Unified Memory**: M1/M2 shares memory between CPU and GPU; need headroom for system operations
- **Attention Slicing**: Required for <64GB system RAM or large sequences (>12k tokens)
- **Conservative Start**: Better to start smaller and increase based on monitoring

**Optimal Configuration by Device**:

| Device | RAM | Recommended Batch Size | Notes |
|--------|-----|----------------------|-------|
| M1 (8GB) | 8GB | 8-16 | Use attention slicing, monitor swap |
| M1/M2 (16GB) | 16GB | 16-32 | Safe for typical workloads |
| M1 Max/Ultra (32-64GB) | 32-64GB | 32-64 | Can handle larger batches |
| M2 Ultra (64GB+) | 64GB+ | 64-128 | Optimal for large-scale indexing |

**Implementation Pattern**:

```python
# Adaptive batch sizing based on available memory
import psutil

def get_optimal_batch_size():
    memory_gb = psutil.virtual_memory().total / (1024 ** 3)

    if memory_gb < 16:
        return 8
    elif memory_gb < 32:
        return 16
    elif memory_gb < 64:
        return 32
    else:
        return 64

batch_size = get_optimal_batch_size()
```

**Performance Benchmarks (2025)**:
- Apple Silicon demonstrates **superior energy efficiency** compared to other hardware platforms
- Energy consumption per iteration similar to RTX 4090, much better than A6000
- M2 Ultra 60-core GPU achieves excellent performance across batch sizes (32, 64, 128)

**Memory Optimization Techniques**:
- Use `torch.float32` for MPS (float16 not supported on Apple Silicon MPS backend)
- Enable `gradient_checkpointing=False` for inference (no backprop needed)
- Process documents in batches with `torch.no_grad()` context
- Monitor memory with `torch.mps.driver_allocated_memory()`

**Alternatives Considered**:
- **Batch size 4-8**: Too conservative, slower indexing without benefits
- **Batch size 128+**: Risk of memory pressure and swap on most Apple Silicon devices
- **Dynamic batching**: Adds complexity; static batch sizing sufficient for offline indexing

---

## 3. pgvector Configuration

### Decision: Use HNSW index with cosine distance for 1024-dimensional vectors

**Rationale**:
- **Dimensionality**: Qwen3-Embedding-0.6B outputs 1024-dimensional vectors (confirmed from model config)
- **Index Type**: HNSW superior for query performance (~1.5ms vs IVFFlat ~2.4ms vs sequential scan ~650ms)
- **Distance Metric**: Cosine similarity best for text embeddings (scale-invariant, directional)
- **Scale**: 500-1000 chunks well within HNSW capabilities (millions supported)
- **Dynamic Data**: HNSW handles incremental additions without retraining (unlike IVFFlat)

**Database Schema Design**:

```sql
-- Create extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Chunks table with vector embeddings
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_text TEXT NOT NULL,
    source_document VARCHAR(255) NOT NULL,

    -- Metadata fields
    chapter_title VARCHAR(500),
    section_title VARCHAR(500),
    subsection_title TEXT[],  -- Array for multiple subsections
    summary TEXT,
    token_count INTEGER,

    -- Vector embedding (1024 dimensions for Qwen3-Embedding-0.6B)
    embedding vector(1024) NOT NULL,

    -- Timestamps
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index for fast similarity search
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Additional indexes for metadata filtering
CREATE INDEX idx_source_document ON document_chunks(source_document);
CREATE INDEX idx_chapter_title ON document_chunks(chapter_title);
```

**HNSW Parameters**:
- **m = 16**: Number of connections per layer (default, balanced for most cases)
- **ef_construction = 64**: Size of dynamic candidate list during construction (higher = better recall, slower build)
- **ef_search**: Runtime parameter (increase for better recall during queries)

**HNSW vs IVFFlat Comparison**:

| Aspect | HNSW | IVFFlat |
|--------|------|---------|
| Query Speed | **~1.5ms** (best) | ~2.4ms |
| Build Time | Slower | **Faster** |
| Memory Usage | Higher | **Lower** |
| Data Changes | **Handles well** | Requires retraining |
| Training Step | **No training needed** | Requires training |
| Scaling | **Logarithmic** | Linear |
| Best For | **Dynamic data, high recall** | Static data, resource constrained |

**Distance Metrics Comparison**:

| Metric | Operator | Use Case | Best For |
|--------|----------|----------|----------|
| **Cosine** | `<=>` | Text embeddings | **Semantic search** (chosen) |
| L2/Euclidean | `<->` | Pixel-level similarity | Image recognition |
| Inner Product | `<#>` | Magnitude matters | Alternative item search |

**Indexing Best Practices**:
- Create index AFTER bulk data insertion (faster than incremental)
- Use `ORDER BY embedding <=> query_vector LIMIT k` for index usage
- Enable iterative index scans (pgvector 0.8.0+): `SET enable_iterative_scans = on;`
- For filtering, create partial indexes: `CREATE INDEX ... WHERE condition`
- Binary quantization (pgvector 0.8.0+): 32× memory reduction, 95% accuracy

**Alternatives Considered**:
- **IVFFlat index**: Faster build but requires retraining on data changes; not suitable for potentially evolving dataset
- **L2 distance**: Works but cosine is standard for text embeddings and scale-invariant
- **No index (sequential scan)**: 430× slower (~650ms vs ~1.5ms); unacceptable for production

---

## 4. PostgreSQL Python Client

### Decision: Use psycopg2 for synchronous operations, asyncpg if async needed

**Rationale**:
- **Current Compatibility**: Existing FAISSRetriever uses async/await pattern with LangGraph
- **Performance**: asyncpg is 3-5× faster for high concurrency workloads
- **LangGraph Integration**: LangGraph expects async retriever interface (`async def search()`)
- **Connection Pooling**: Both support pooling; asyncpg has native async pool

**Implementation Recommendation**:

**For LangGraph Backend (async required)**:
```python
import asyncpg
from typing import List

class PostgreSQLRetriever(DocumentRetriever):
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def initialize(self):
        """Create connection pool on startup"""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )

    async def search(self, query: str, top_k: int = 5) -> List[Document]:
        """Async similarity search"""
        query_embedding = self._embed(query)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT chunk_id, chunk_text, source_document,
                       chapter_title, section_title, subsection_title,
                       summary, token_count,
                       1 - (embedding <=> $1) AS similarity
                FROM document_chunks
                ORDER BY embedding <=> $1
                LIMIT $2
            """, query_embedding, top_k)

        return [self._row_to_document(row) for row in rows]
```

**For Indexing Script (sync acceptable)**:
```python
import psycopg2
from psycopg2 import pool

class DatabaseIndexer:
    def __init__(self, db_config):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            **db_config
        )

    def index_chunk(self, chunk_data, embedding):
        """Synchronous insert for batch indexing"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_chunks
                    (chunk_id, chunk_text, embedding, ...)
                    VALUES (%s, %s, %s, ...)
                    ON CONFLICT (chunk_id) DO NOTHING
                """, (chunk_data['chunk_id'], chunk_data['chunk_text'], embedding))
            conn.commit()
        finally:
            self.pool.putconn(conn)
```

**Connection Pooling Best Practices**:

| Aspect | psycopg2 | asyncpg |
|--------|----------|---------|
| Pool Class | `ThreadedConnectionPool` | `asyncpg.create_pool()` |
| Min Connections | 1-5 | 5-10 |
| Max Connections | 10-20 | 20-50 |
| Timeout | 30-60s | 60s |
| Best For | **Indexing script** | **LangGraph backend** |

**Retry Logic Pattern**:

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def execute_with_retry(pool, query, *args):
    """Execute query with exponential backoff retry"""
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)
```

**Comparison Summary**:

| Feature | psycopg2 | asyncpg |
|---------|----------|---------|
| API Style | Sync (blocking) | **Async (non-blocking)** |
| Performance | Good for simple queries | **3-5× faster for concurrency** |
| LangGraph Compat | Requires async wrapper | **Native async** |
| Default Support | Django, SQLAlchemy | FastAPI, Sanic |
| Connection Pool | `ThreadedConnectionPool` | **Native async pool** |
| Learning Curve | **Lower (standard)** | Higher (async/await) |

**Recommendation**:
- **Indexing Script**: Use **psycopg2** (simpler, synchronous batch processing)
- **LangGraph Backend**: Use **asyncpg** (matches async interface, better concurrency)

**Alternatives Considered**:
- **psycopg3**: Modern rewrite with async support, but psycopg2 is battle-tested and widely deployed
- **SQLAlchemy ORM**: Adds abstraction layer; raw SQL more efficient for vector operations
- **pg8000**: Pure Python but slower than psycopg2's C extensions

---

## 5. Qwen3-Reranker-0.6B Integration

### Decision: Two-stage retrieval with top-20 candidates reranked to top-5

**Rationale**:
- **Quality Improvement**: Reranking typically provides 1-5% improvement in relevance
- **Cost-Effectiveness**: Rerank only top candidates (not entire corpus)
- **Speed Target**: Reranking 20 candidates completes in <2s (meets success criteria SC-003)
- **Semantic Enhancement**: Reranker evaluates query-document pairs more accurately than embedding similarity alone

**Model Usage Pattern**:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class Qwen3Reranker:
    def __init__(self, model_name="Qwen/Qwen3-Reranker-0.6B"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side='left')
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,  # MPS requires float32
            device_map="auto"
        ).eval()

        # Token IDs for yes/no scoring
        self.token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        self.token_true_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.max_length = 8192

        # Prompt template tokens
        prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self.prefix_tokens = self.tokenizer.encode(prefix, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(suffix, add_special_tokens=False)

    def format_instruction(self, instruction, query, doc):
        """Format input for reranker"""
        if instruction is None:
            instruction = 'Given a web search query, retrieve relevant passages that answer the query'
        return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"

    @torch.no_grad()
    def rerank(self, query: str, documents: List[str], instruction: str = None) -> List[float]:
        """Rerank documents and return relevance scores"""
        pairs = [self.format_instruction(instruction, query, doc) for doc in documents]

        # Tokenize and process
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation='longest_first',
            return_tensors="pt",
            max_length=self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens)
        )

        # Add prefix and suffix tokens
        for i, ele in enumerate(inputs['input_ids']):
            inputs['input_ids'][i] = self.prefix_tokens + ele.tolist() + self.suffix_tokens

        # Move to device
        for key in inputs:
            inputs[key] = inputs[key].to(self.model.device)

        # Compute scores
        outputs = self.model(**inputs)
        batch_scores = outputs.logits[:, -1, :]

        # Extract yes/no probabilities
        true_vector = batch_scores[:, self.token_true_id]
        false_vector = batch_scores[:, self.token_false_id]
        batch_scores = torch.stack([false_vector, true_vector], dim=1)
        batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)

        # Return relevance scores (higher = more relevant)
        scores = batch_scores[:, 1].exp().tolist()
        return scores
```

**Two-Stage Retrieval Flow**:

```python
async def search_with_reranking(self, query: str, top_k: int = 5) -> List[Document]:
    """
    Two-stage retrieval: semantic search + reranking

    Stage 1: Retrieve top 20 candidates using pgvector similarity
    Stage 2: Rerank to top 5 using Qwen3-Reranker
    """
    # Stage 1: Vector similarity search (retrieve 4x more candidates)
    candidate_count = top_k * 4  # 20 candidates for top_k=5
    candidates = await self._vector_search(query, top_k=candidate_count)

    # Stage 2: Rerank candidates
    documents = [doc.content for doc in candidates]
    rerank_scores = self.reranker.rerank(query, documents)

    # Combine and sort by rerank scores
    scored_docs = list(zip(candidates, rerank_scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    # Return top k after reranking
    return [doc for doc, score in scored_docs[:top_k]]
```

**Optimal Candidate Count**:

| Top K Requested | Candidates to Retrieve | Rerank Ratio | Speed Impact |
|----------------|----------------------|--------------|--------------|
| 3 | 12 | 4× | <1s |
| 5 | **20** | **4×** | **<2s (recommended)** |
| 10 | 30-40 | 3-4× | ~3s |

**Input Format**:
```
<Instruct>: {instruction}
<Query>: {query}
<Document>: {document}
```

**Output Scores**:
- Range: 0.0 to 1.0 (probability that document is relevant)
- Higher score = more relevant
- Based on yes/no token logits with log_softmax normalization

**Instruction Guidelines**:
- **Default**: "Given a web search query, retrieve relevant passages that answer the query"
- **Custom**: Task-specific instructions improve performance 1-5%
- **Language**: Write in English (training data was primarily English)
- **Examples**:
  - "Retrieve medical information about medication side effects"
  - "Find detailed guidance on pediatric medication dosing"

**Alternatives Considered**:
- **No reranking**: Simpler but lower quality; embedding similarity alone misses nuanced relevance
- **Cross-encoder reranking**: Similar approach but Qwen3-Reranker optimized for multilingual and instruction-aware tasks
- **Rerank all results**: Too expensive; reranking 100+ documents adds latency without quality benefit
- **Separate reranking step**: Could decouple but adds complexity; integrated approach cleaner

---

## 6. Docker PostgreSQL Setup

### Decision: Use official pgvector/pgvector:pg15 Docker image

**Rationale**:
- **Official Image**: Maintained by pgvector project, regularly updated
- **PostgreSQL 15**: Stable version with good pgvector support (latest is pg17, but pg15 production-ready)
- **Pre-configured**: Extension already compiled and ready to enable
- **Volume Persistence**: Easy data persistence for local development
- **Environment Variables**: Standard PostgreSQL configuration

**Docker Compose Configuration**:

```yaml
version: '3.8'

services:
  postgres-vector:
    image: pgvector/pgvector:pg15
    container_name: langgraph-postgres-vector
    restart: unless-stopped

    ports:
      - "5432:5432"

    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-medical_knowledge}

    volumes:
      # Persistent data storage
      - postgres_data:/var/lib/postgresql/data

      # Initialization scripts (optional)
      - ./init-scripts:/docker-entrypoint-initdb.d

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5

    networks:
      - langgraph-network

volumes:
  postgres_data:
    driver: local

networks:
  langgraph-network:
    driver: bridge
```

**Environment Variables (.env file)**:

```bash
# PostgreSQL Configuration
POSTGRES_USER=medical_rag_user
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=medical_knowledge

# Connection String
DATABASE_URL=postgresql://medical_rag_user:secure_password_here@localhost:5432/medical_knowledge
```

**Initialization Script** (`init-scripts/01-init-pgvector.sql`):

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_text TEXT NOT NULL,
    source_document VARCHAR(255) NOT NULL,

    chapter_title VARCHAR(500),
    section_title VARCHAR(500),
    subsection_title TEXT[],
    summary TEXT,
    token_count INTEGER,

    embedding vector(1024) NOT NULL,

    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes (HNSW index created AFTER bulk data insertion)
CREATE INDEX idx_source_document ON document_chunks(source_document);
CREATE INDEX idx_chapter_title ON document_chunks(chapter_title);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE medical_knowledge TO medical_rag_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medical_rag_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO medical_rag_user;
```

**Setup Commands**:

```bash
# Start database
docker-compose up -d

# Verify container is running
docker ps | grep langgraph-postgres-vector

# Check logs
docker-compose logs -f postgres-vector

# Connect to database
docker exec -it langgraph-postgres-vector psql -U medical_rag_user -d medical_knowledge

# Stop database (preserves data)
docker-compose stop

# Remove database (deletes data)
docker-compose down -v
```

**Volume Persistence Best Practices**:
- **Named Volume**: `postgres_data` persists across container restarts
- **Backup Strategy**: Regular `pg_dump` to external storage
- **Development**: Local volume sufficient
- **Production**: External managed database (AWS RDS, Cloud SQL, etc.)

**Alternatives Considered**:
- **ankane/pgvector**: Alternative image, less frequently updated than official pgvector/pgvector
- **Custom Dockerfile**: More control but requires maintenance; official image sufficient
- **PostgreSQL 17**: Latest but potentially less stable; pg15 production-proven
- **Bare metal PostgreSQL**: More setup required; Docker provides consistency and portability

---

## 7. DocumentRetriever Interface Compatibility

### Decision: Implement PostgreSQLRetriever as drop-in replacement for FAISSRetriever

**Rationale**:
- **Interface Contract**: Must implement `search()` and `add_documents()` methods
- **Async Compatibility**: LangGraph expects async methods for non-blocking operations
- **Document Dataclass**: Must return List[Document] with all fields populated
- **Zero Code Changes**: RAG agent should work without modification (same closure pattern)

**Existing Interface Requirements** (from `app/core/retriever.py`):

```python
@dataclass
class Document:
    content: str                          # chunk_text
    metadata: dict                        # chapter, section, summary, etc.
    id: Optional[str] = None             # chunk_id
    parent_id: Optional[str] = None      # Not used (flat hierarchy)
    child_ids: List[str] = field(default_factory=list)  # Not used
    timestamp_start: Optional[str] = None  # Not used (no video timestamps)
    timestamp_end: Optional[str] = None    # Not used

class DocumentRetriever(ABC):
    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents"""
        pass

    @abstractmethod
    async def add_documents(self, docs: List[Document]) -> None:
        """Add documents to the index"""
        pass
```

**PostgreSQLRetriever Implementation**:

```python
import asyncpg
from typing import List, Optional
from app.core.retriever import DocumentRetriever, Document
import numpy as np
import torch

class PostgreSQLRetriever(DocumentRetriever):
    """PostgreSQL + pgvector retriever with Qwen3 embedding and reranking"""

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

        # Initialize embedding model
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.embedding_model = AutoModel.from_pretrained(
            embedding_model,
            torch_dtype=torch.float32,  # MPS requires float32
            device_map="auto"
        ).to(self.device).eval()
        self.tokenizer = AutoTokenizer.from_pretrained(embedding_model)

        # Initialize reranker (lazy load)
        self._reranker = None
        self.reranker_model_name = reranker_model

    async def initialize(self):
        """Create connection pool (call during app startup)"""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )

    async def close(self):
        """Close connection pool (call during app shutdown)"""
        if self.pool:
            await self.pool.close()

    def _embed(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        with torch.no_grad():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=8192
            ).to(self.device)

            outputs = self.embedding_model(**inputs)
            # Mean pooling
            embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]

        return embedding

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        """
        Search for relevant documents using semantic similarity

        Args:
            query: Search query string
            top_k: Number of top results to return

        Returns:
            List of most relevant Documents
        """
        # Generate query embedding
        query_embedding = self._embed(query)

        # Retrieve candidates (4x more if reranking)
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
                    'similarity': float(row['similarity'])
                },
                id=row['chunk_id'],
                parent_id=None,
                child_ids=[],
                timestamp_start=None,
                timestamp_end=None
            )
            documents.append(doc)

        # Rerank if enabled
        if self.use_reranking and len(documents) > top_k:
            documents = await self._rerank_documents(query, documents, top_k)

        return documents[:top_k]

    async def add_documents(self, docs: List[Document]) -> None:
        """
        Add documents to the index

        Note: In production, indexing is done via separate batch script.
        This method is for compatibility and testing.
        """
        async with self.pool.acquire() as conn:
            for doc in docs:
                # Generate embedding
                embedding = self._embed(doc.content)

                # Extract metadata
                chunk_id = doc.id or f"doc_{hash(doc.content)}"
                metadata = doc.metadata or {}

                # Insert into database
                await conn.execute("""
                    INSERT INTO document_chunks (
                        chunk_id, chunk_text, source_document,
                        chapter_title, section_title, subsection_title,
                        summary, token_count, embedding
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (chunk_id) DO NOTHING
                """,
                    chunk_id,
                    doc.content,
                    metadata.get('source_document', 'unknown'),
                    metadata.get('chapter_title'),
                    metadata.get('section_title'),
                    metadata.get('subsection_title', []),
                    metadata.get('summary'),
                    metadata.get('token_count'),
                    embedding.tolist()
                )

    async def _rerank_documents(
        self,
        query: str,
        documents: List[Document],
        top_k: int
    ) -> List[Document]:
        """Rerank documents using Qwen3-Reranker"""
        if self._reranker is None:
            # Lazy load reranker
            from qwen3_reranker import Qwen3Reranker
            self._reranker = Qwen3Reranker(self.reranker_model_name)

        # Extract texts
        texts = [doc.content for doc in documents]

        # Get rerank scores
        scores = self._reranker.rerank(query, texts)

        # Sort by rerank score
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Update metadata with rerank scores
        reranked = []
        for doc, score in scored_docs[:top_k]:
            doc.metadata['rerank_score'] = float(score)
            reranked.append(doc)

        return reranked
```

**Integration with RAG Agent** (no changes needed):

```python
# app/agents/rag_agent.py (existing code, no modifications)

# Initialize retriever
retriever = PostgreSQLRetriever(
    db_url=settings.database_url,
    use_reranking=True
)
await retriever.initialize()

# Create graph with closure (same pattern as FAISSRetriever)
graph = create_rag_graph(retriever)
```

**Field Mapping**:

| JSON Field | Database Column | Document Field | Notes |
|-----------|----------------|---------------|-------|
| chunk_text | chunk_text | content | Primary text content |
| chunk_id | chunk_id | id | Unique identifier |
| source_document | source_document | metadata['source_document'] | Origin file |
| chapter_title | chapter_title | metadata['chapter_title'] | Chapter name |
| section_title | section_title | metadata['section_title'] | Section name |
| subsection_title | subsection_title | metadata['subsection_title'] | List of subsections |
| summary | summary | metadata['summary'] | Brief summary |
| token_count | token_count | metadata['token_count'] | Token count |
| - | embedding | (internal) | Not exposed in Document |
| - | - | parent_id | Unused (flat hierarchy) |
| - | - | child_ids | Unused (no hierarchical chunks) |
| - | - | timestamp_start/end | Unused (no video content) |

**Compatibility Checklist**:
- ✅ Implements `DocumentRetriever` abstract class
- ✅ `search()` method returns `List[Document]`
- ✅ `add_documents()` method accepts `List[Document]`
- ✅ Both methods are async (compatible with LangGraph)
- ✅ Document dataclass fields all populated correctly
- ✅ Works with existing closure injection pattern
- ✅ No changes required to RAG agent code

**Alternatives Considered**:
- **Modify Document dataclass**: Would require changing RAG agent; avoided to maintain compatibility
- **Add custom fields**: Could extend metadata dict instead of modifying dataclass
- **Separate reranking class**: Integrated for simplicity; could extract later if needed

---

## Summary of Key Decisions

| Area | Decision | Key Rationale |
|------|----------|---------------|
| **Embedding Model** | Qwen3-Embedding-0.6B via Hugging Face transformers | MPS support, 1024-dim output, 32k context |
| **Batch Size** | 16-32 (adaptive based on RAM) | Balance speed and memory pressure on Apple Silicon |
| **Vector Database** | PostgreSQL 15 + pgvector | Production-ready, HNSW index, cosine similarity |
| **Index Type** | HNSW with cosine distance | Best query performance (~1.5ms), no retraining needed |
| **Python Client** | asyncpg for backend, psycopg2 for indexing | Async compatibility with LangGraph, performance |
| **Connection Pooling** | asyncpg.create_pool (5-20 connections) | Handles concurrent requests efficiently |
| **Reranker** | Qwen3-Reranker-0.6B (top-20 → top-5) | 1-5% quality improvement, <2s reranking time |
| **Docker Setup** | pgvector/pgvector:pg15 official image | Pre-configured, volume persistence, easy setup |
| **Interface** | Drop-in DocumentRetriever replacement | Zero changes to RAG agent, maintains compatibility |

---

## Implementation Checklist

### Phase 1: Database Setup
- [ ] Create `docker-compose.yml` with pgvector/pgvector:pg15
- [ ] Configure environment variables in `.env`
- [ ] Write `init-scripts/01-init-pgvector.sql`
- [ ] Test Docker setup: `docker-compose up -d`
- [ ] Verify extension: `CREATE EXTENSION vector;`

### Phase 2: Indexing Script
- [ ] Install dependencies: `transformers>=4.51.0`, `torch>=2.0.0`, `psycopg2-binary`
- [ ] Implement `Qwen3Embedder` class with MPS support
- [ ] Implement `DatabaseIndexer` class with psycopg2 pooling
- [ ] Add batch processing logic (read JSON → embed → insert)
- [ ] Add duplicate detection (ON CONFLICT DO NOTHING)
- [ ] Add error handling and logging
- [ ] Test with sample data from `02_aripiprazole_chunk_017.json`
- [ ] Create HNSW index AFTER bulk insertion
- [ ] Validate indexing: count rows, check embeddings

### Phase 3: Backend Integration
- [ ] Install `asyncpg` for async PostgreSQL client
- [ ] Implement `PostgreSQLRetriever` class
- [ ] Implement `Qwen3Reranker` class
- [ ] Add connection pool initialization in app startup
- [ ] Update configuration with `DATABASE_URL`
- [ ] Test search without reranking
- [ ] Test search with reranking (top-20 → top-5)
- [ ] Verify Document dataclass mapping
- [ ] Integration test with RAG agent

### Phase 4: Testing & Validation
- [ ] Unit tests for embedding generation
- [ ] Unit tests for database operations
- [ ] Integration tests for full retrieval pipeline
- [ ] Performance benchmarks (query speed, reranking time)
- [ ] Manual testing: "What are common side effects of aripiprazole?"
- [ ] Validate search result relevance (80% accuracy in top 3)
- [ ] Stress test: concurrent queries, memory usage
- [ ] Document troubleshooting guide

---

## References

1. **Qwen3-Embedding Model**: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
2. **Qwen3-Reranker Model**: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
3. **pgvector Documentation**: https://github.com/pgvector/pgvector
4. **PostgreSQL Docker Image**: https://hub.docker.com/_/postgres
5. **asyncpg Documentation**: https://magicstack.github.io/asyncpg/
6. **PyTorch MPS Backend**: https://pytorch.org/docs/stable/notes/mps.html
7. **HNSW Algorithm**: AWS Blog on pgvector indexing techniques
8. **Transformers Library**: https://huggingface.co/docs/transformers/
