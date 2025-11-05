# Feature Specification: Semantic Search with PostgreSQL and pgvector

**Feature Branch**: `002-semantic-search`
**Created**: 2025-11-02
**Status**: Draft
**Input**: User description: "I have chunked data in data/chunking_final I would like to index them using semantic representation (https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) note that I am on apple mps machine (so please support this). The computing embedding and indexing should be a separated script. We will not inject the data on the fly or when start the backend service. I provide a sample data in 02_aripiprazole_chunk_017.json all the data is in the same format. All the data is important we need to include them in the database. For semantic representation, we need the 'chunk_text'. I am thinking about using postreSQL (?) with pgvector for this purpose. And the goal is to put this into our existing chat backend (langgraph) service. Please carefully think about this and let me know the goal. In the production env, the database will be managed externally so we should mock this by setting a separated docker for the database. Create this part of the script in a separated folder. In the backend, let's disable the bm25 for now but we will have that later I just want to test the semantic representation first. The reranker let's also use Qwen3's reranker for it."

## User Scenarios & Testing

### User Story 1 - Index All Chunked Documents (Priority: P1)

As a system administrator, I need to index all existing chunked medical documents from `data/chunking_final` into the vector database, so that the chat backend can perform semantic search over this content.

**Why this priority**: This is the foundation for all semantic search functionality. Without indexed documents, no search can occur. This represents the core data ingestion pipeline.

**Independent Test**: Can be fully tested by running the indexing script against the data directory and verifying all chunks are stored in PostgreSQL with their embeddings. Success is measured by comparing the count of JSON files in `data/chunking_final` to the count of records in the database.

**Acceptance Scenarios**:

1. **Given** a directory containing 500+ chunked JSON files, **When** the indexing script runs, **Then** all chunks are successfully embedded and stored in PostgreSQL with metadata
2. **Given** the indexing process encounters a file with missing or invalid `chunk_text`, **When** processing that file, **Then** the error is logged and processing continues with remaining files
3. **Given** the indexing script is run a second time, **When** it encounters already-indexed chunks, **Then** it skips duplicates without re-embedding them
4. **Given** the indexing script completes, **When** checking the database, **Then** all metadata fields (chunk_id, source_document, chapter_title, section_title, summary, token_count) are correctly populated

---

### User Story 2 - Query with Semantic Search (Priority: P1)

As a chat backend user, I want to query the system with natural language questions and receive semantically relevant document chunks, so that I can get accurate answers grounded in the medical documentation.

**Why this priority**: This is the primary user-facing value of the system. Without semantic search, the indexed data provides no benefit to end users.

**Independent Test**: Can be fully tested by sending a natural language query to the chat backend and verifying that returned chunks are semantically relevant to the query. For example, query "side effects of aripiprazole" should return chunks from the aripiprazole document discussing side effects.

**Acceptance Scenarios**:

1. **Given** the database contains indexed medical chunks, **When** a user asks "What are common side effects of aripiprazole?", **Then** the system returns chunks specifically discussing aripiprazole side effects
2. **Given** a user query that matches multiple documents, **When** semantic search executes, **Then** results are ranked by semantic similarity and the top 5 most relevant chunks are returned
3. **Given** a user query in plain language, **When** the query is processed, **Then** the system converts it to embeddings using the same Qwen3-Embedding-0.6B model used for indexing
4. **Given** search results are returned, **When** the user reviews them, **Then** each result includes the chunk text, source document name, and relevant metadata (chapter, section)

---

### User Story 3 - Rerank Search Results (Priority: P2)

As a chat backend user, I want the most relevant search results to appear first, so that I don't have to read through less relevant information to find what I need.

**Why this priority**: Reranking improves result quality but is not essential for basic functionality. Users can still get value from semantic search alone, though reranking enhances the experience.

**Independent Test**: Can be fully tested by comparing search results before and after reranking. Given the same query, the reranked results should show measurably better relevance scores and user satisfaction.

**Acceptance Scenarios**:

1. **Given** semantic search returns 20 candidate chunks, **When** the reranker processes them, **Then** the top 5 chunks shown to the user have higher relevance scores than those ranked 6-20
2. **Given** a query like "medication dosage for children", **When** reranking occurs, **Then** chunks specifically discussing pediatric dosing appear before general dosing information
3. **Given** the reranker is processing results, **When** using Qwen3 reranker model, **Then** reranking completes in under 2 seconds for typical queries

---

### User Story 4 - Local Development Setup (Priority: P2)

As a developer, I need to set up the vector database locally using Docker, so that I can develop and test the semantic search system without requiring external database infrastructure.

**Why this priority**: This enables local development but is not required for production deployment (where the database is externally managed). Essential for development velocity.

**Independent Test**: Can be fully tested by running the Docker setup script and verifying the PostgreSQL + pgvector database is accessible and ready to accept connections.

**Acceptance Scenarios**:

1. **Given** a clean development machine with Docker installed, **When** the database setup script runs, **Then** a PostgreSQL container with pgvector extension is running and accessible
2. **Given** the Docker database is running, **When** the indexing script executes, **Then** it successfully connects and stores embeddings
3. **Given** the database container is stopped, **When** it is restarted, **Then** all indexed data persists and remains queryable

---

### Edge Cases

- What happens when the embedding model encounters text longer than its maximum token limit (32k tokens for Qwen3-Embedding-0.6B, though documents typically only 1k tokens)?
- How does the system handle network failures or API timeouts when generating embeddings?
- What happens if a chunk JSON file is corrupted or missing required fields like `chunk_text`?
- How does the indexing script handle very large directories (10,000+ files)?
- What happens when the PostgreSQL database runs out of disk space during indexing?
- How does the system handle queries that have no semantically similar results in the database?
- What happens if the embedding model fails to load on Apple MPS due to memory constraints?
- How does the system maintain compatibility with the existing DocumentRetriever interface?

## Existing Architecture

The project currently has a medication RAG chat backend built with LangGraph (`app/agents/rag_agent.py`). Key components:

- **RAG Agent**: Uses `search_medical_docs` tool to query medical knowledge base
- **DocumentRetriever Interface** (`app/core/retriever.py`): Abstract base class with `search()` and `add_documents()` methods
- **Current Implementation**: `FAISSRetriever` using sentence-transformers/all-MiniLM-L6-v2 with in-memory FAISS
- **Document Model**: Dataclass with content, metadata, id, parent_id, child_ids, timestamps
- **Integration Pattern**: Retriever injected into agent via closure to avoid serialization issues with LangGraph checkpointing

**This feature replaces**:
- `FAISSRetriever` → `PostgreSQLRetriever` (drop-in replacement implementing DocumentRetriever interface)
- `sentence-transformers/all-MiniLM-L6-v2` → `Qwen3-Embedding-0.6B`
- Simple similarity search → Semantic search with reranking (Qwen3-Reranker-0.6B)

**Interface Compatibility**: The new `PostgreSQLRetriever` MUST implement the same `DocumentRetriever` interface so it can be swapped in without modifying the RAG agent code.

## Requirements

### Functional Requirements

- **FR-001**: System MUST generate embeddings for all chunk files in `data/chunking_final` using Qwen3-Embedding-0.6B model
- **FR-002**: System MUST support Apple MPS (Metal Performance Shaders) acceleration for embedding generation
- **FR-003**: System MUST store embeddings in PostgreSQL database with pgvector extension
- **FR-004**: Indexing process MUST be a separate standalone script (not part of backend startup)
- **FR-005**: System MUST extract and embed the `chunk_text` field from each JSON chunk file
- **FR-006**: System MUST store chunk metadata alongside embeddings: chunk_id, source_document, chapter_title, section_title, subsection_title (list), summary, token_count
- **FR-007**: Chat backend MUST query the vector database using semantic similarity search
- **FR-008**: System MUST use Qwen3 reranker model to improve result relevance
- **FR-009**: System MUST provide Docker-based PostgreSQL setup for local development
- **FR-010**: Production deployment MUST support externally managed PostgreSQL database
- **FR-011**: System MUST handle embedding generation failures gracefully (log and continue)
- **FR-012**: System MUST avoid re-indexing chunks that already exist in the database
- **FR-013**: Chat backend MUST NOT use BM25 search (disabled for initial testing)
- **FR-014**: System MUST return search results ranked by semantic similarity score
- **FR-015**: Indexing script MUST process all JSON files in nested subdirectories (medications, chapters, videos)
- **FR-016**: PostgreSQLRetriever MUST implement the DocumentRetriever interface with `search()` and `add_documents()` methods
- **FR-017**: PostgreSQLRetriever MUST be compatible with existing Document dataclass (content, metadata, id, parent_id, child_ids, timestamps)

### Key Entities

- **Chunk**: Represents a single document chunk with text content, metadata, and vector embedding
  - Attributes: chunk_id (unique identifier), chunk_text (content for embedding), source_document (origin file), metadata (chapter, section, summary), embedding (vector representation), token_count
  - Relationships: Each chunk belongs to one source document; embeddings enable similarity comparisons between chunks

- **Embedding**: Vector representation of chunk text generated by Qwen3-Embedding-0.6B model
  - Attributes: vector (float array), dimension (model-specific, typically 768 or 1024), model_version (Qwen3-Embedding-0.6B)
  - Relationships: One-to-one with Chunk; used for similarity search via pgvector

- **Query**: User's natural language search input
  - Attributes: query_text (user input), query_embedding (vector form), timestamp
  - Relationships: Compared against all chunk embeddings to find semantic matches

- **Search Result**: Chunk returned as relevant to a query
  - Attributes: chunk (reference to Chunk entity), similarity_score (cosine similarity or distance metric), rerank_score (from reranker model), rank (position in results)
  - Relationships: Links Query to relevant Chunks with relevance scores

## Success Criteria

### Measurable Outcomes

- **SC-001**: All chunks in `data/chunking_final` (500+ files) are successfully indexed with embeddings in under 30 minutes
- **SC-002**: Semantic search queries return top 5 results in under 3 seconds (including embedding generation and database query)
- **SC-003**: Reranking of search results completes in under 2 seconds for typical queries (20 candidates → 5 results)
- **SC-004**: System successfully runs on Apple Silicon (M1/M2/M3) with MPS acceleration for embedding generation
- **SC-005**: Developers can set up local PostgreSQL + pgvector environment in under 5 minutes using provided Docker script
- **SC-006**: Search result relevance: 80% of test queries return at least one highly relevant chunk (manual evaluation) in top 3 results
- **SC-007**: Indexing script handles errors gracefully: processes 95%+ of chunks successfully even if individual files fail
- **SC-008**: Database stores embeddings efficiently: total storage size is under 2GB for 500 chunks with metadata
- **SC-009**: Re-running indexing script on already-indexed data completes in under 1 minute (skips existing chunks)

## Assumptions

- Qwen3-Embedding-0.6B model produces embeddings compatible with pgvector storage (standard float vector format)
- Qwen3-Embedding-0.6B context length is 32k tokens, sufficient for all documents (typically 1k tokens)
- All chunk JSON files follow the same schema as `02_aripiprazole_chunk_017.json`
- PostgreSQL database can be accessed via standard connection string (host, port, database, user, password)
- Apple MPS is available and functional on the development machine (requires macOS 12.3+)
- The existing RAG agent (`app/agents/rag_agent.py`) uses DocumentRetriever interface and doesn't need modification
- RAG agent's closure pattern for injecting retriever remains compatible with PostgreSQLRetriever
- Vector search using cosine similarity is sufficient for initial semantic search (other metrics like L2 distance can be explored later)
- Qwen3 reranker model accepts text pairs (query, chunk) and returns relevance scores
- BM25 integration is deferred to a future iteration (not part of this feature scope)
- The `chunk_text` field contains the primary content for embedding (contextual_prefix is excluded from initial testing)
- Docker is available on development machines for local database setup
- FAISSRetriever can be deprecated or kept as fallback option

## Dependencies

- Qwen3-Embedding-0.6B model from Hugging Face (https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) - replaces sentence-transformers/all-MiniLM-L6-v2
- Qwen3-Reranker-0.6B model from Hugging Face (https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- PostgreSQL 15+ with pgvector extension (for vector similarity search)
- Python libraries: transformers, torch, psycopg2 (or asyncpg), sentence-transformers (or equivalent)
- Docker and Docker Compose for local development environment
- Existing LangGraph chat backend infrastructure:
  - `app/agents/rag_agent.py` - RAG agent with search_medical_docs tool
  - `app/core/retriever.py` - DocumentRetriever interface and Document dataclass
  - `app/graph/state.py` - MedicalChatState
  - `app/config.py` - Settings for top_k_documents

## Out of Scope

- BM25 hybrid search (deferred to future iteration)
- Real-time indexing of new chunks (batch indexing only)
- Embedding model fine-tuning or customization
- Multi-language support (assumes English medical text)
- Advanced pgvector indexing strategies (HNSW, IVFFlat) - will use default vector search initially
- Query expansion or synonym handling
- User authentication or access control for database
- Frontend UI for search testing (assumes backend API only)
- Monitoring and observability for production deployment
- Backup and disaster recovery for vector database
