# Feature Specification: Multi-Query Expansion and Keyword Matching

**Feature Branch**: `005-multi-query-keyword-search`
**Created**: 2025-11-13
**Status**: Draft
**Input**: User description: "1. Let's allow more queries. And allow AI to write separated queries. For example, if the user query is a comparison between two medications. Then we should probably get two separate queries: (1) first medication and (2) second medication. Let's do it for up to 10 queries (a temporary parameter). 2. Add keyword matching features to DB using available tools (bigram or trigram term matching/sparse vector similarity). This only applies to query rewriting retrieval (user query is in Simplified Chinese and documents are in English). Let's use PostgreSQL's extension for this at the moment."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Query Generation for Complex Comparisons (Priority: P1)

When users ask comparative or multi-faceted questions (e.g., "Compare aripiprazole and risperidone for treating schizophrenia"), the system decomposes the query into multiple focused sub-queries to improve retrieval coverage. Each sub-query targets a specific aspect or entity mentioned in the original question.

**Why this priority**: This is the foundational capability that directly addresses the core user need - getting comprehensive answers to complex queries. Without this, users must manually break down their questions into multiple separate searches.

**Independent Test**: Can be fully tested by submitting a comparative question (e.g., "Compare Drug A and Drug B") and verifying that the system generates separate queries for each drug, executes them independently, and merges the results. Delivers immediate value by providing more comprehensive answers.

**Acceptance Scenarios**:

1. **Given** a user asks "Compare aripiprazole and risperidone for schizophrenia treatment", **When** the system processes the query, **Then** it generates 2-5 separate queries such as: "aripiprazole mechanism schizophrenia", "risperidone mechanism schizophrenia", "aripiprazole side effects", "risperidone side effects", "aripiprazole vs risperidone efficacy"

2. **Given** a user asks a simple single-topic question like "What is aripiprazole?", **When** the system processes the query, **Then** it generates 1-2 focused queries without unnecessary decomposition

3. **Given** the system generates 8 sub-queries from a complex question, **When** all queries are executed, **Then** results are retrieved for each query and merged without duplicates, maintaining relevance ranking

---

### User Story 2 - Query Quality Control and Deduplication (Priority: P2)

The system validates generated queries to ensure quality, removes duplicates, and filters out irrelevant or malformed queries before execution. This prevents wasted database queries and poor-quality results from degrading the overall answer.

**Why this priority**: Without quality control, multi-query generation could produce redundant or low-quality queries that waste resources and confuse results. This is essential for production reliability but can be added after basic generation works.

**Independent Test**: Can be tested by intentionally triggering edge cases (e.g., ambiguous input, repeated terms) and verifying that duplicate or malformed queries are filtered out before database execution. Delivers value by improving result quality and reducing unnecessary database load.

**Acceptance Scenarios**:

1. **Given** the query generator produces 2 identical queries, **When** the deduplication step runs, **Then** only one query is retained

2. **Given** the query generator produces a malformed query (empty string, only punctuation, etc.), **When** validation runs, **Then** the malformed query is filtered out and not executed

3. **Given** the query generator produces 10 sub-queries, **When** ranking by relevance, **Then** queries are ordered by semantic similarity to the original question, with the top 10 (or configured limit) retained

---

### User Story 3 - Hybrid Keyword+Vector Search with pg_trgm (Priority: P3)

For queries that contain specific medical terms, drug names, or technical vocabulary, the system uses PostgreSQL's pg_trgm extension to perform trigram-based lexical matching alongside vector semantic search. This catches exact or near-exact term matches that pure semantic search might miss.

**Why this priority**: Keyword matching adds robustness for term-specific queries but is not essential for the basic multi-query feature to work. It enhances retrieval quality but can be layered in after core functionality is stable.

**Independent Test**: Can be tested by submitting a query with a specific drug name (e.g., "阿立哌唑副作用" - aripiprazole side effects in Chinese) and verifying that documents containing the English term "aripiprazole" are retrieved even if semantic similarity is moderate. Delivers value by improving recall for terminology-heavy queries.

**Acceptance Scenarios**:

1. **Given** pg_trgm extension is enabled and trigram indexes exist on the `content` column, **When** a user queries with a specific drug name, **Then** documents containing that exact term or close variants (typos, abbreviations) are retrieved with high keyword scores

2. **Given** a query returns 20 results from vector search and 15 results from keyword search (with 5 overlapping), **When** the deduplication step runs, **Then** 30 unique candidate documents are collected and passed to the reranker, which produces a final ranked list of top-5 results

3. **Given** a user submits a query in Simplified Chinese, **When** LLM query expansion runs, **Then** the LLM translates the Chinese query to multiple English queries, which are then used for both vector and keyword retrieval against the English document corpus

---

### User Story 4 - Cross-Language Query Handling (Priority: P4)

For the specific use case of Simplified Chinese user queries against English medical documents, the LLM query expansion step handles translation, preserving medical terminology and technical terms accurately while converting Chinese text to English search queries.

**Why this priority**: This is a specialized enhancement for the Chinese→English use case. It provides incremental value but is not required for the core multi-query or keyword matching features to function. The LLM's built-in translation capabilities handle most cases, so this is about optimizing prompt engineering rather than adding new infrastructure.

**Independent Test**: Can be tested by submitting Chinese medical queries and verifying that the LLM generates accurate English queries with correct medical terminology, which then successfully retrieve relevant English documents. Delivers value by improving cross-language recall through better query translation.

**Acceptance Scenarios**:

1. **Given** a user queries "阿立哌唑的作用机制" (aripiprazole mechanism of action), **When** LLM query expansion runs, **Then** the LLM generates English queries such as "aripiprazole mechanism of action", "how aripiprazole works", "aripiprazole pharmacology", preserving the drug name accurately

2. **Given** a Chinese query contains a drug name with multiple English spellings (e.g., "利培酮" for risperidone), **When** the LLM translates it, **Then** the LLM uses the standard English spelling "risperidone" in generated queries

3. **Given** a query contains mixed Chinese and Latin characters (e.g., "5-HT2A受体阻断" - 5-HT2A receptor blockade), **When** the LLM processes it, **Then** the Latin portion ("5-HT2A") is preserved exactly while the Chinese portion is translated to "receptor blockade" or similar English terms

---

### Edge Cases

- **What happens when query generation produces 0 valid queries?** System should fall back to using the original user query directly
- **How does the system handle queries that generate >10 sub-queries?** Rank queries by relevance and keep only top 10 (configurable limit)
- **What if keyword matching returns 0 results but vector search returns many?** Hybrid search should gracefully degrade to vector-only results with appropriate logging
- **How are duplicate results from multiple queries handled?** Deduplicate by document chunk ID, keeping the highest-scoring occurrence
- **What if pg_trgm indexes are missing or extension is not enabled?** System should detect this at startup and either fail-fast with clear error or fall back to vector-only search with warning logs
- **How does the system handle extremely long user queries (>1000 characters)?** Truncate or summarize input before query generation to stay within LLM token limits
- **What if all generated queries fail validation?** Fall back to original user query as single query
- **How are query execution failures handled (timeout, database error)?** Skip failed queries, log errors, and continue with successful queries. If all queries fail, return error to user with clear message

## Requirements *(mandatory)*

### Functional Requirements

**Multi-Query Generation**:
- **FR-001**: System MUST generate between 1 and 10 sub-queries from a single user input query, with the exact count determined by query complexity and decomposability
- **FR-002**: System MUST output queries as a newline-separated list (one query per line), truncating to 10 queries if LLM generates more
- **FR-003**: System MUST execute all generated sub-queries in parallel to minimize total latency
- **FR-004**: System MUST merge and deduplicate results from multiple queries before passing to reranker
- **FR-005**: System MUST support a configurable maximum query count parameter (default: 10) that can be adjusted without code changes
- **FR-006**: System MUST use an LLM-based query decomposition prompt that employs a balanced strategy: generating both breadth (different aspects/entities) and depth (query variations) to maximize retrieval coverage
- **FR-007**: System MUST leverage persona simulation in query generation (e.g., generating queries from patient perspective, clinician perspective, pharmacist perspective) to diversify query formulations

**Query Quality Control**:
- **FR-008**: System MUST validate each generated query to ensure it is non-empty, contains meaningful content (not just punctuation/whitespace), and is relevant to the original question
- **FR-009**: System MUST detect and remove duplicate queries (exact string match or high semantic similarity >0.95) before execution
- **FR-010**: System MUST rank generated queries by semantic similarity to the original user question, executing only the top N queries (where N ≤ configured max)

**Hybrid Retrieval Pipeline with pg_trgm**:
- **FR-011**: System MUST enable the PostgreSQL pg_trgm extension (v1.6 or higher) on the vector_chunks table
- **FR-012**: System MUST create GIN trigram indexes on the `content` column of vector_chunks table to enable fast trigram similarity queries
- **FR-013**: System MUST implement a 5-step hybrid retrieval pipeline: (1) Query expansion via LLM, (2) Vector embedding retrieval using pgvector, (3) Keyword retrieval using pg_trgm, (4) Deduplication by document chunk ID, (5) Reranking to select top-N results
- **FR-014**: System MUST retrieve results independently from both vector search (pgvector) and keyword search (pg_trgm), collecting all candidate documents before deduplication
- **FR-015**: System MUST pass all deduplicated candidate documents (from both retrieval methods) to a reranker model, which produces final ranked results based on relevance to the original query

**Cross-Language Query Expansion**:
- **FR-016**: System MUST use the LLM query expansion step to handle Chinese→English translation, where Simplified Chinese user queries are converted to English search queries by the LLM
- **FR-017**: System MUST ensure that LLM-generated English queries preserve medical terminology, drug names, and technical terms accurately when translating from Chinese input
- **FR-018**: System MUST handle mixed-language queries (Chinese + Latin characters like "5-HT2A受体") by instructing the LLM to preserve Latin/English terms exactly while translating Chinese portions

**Error Handling and Fallbacks**:
- **FR-019**: System MUST fall back to using the original user query (translated to English by LLM) if query generation produces zero valid queries
- **FR-020**: System MUST log query generation failures, validation failures, and execution errors with sufficient detail for debugging
- **FR-021**: System MUST degrade gracefully to vector-only search if pg_trgm extension or indexes are unavailable, with appropriate warning logs

### Key Entities

- **Query**: A single English search query string generated from user input
  - Attributes: query_text (string), source ("original" | "generated"), rank (integer 1-10), similarity_to_original (float 0-1)
  - Format: Newline-separated plain text output from LLM (no key-value pairs)

- **QuerySet**: Collection of 1-10 Query objects generated from a single user input
  - Attributes: original_query (string, may be Chinese), generated_queries (list of Query), generation_timestamp (datetime), total_generated (integer), total_after_deduplication (integer)

- **SearchResult**: Retrieved document chunk with retrieval metadata
  - Attributes: chunk_id, content, metadata, vector_score (float 0-1 or null), keyword_score (float 0-1 or null), reranker_score (float 0-1), source_query (Query reference), retrieval_method ("vector" | "keyword" | "both")

- **TrigramIndex**: PostgreSQL GIN index on text columns for trigram-based similarity matching
  - Attributes: table_name, column_name, index_name, creation_timestamp, index_size_mb

- **RetrievalPipeline**: Orchestrates the 5-step hybrid retrieval process
  - Steps: query_expansion → vector_retrieval → keyword_retrieval → deduplication → reranking
  - Attributes: pipeline_id, start_time, end_time, queries_generated (integer), candidates_retrieved (integer), candidates_after_dedup (integer), final_results (integer)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Multi-query generation improves answer accuracy by ≥30% for comparative queries (measured by human eval on 100-query test set comparing single-query vs multi-query results)

- **SC-002**: Query generation and validation completes in <500ms for generating up to 10 queries (measured at 95th percentile latency)

- **SC-003**: Hybrid retrieval pipeline (vector + keyword + reranking) improves recall by ≥25% for term-specific queries (e.g., drug names, medical procedures) compared to vector-only search (measured on 100-query test set with known ground truth)

- **SC-004**: End-to-end retrieval pipeline (query expansion → dual retrieval → deduplication → reranking) maintains total latency <3 seconds for returning top-5 final results (measured at 95th percentile)

- **SC-005**: LLM-based query expansion accurately translates ≥90% of Chinese medical queries into semantically equivalent English queries, as validated by bilingual medical expert review on 50-query test set

- **SC-006**: Query deduplication reduces redundant database queries by ≥40% when query generation produces similar sub-queries (measured by comparing pre-deduplication vs post-deduplication query counts)

- **SC-007**: Reranker successfully identifies and promotes the most relevant documents, achieving ≥80% user satisfaction with top-5 results (measured through user feedback or click-through rate)

## Assumptions

1. **Database Performance**: PostgreSQL instance has sufficient resources (CPU, memory, disk I/O) to handle increased query load from multi-query execution and parallel vector+keyword retrieval
2. **LLM Capabilities**: Query expansion LLM (assumed GPT-4 or similar) can accurately translate Chinese medical queries to English and generate diverse query variations with acceptable latency (<2s) and cost
3. **Reranker Availability**: A reranker model (e.g., Qwen3-Reranker-0.6B or similar) is available and can process 20-50 candidate documents efficiently (<1s)
4. **Embedding Model Consistency**: Vector embeddings for semantic search are already generated and indexed for all document chunks
5. **User Query Length**: Typical user queries are <500 characters; extremely long queries (>1000 chars) are rare edge cases
6. **Document Language**: Medical document corpus is primarily in English; LLM query expansion converts all non-English queries to English before retrieval
7. **PostgreSQL Version**: Database is PostgreSQL 15+ with pgvector 0.8.0+ already installed and configured
8. **Index Maintenance**: Trigram indexes are maintained automatically by PostgreSQL; no custom index rebuild logic is required initially
9. **Output Format**: LLM can reliably produce newline-separated query lists without requiring complex parsing of structured output (no JSON/key-value pairs needed)

