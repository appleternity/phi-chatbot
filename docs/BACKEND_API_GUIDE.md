# Backend API Guide

> **Comprehensive Developer Guide to Backend Functions and Architecture**

## Table of Contents

1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Configuration System](#configuration-system)
4. [Agent System](#agent-system)
5. [Retrieval Systems](#retrieval-systems)
6. [State Management](#state-management)
7. [Graph Orchestration](#graph-orchestration)
8. [Data Models](#data-models)
9. [System Prompts](#system-prompts)
10. [Data Flow](#data-flow)
11. [Key Architectural Patterns](#key-architectural-patterns)
12. [Deployment Guide](#deployment-guide)

---

## Overview

### System Architecture

This is a **multi-agent medical chatbot** built with LangGraph that intelligently routes user queries to specialized agents:

- **Emotional Support Agent**: Empathetic listening and emotional validation
- **RAG Agent**: Medical information retrieval with knowledge base search
- **Parenting Agent**: Expert child development advice using advanced RAG

**Key Features**:
- Session-aware conversation memory
- Hybrid vector + keyword search
- Cross-encoder reranking for precision
- Hierarchical document chunking for video transcripts
- Graceful degradation when optional components unavailable

**Technology Stack**:
- **Framework**: LangGraph, LangChain, FastAPI
- **LLM**: OpenRouter API (qwen/qwen3-max)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **Vector Search**: FAISS
- **Keyword Search**: BM25
- **Reranking**: Cross-encoder/ms-marco-MiniLM-L-6-v2

---

## API Endpoints

**File**: `app/main.py`

### Health Check Endpoint

```python
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        HealthResponse: {"status": "healthy", "version": "0.1.0"}

    Performance: ~1ms (no I/O)
    """
```

### Chat Endpoint

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_store: Annotated[SessionStore, Depends(get_session_store)]
) -> ChatResponse:
    """
    Main chat interface handling user messages.

    Args:
        request: ChatRequest with session_id and message
        session_store: Injected session storage dependency

    Returns:
        ChatResponse with agent response and metadata

    Process:
        1. Load or create session from session_store
        2. Construct MedicalChatState with message + session metadata
        3. Invoke LangGraph with thread_id for conversation memory
        4. Extract response from last message in result
        5. Update session with assigned_agent and metadata
        6. Return ChatResponse

    Performance: 2-20s depending on agent and complexity
    """
```

**Request Model**:
```python
class ChatRequest(BaseModel):
    session_id: str          # Unique session identifier
    message: str             # User message (min_length=1)
```

**Response Model**:
```python
class ChatResponse(BaseModel):
    session_id: str          # Echo of request session_id
    message: str             # Agent response
    agent: str               # "supervisor", "emotional_support", "rag_agent", "parenting"
    metadata: Optional[dict] # Classification details, sources, etc.
```

### Application Lifecycle

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler - initializes components on startup.

    Startup Flow:
        1. Initialize InMemorySessionStore with configurable TTL
        2. Load medical embeddings (REQUIRED - fail-fast if missing)
        3. Load parenting embeddings (OPTIONAL - graceful degradation)
        4. Build LangGraph with all available agents
        5. Log successful startup

    Cleanup:
        - Context manager cleanup on shutdown
    """
```

**Helper Functions**:

| Function | Purpose | Behavior |
|----------|---------|----------|
| `_initialize_session_store()` | Creates session storage | In-memory with TTL |
| `_load_medical_retriever()` | Loads medical knowledge base | Fail-fast if not found |
| `_load_parenting_system()` | Loads parenting knowledge base | Graceful degradation |

---

## Configuration System

**File**: `app/config.py`

### Settings Class

```python
class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Attributes:
        # LLM Configuration
        openai_api_base: str              # OpenRouter API endpoint
        openai_api_key: str               # API key (required)
        model_name: str                   # "qwen/qwen3-max" (default)

        # Application Settings
        log_level: str                    # "INFO", "DEBUG", "WARNING", etc.
        session_ttl_seconds: int          # Session expiration (default: 3600)
        environment: str                  # "development", "production"

        # Embedding Configuration
        embedding_model: str              # Embedding model name
        embedding_dim: int                # Embedding dimensions (384)

        # Persistence Paths
        index_path: str                   # Medical embeddings path
        parenting_index_path: str         # Parenting embeddings path

        # Retrieval Settings
        top_k_documents: int              # Documents to retrieve (default: 3)

    Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    """
```

**Usage**:
```python
from app.config import settings

# Access configuration
api_key = settings.openai_api_key
model = settings.model_name
```

**Required Environment Variables**:
```bash
OPENAI_API_KEY=your-openrouter-api-key
OPENAI_API_BASE=https://openrouter.ai/api/v1
```

**Optional Environment Variables**:
```bash
MODEL_NAME=qwen/qwen3-max
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
TOP_K_DOCUMENTS=3
```

---

## Agent System

### Base Agent Utilities

**File**: `app/agents/base.py`

#### LLM Factory Function

```python
def create_llm(temperature: float = 0.7) -> BaseChatModel:
    """
    Factory for creating LLM instances with environment-aware behavior.

    Args:
        temperature: Response randomness [0.0=deterministic, 1.0=creative]

    Returns:
        BaseChatModel instance (FakeChatModel for tests, ChatOpenAI for production)

    Behavior:
        Test Mode (TESTING=true):
            - Returns FakeChatModel (deterministic responses)
            - 50-100x faster execution
            - No API costs

        Production Mode:
            - Returns ChatOpenAI with OpenRouter configuration
            - Real LLM inference
            - API costs apply

    Usage:
        llm = create_llm(temperature=0.1)  # Deterministic
        llm = create_llm(temperature=1.0)  # Creative
    """
```

---

### Supervisor Agent

**File**: `app/agents/supervisor.py`

#### Purpose

Routes initial user messages to the most appropriate agent using LLM-based intent classification.

#### Data Structure

```python
class AgentClassification(BaseModel):
    """
    Structured output from supervisor classification.

    Attributes:
        agent: One of ["emotional_support", "rag_agent", "parenting"]
        reasoning: Explanation for classification decision
        confidence: Score [0.0, 1.0] indicating classification certainty
    """
```

#### Node Function

```python
def supervisor_node(state: MedicalChatState) -> Command[Literal["emotional_support", "rag_agent", "parenting"]]:
    """
    Classifies user intent and routes to appropriate agent.

    Args:
        state: MedicalChatState containing conversation messages

    Returns:
        Command with goto=<agent_name> and updated metadata

    Process:
        1. Extract last user message from state
        2. Invoke LLM with SUPERVISOR_PROMPT for classification
        3. Parse structured output (agent, reasoning, confidence)
        4. Log classification decision
        5. Return Command routing to assigned agent

    LLM Configuration:
        - Temperature: 0.1 (deterministic classification)
        - Structured output: with_structured_output(AgentClassification)

    Execution Context:
        - Runs ONLY on first message in session
        - Subsequent messages route directly to assigned_agent

    Performance: ~500-1000ms
    """
```

**Example Flow**:
```
User: "I'm feeling anxious about my medication"
  ↓ supervisor_node
  ↓ LLM classification
Agent: "emotional_support"
Reasoning: "User expressing emotional distress"
Confidence: 0.85
```

---

### Emotional Support Agent

**File**: `app/agents/emotional_support.py`

#### Purpose

Provides empathetic, non-clinical emotional support and active listening without knowledge base retrieval.

#### Node Function

```python
def emotional_support_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    Generates empathetic response for emotional support.

    Args:
        state: MedicalChatState with conversation history

    Returns:
        Command with agent response and goto=END

    Process:
        1. Construct messages with EMOTIONAL_SUPPORT_PROMPT as system message
        2. Invoke LLM with high temperature for natural responses
        3. Wrap response in AIMessage
        4. Return Command terminating conversation turn

    LLM Configuration:
        - Temperature: 1.0 (creative, varied, natural responses)
        - No tools (direct generation)

    Guidelines:
        - Active listening and empathy
        - No medical advice
        - Crisis resource referrals when appropriate
        - Encourage professional help for serious concerns

    Performance: ~2-5s
    """
```

---

### RAG Agent (Medical Information)

**File**: `app/agents/rag_agent.py`

#### Purpose

Answers medical questions using retrieval-augmented generation with knowledge base search.

#### Tool Definition

```python
@tool
async def search_medical_docs(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """
    Searches medical knowledge base for medication/treatment information.

    Args:
        query: Search query (medication name, condition, treatment, etc.)
        state: Injected state containing retriever instance

    Returns:
        Formatted string of retrieved documents with metadata

    Process:
        1. Extract retriever from injected state
        2. Execute async search for top_k documents
        3. Format documents with metadata:
           - Document name/title
           - Content text
           - Source information
        4. Return formatted string for LLM context

    Usage by Agent:
        Agent decides when to call this tool based on user query
        Tool results injected into LLM context for answer synthesis

    Performance: ~100-300ms (FAISS search)
    """
```

#### Agent Creation

```python
def create_rag_agent(retriever: DocumentRetriever):
    """
    Creates ReAct agent with search_medical_docs tool binding.

    Args:
        retriever: FAISSRetriever instance for medical knowledge base

    Returns:
        Compiled ReAct agent

    Critical Design Decision: checkpointer=False
        - RAG agent is stateless (inner graph)
        - Outer graph (main chatbot) handles conversation persistence
        - Prevents serialization errors with non-serializable retriever

    Architecture:
        - ReAct pattern: Reasoning + Acting
        - Agent decides when to use search tool
        - Synthesizes answer from retrieved documents

    Configuration:
        - Temperature: 1.0 (natural language generation)
        - System prompt: RAG_AGENT_PROMPT
        - Tools: [search_medical_docs]
    """
```

#### Node Function

```python
def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    Wrapper that invokes RAG agent with retriever injection.

    Args:
        state: MedicalChatState containing rag_agent and retriever

    Returns:
        Command with agent response messages

    Process:
        1. Extract rag_agent from state (captured via closure)
        2. Extract retriever from state (captured via closure)
        3. Create temporary state_with_retriever for tool injection
        4. Invoke agent with injected state
        5. Extract response messages
        6. Return Command(goto=END, update={"messages": response})

    Pattern: Closure-based dependency injection
        - Non-serializable objects (agent, retriever) in closure
        - Only serializable state gets checkpointed

    Performance: ~3-8s (retrieval + LLM synthesis)
    """
```

**Example Flow**:
```
User: "What are the side effects of metformin?"
  ↓ rag_agent_node
  ↓ Agent decision: Need to search
  ↓ search_medical_docs("metformin side effects")
  ↓ Retrieved 3 documents about metformin
  ↓ LLM synthesizes answer with citations
Response: "Metformin commonly causes gastrointestinal side effects..."
```

---

### Parenting Agent (Advanced RAG)

**File**: `app/agents/parenting_agent.py`

#### Purpose

Provides expert parenting advice using multi-step retrieval-augmented generation with quality checks and corrective mechanisms.

#### Architecture

```
START
  ↓
agent_decision (LLM decides: retrieve or answer?)
  ├─ has_tool_calls → tools (execute search)
  │                    ↓
  │                  grade_documents (filter by relevance)
  │                    ↓
  │                  check_quality (assess retrieval)
  │                    ├─ good → generate_answer
  │                    └─ poor → rewrite_query → agent_decision (retry, max 2)
  │
  └─ no_tool_calls → generate_answer (direct answer)

generate_answer
  ↓
confidence_check
  ├─ high (≥0.6) → END
  └─ low → insufficient_info → END
```

#### State Definition

**File**: `app/graph/parenting_state.py`

```python
class ParentingRAGState(MessagesState):
    """
    State for multi-step parenting RAG agent.

    Query Processing:
        question: str                      # Original user question
        queries: List[str]                 # Multi-query variations (future use)

    Retrieval:
        documents: List[Document]          # Raw search results
        filtered_documents: List[Document] # Post-grading documents

    Generation:
        generation: str                    # Final response text

    Control Flow:
        retrieval_attempts: int            # Current attempt (max 3)
        should_rewrite: bool               # Flag for query rewriting

    Quality Metrics:
        relevance_scores: List[float]      # Per-document scores [0.0-1.0]
        confidence: float                  # Overall confidence [0.0-1.0]

    Metadata:
        sources: List[dict]                # Citation information
        user_context: dict                 # Child age, preferences, history
    """
```

#### Node Functions

**1. Agent Decision Node**

```python
def agent_decision_node(state: ParentingRAGState) -> dict:
    """
    LLM decides whether to retrieve documents or answer directly.

    Args:
        state: ParentingRAGState with current question

    Returns:
        Dict with updated messages (potentially includes tool calls)

    Process:
        1. Extract question from state
        2. Invoke LLM with tool binding (search_parenting_knowledge)
        3. LLM decides:
           - Call search tool if knowledge needed
           - Answer directly if question answerable without retrieval
        4. Return messages (with or without tool calls)

    Configuration:
        - Temperature: 0.3 (balanced reasoning)
        - Tool choice: "auto" (LLM decides)
    """
```

**2. Tools Node**

```python
def tools_node_factory(retriever, reranker):
    """
    Creates tool execution node with dependency injection.

    Args:
        retriever: HybridRetriever instance
        reranker: CrossEncoderReranker instance

    Returns:
        Node function that executes search_parenting_knowledge tool

    Process:
        1. Extract tool calls from messages
        2. Inject retriever and reranker into state
        3. Execute tool (performs hybrid search + reranking)
        4. Store documents in state for downstream grading
        5. Return tool messages with formatted results
    """
```

**3. Grade Documents Node**

```python
def grade_documents_node(state: ParentingRAGState) -> dict:
    """
    Filters retrieved documents by relevance using LLM grading.

    Args:
        state: ParentingRAGState with documents from retrieval

    Returns:
        Dict with filtered_documents and relevance_scores

    Process:
        1. For each document:
           a. Create (question, document) pair
           b. Invoke LLM for relevance grading
           c. Parse structured output (score, reasoning, relevant)
        2. Filter documents where score >= 0.5
        3. Store filtered_documents and relevance_scores in state

    LLM Configuration:
        - Temperature: 0.1 (deterministic grading)
        - Structured output: RelevanceGrade model

    Performance: ~200ms per document
    """
```

**4. Check Quality Node**

```python
def check_quality_node(state: ParentingRAGState) -> dict:
    """
    Assesses retrieval quality and decides next action.

    Args:
        state: ParentingRAGState with filtered_documents and scores

    Returns:
        Dict with should_rewrite flag

    Quality Criteria (all must be true for "good"):
        - At least 1 filtered document
        - Average relevance score >= 0.6
        - Retrieval attempts < 2

    Decision:
        Good quality → should_rewrite = False → proceed to generation
        Poor quality → should_rewrite = True → rewrite query and retry

    Performance: <1ms (simple logic)
    """
```

**5. Rewrite Query Node**

```python
def rewrite_query_node(state: ParentingRAGState) -> dict:
    """
    Improves poorly-performing queries using LLM.

    Args:
        state: ParentingRAGState with original question

    Returns:
        Dict with improved question and incremented retrieval_attempts

    Process:
        1. Extract original question
        2. Invoke LLM with query improvement prompt
        3. Generate enhanced query (more specific, better keywords)
        4. Update state with new question
        5. Increment retrieval_attempts counter

    LLM Configuration:
        - Temperature: 0.3 (controlled creativity)

    Max Attempts: 2 (prevents infinite loops)

    Performance: ~500-1000ms
    """
```

**6. Generate Answer Node**

```python
def generate_answer_node(state: ParentingRAGState) -> dict:
    """
    Synthesizes answer from filtered documents using LLM.

    Args:
        state: ParentingRAGState with filtered_documents or empty

    Returns:
        Dict with generation (answer text) and sources

    Process:
        1. Extract question and filtered_documents
        2. Format documents as context
        3. Invoke LLM with PARENTING_AGENT_PROMPT
        4. Generate age-appropriate, evidence-based answer
        5. Extract source citations
        6. Return answer and metadata

    LLM Configuration:
        - Temperature: 0.7 (balanced creativity)

    Features:
        - Cites sources from documents
        - Age-appropriate language
        - Developmental context
        - Actionable advice

    Performance: ~2-5s
    """
```

**7. Confidence Check Node**

```python
def confidence_check_node(state: ParentingRAGState) -> dict:
    """
    Validates answer confidence using composite score.

    Args:
        state: ParentingRAGState with relevance_scores and filtered_documents

    Returns:
        Dict with confidence score

    Formula:
        confidence = (avg_relevance_score * 0.7) + (min(doc_count/3, 1.0) * 0.3)

    Weighting:
        - Relevance: 70% (quality of documents)
        - Coverage: 30% (quantity of documents, capped at 3)

    Threshold:
        - High confidence: >= 0.6 → return answer
        - Low confidence: < 0.6 → return insufficient_info

    Performance: <1ms
    """
```

**8. Insufficient Info Node**

```python
def insufficient_info_node(state: ParentingRAGState) -> dict:
    """
    Fallback response when confidence is low.

    Args:
        state: ParentingRAGState

    Returns:
        Dict with fallback message

    Message:
        - Acknowledges question
        - Explains limited information
        - Suggests consulting pediatrician or parenting expert
        - Encourages follow-up with more context

    Performance: <1ms (static response)
    """
```

#### Tool Definition

**File**: `app/agents/parenting_tools.py`

```python
@tool
async def search_parenting_knowledge(
    query: str,
    state: Annotated[dict, "InjectedState"]
) -> str:
    """
    Searches parenting knowledge base using hybrid retrieval + reranking.

    Args:
        query: Parenting-related question
        state: Injected state with retriever and reranker instances

    Returns:
        Formatted string of top_k documents with metadata

    Process:
        1. Extract retriever and reranker from injected state
        2. Hybrid search (FAISS + BM25):
           - Retrieves top_k * 2 candidates
           - Combines semantic and keyword matching
        3. Cross-encoder reranking:
           - Re-scores candidates for precision
           - Keeps top_k by relevance
        4. Store documents in state for downstream grading
        5. Format and return documents with:
           - Title/source
           - Content
           - Timestamps (if available)
           - Speakers (if from video transcript)

    Configuration:
        - top_k: From settings (default 3)
        - Hybrid alpha: 0.5 (balanced vector + keyword)

    Performance: ~500-1500ms (hybrid search + reranking)
    """
```

#### Agent Creation

```python
def create_parenting_rag_agent(
    retriever: DocumentRetriever,
    reranker: CrossEncoderReranker
) -> StateGraph:
    """
    Creates compiled multi-node LangGraph with corrective RAG.

    Args:
        retriever: HybridRetriever instance
        reranker: CrossEncoderReranker instance

    Returns:
        Compiled StateGraph[ParentingRAGState]

    Features:
        - 8-node pipeline with conditional routing
        - Query rewriting with max 2 attempts
        - Confidence-based fallback
        - Parent-child document support
        - Structured quality checks

    Routing Logic:
        - agent_decision → [tools OR generate_answer]
        - tools → grade_documents
        - grade_documents → check_quality
        - check_quality → [generate_answer OR rewrite_query]
        - rewrite_query → agent_decision (retry)
        - generate_answer → confidence_check
        - confidence_check → [END OR insufficient_info]

    Performance: 5-20s depending on query quality and retrieval cycles
    """
```

#### Integration with Main Graph

```python
def parenting_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    Wrapper for main graph integration.

    Args:
        state: MedicalChatState from main graph

    Returns:
        Command with updated messages and goto=END

    Process:
        1. Extract parenting_agent, retriever, reranker from state (closure)
        2. Create ParentingRAGState from MedicalChatState:
           - Extract question from last message
           - Initialize empty fields
        3. Invoke parenting RAG agent
        4. Extract final messages from result
        5. Return Command with updated messages

    Pattern: State transformation between graphs
        - Main graph uses MedicalChatState
        - Parenting agent uses ParentingRAGState
        - Wrapper handles conversion
    """
```

---

## Retrieval Systems

### FAISS Retriever (Vector Search)

**File**: `app/core/retriever.py`

#### Document Data Structure

```python
@dataclass
class Document:
    """
    Universal document representation.

    Attributes:
        content: str                      # Document text
        metadata: dict                    # Source, timestamp, etc.
        id: Optional[str]                 # Unique identifier
        parent_id: Optional[str]          # Reference to parent chunk
        child_ids: List[str]              # Child chunk IDs (for parent docs)
        timestamp_start: Optional[str]    # Video timestamp "HH:MM:SS.mmm"
        timestamp_end: Optional[str]      # Video timestamp "HH:MM:SS.mmm"
    """
```

#### FAISSRetriever Class

```python
class FAISSRetriever(DocumentRetriever):
    """
    Vector similarity search using FAISS and SentenceTransformers.

    Attributes:
        _model: SentenceTransformer              # Embedding model
        _documents: List[Document]               # Indexed documents
        _embeddings: np.ndarray                  # Embeddings [N, dim]
        _index: faiss.Index                      # FAISS index
        _device: str                             # "mps" or "cpu"

    Architecture:
        - Bi-encoder: Separate encoding of queries and documents
        - L2 distance metric: Euclidean distance for similarity
        - Apple Silicon optimization: MPS device support
    """
```

#### Key Methods

**Initialization**

```python
def __init__(self, embedding_model: str):
    """
    Initialize retriever with embedding model.

    Args:
        embedding_model: HuggingFace model name

    Device Detection:
        1. Check for Apple Silicon (MPS) availability
        2. Fallback to CPU if MPS unavailable
        3. Log device selection

    Index State: Empty until documents added
    """
```

**Adding Documents**

```python
async def add_documents(self, documents: List[Document]) -> None:
    """
    Incrementally add documents to index.

    Args:
        documents: List of Document objects to index

    Process:
        1. Encode documents using SentenceTransformer:
           - Batch encoding for efficiency
           - Normalize embeddings (L2 norm)
        2. Create or update FAISS index:
           - IndexFlatL2 for exact search
           - Add embeddings to index
        3. Store documents for retrieval mapping
        4. Log added count

    Performance: ~100ms per 100 documents
    Incremental: Can be called multiple times
    """
```

**Searching**

```python
async def search(self, query: str, top_k: int = 3) -> List[Document]:
    """
    Vector similarity search for relevant documents.

    Args:
        query: Search query text
        top_k: Number of documents to retrieve

    Returns:
        List of top_k most similar Document objects

    Process:
        1. Encode query using same embedding model
        2. FAISS search:
           - Find k-nearest neighbors (L2 distance)
           - Returns distances and indices
        3. Map indices to Document objects
        4. Return ordered by similarity (ascending distance)

    Performance: ~10-50ms depending on index size
    Algorithm: Exact search (brute force for accuracy)
    """
```

**Saving Index**

```python
async def save_index(self, path: str) -> None:
    """
    Persist FAISS index and metadata to disk.

    Args:
        path: Directory path for saving index files

    Saves:
        - faiss_index.pkl: FAISS index object
        - documents.pkl: List of Document objects
        - embeddings.npy: NumPy array of embeddings
        - metadata.json: Model name, timestamp, dimensions

    Process:
        1. Create directory if not exists
        2. Serialize and save all components
        3. Write metadata with timestamp
        4. Log save location

    Use Case: Pre-compute embeddings for production deployment
    """
```

**Loading Index**

```python
@classmethod
async def load_index(
    cls,
    path: str,
    embedding_model: str
) -> "FAISSRetriever":
    """
    Load pre-computed FAISS index from disk.

    Args:
        path: Directory containing index files
        embedding_model: Model name (must match saved index)

    Returns:
        FAISSRetriever with loaded index

    Validation:
        - All required files present
        - Document count == embedding count
        - Embedding dimensions consistent
        - Model name compatibility (warning if mismatch)

    Raises:
        FileNotFoundError: If required files missing
        ValueError: If validation fails

    Performance: ~100-500ms depending on index size
    """
```

---

### Hybrid Retriever (Vector + Keyword)

**File**: `app/core/hybrid_retriever.py`

#### Purpose

Combines FAISS vector search (semantic) with BM25 keyword search (lexical) for improved recall and precision.

#### Class Definition

```python
class HybridRetriever(DocumentRetriever):
    """
    Hybrid search combining semantic and lexical matching.

    Attributes:
        _faiss_retriever: FAISSRetriever       # Semantic search
        _documents: List[Document]             # All indexed documents
        _bm25_index: BM25Okapi                 # Keyword search
        _tokenized_corpus: List[List[str]]     # Tokenized documents
        _alpha: float                          # Combination weight [0, 1]
        _doc_id_to_idx: dict                   # Document ID → index mapping

    Alpha Parameter:
        - 0.0: Pure BM25 (keyword only)
        - 0.5: Balanced hybrid (default)
        - 1.0: Pure FAISS (semantic only)
    """
```

#### Initialization

```python
def __init__(
    self,
    faiss_retriever: FAISSRetriever,
    documents: List[Document],
    alpha: float = 0.5
):
    """
    Initialize hybrid retriever.

    Args:
        faiss_retriever: Pre-initialized FAISSRetriever
        documents: All documents (same as in FAISS)
        alpha: Weight for score combination (default 0.5)

    Process:
        1. Store FAISS retriever and documents
        2. Tokenize documents for BM25
        3. Build BM25 index
        4. Create doc_id_to_idx mapping for fast lookup

    Performance: ~100ms for 1000 documents
    """
```

#### Search Algorithm

```python
async def search(self, query: str, top_k: int = 3) -> List[Document]:
    """
    Hybrid search combining FAISS and BM25.

    Args:
        query: Search query text
        top_k: Number of documents to return

    Returns:
        List of top_k documents ranked by combined score

    Algorithm:
        1. Calculate effective_top_k:
           min(top_k * 3, total_documents)
           - Over-retrieve for better coverage

        2. FAISS semantic search:
           - Get effective_top_k candidates
           - Scores from L2 distances

        3. BM25 keyword search:
           - Tokenize query
           - Get effective_top_k candidates
           - Scores from BM25 algorithm

        4. Normalize scores to [0, 1]:
           - Min-max normalization
           - Handles different score ranges

        5. Combine scores:
           combined = alpha * faiss_score + (1-alpha) * bm25_score

        6. Sort by combined score (descending)

        7. Parent-child resolution:
           - If document has parent_id, return parent instead
           - Deduplicates when multiple children match

        8. Return top_k documents

    Performance: ~100-500ms depending on index size

    Example Scores:
        Query: "sleep training methods"

        Doc A (FAISS=0.8, BM25=0.4):
          combined = 0.5*0.8 + 0.5*0.4 = 0.6

        Doc B (FAISS=0.6, BM25=0.7):
          combined = 0.5*0.6 + 0.5*0.7 = 0.65

        Result: Doc B ranked higher (better keyword match)
    """
```

#### Helper Methods

```python
def _tokenize_documents(documents: List[Document]) -> List[List[str]]:
    """
    Simple whitespace tokenization for BM25.

    Args:
        documents: List of Document objects

    Returns:
        List of tokenized content (list of word lists)

    Process:
        - Split on whitespace
        - Lowercase conversion
        - No stemming or stopword removal (preserves accuracy)
    """

def _bm25_search(self, query: str, top_k: int) -> Dict[str, float]:
    """
    BM25 keyword search.

    Args:
        query: Search query
        top_k: Number of results

    Returns:
        Dict mapping document_id to BM25 score

    Algorithm: BM25Okapi (best-match ranking function)
    """

def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
    """
    Min-max normalization to [0, 1].

    Args:
        scores: Dict mapping document_id to raw score

    Returns:
        Dict with normalized scores

    Formula:
        normalized = (score - min) / (max - min)

    Edge Cases:
        - Single score: returns {doc: 1.0}
        - All same scores: returns {doc: 1.0 for all}
    """

def _combine_scores(
    self,
    faiss_scores: Dict[str, float],
    bm25_scores: Dict[str, float]
) -> Dict[str, float]:
    """
    Weighted linear combination of scores.

    Args:
        faiss_scores: Normalized FAISS scores
        bm25_scores: Normalized BM25 scores

    Returns:
        Dict with combined scores

    Formula:
        combined = alpha * faiss + (1-alpha) * bm25

    Missing Scores:
        - If doc only in FAISS: bm25 = 0.0
        - If doc only in BM25: faiss = 0.0
    """

def _get_parent_document(self, doc: Document) -> Document:
    """
    Retrieve parent document if child has parent_id.

    Args:
        doc: Document (potentially a child)

    Returns:
        Parent document if parent_id exists, else original doc

    Lookup Strategy:
        1. Try fast lookup via doc_id_to_idx
        2. Fallback to linear search if ID not found
        3. Return original if no parent found

    Use Case: Child documents provide context, parent provides full content
    """
```

#### Configuration Methods

```python
def set_alpha(self, alpha: float) -> None:
    """
    Dynamically adjust FAISS/BM25 weight.

    Args:
        alpha: New weight [0.0, 1.0]

    Raises:
        ValueError: If alpha not in [0, 1]

    Use Case: Tune balance based on query characteristics
        - More semantic queries → higher alpha
        - More keyword queries → lower alpha
    """

def get_stats(self) -> dict:
    """
    Return retriever statistics.

    Returns:
        Dict with metadata:
            - total_documents: int
            - alpha: float
            - faiss_index_size: int
            - bm25_corpus_size: int
    """
```

---

### Cross-Encoder Reranker

**File**: `app/core/reranker.py`

#### Purpose

Reranks retrieved documents using cross-encoder models for more accurate relevance scoring.

#### Class Definition

```python
class CrossEncoderReranker:
    """
    Cross-encoder reranking for improved top-k precision.

    Architecture Comparison:
        Bi-encoder (FAISS):
            - Encodes query and docs separately
            - Compares vector representations
            - Fast: O(1) per comparison (pre-computed)
            - Less accurate for subtle relevance

        Cross-encoder (Reranker):
            - Encodes (query, doc) pairs jointly
            - Attention mechanism between query and doc
            - Slower: O(n) pairs to evaluate
            - More accurate relevance scoring

    Attributes:
        _model: CrossEncoder              # Cross-encoder model
        _max_length: int                  # Max token length (512)
        _device: str                      # "mps" or "cpu"

    Use Case: Rerank top candidates from fast retrieval
    """
```

#### Initialization

```python
def __init__(
    self,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    max_length: int = 512
):
    """
    Initialize cross-encoder reranker.

    Args:
        model_name: HuggingFace cross-encoder model
        max_length: Maximum sequence length

    Device Detection:
        1. Check for Apple Silicon (MPS)
        2. Fallback to CPU
        3. Log device selection

    Default Model: ms-marco-MiniLM-L-6-v2
        - Trained on MS MARCO passage ranking
        - Good balance of speed and accuracy
        - ~80MB model size
    """
```

#### Reranking Method

```python
def rerank(
    self,
    query: str,
    documents: List[Document],
    top_k: int
) -> List[Document]:
    """
    Rerank documents and return top_k by relevance.

    Args:
        query: Search query text
        documents: Retrieved documents (from FAISS/Hybrid)
        top_k: Number of documents to return

    Returns:
        List of top_k documents sorted by cross-encoder score (descending)

    Process:
        1. Edge case handling:
           - Empty documents → return []
           - Single document → return it
           - top_k > len(documents) → return all

        2. Create (query, document.content) pairs

        3. Cross-encoder inference:
           - Encode pairs jointly
           - Generate relevance scores (logits)
           - Higher score = more relevant

        4. Attach scores to documents

        5. Sort by score (descending)

        6. Return top_k documents

        7. Log statistics:
           - Score range (min, max, mean)
           - Top document metadata

    Performance: ~50-200ms per document

    Score Interpretation:
        - Scores are logits (not probabilities)
        - Relative ordering matters, not absolute values
        - Typical range: -10 to +10
        - Positive scores generally indicate relevance

    Example:
        Query: "toddler sleep regression"
        Documents: 10 candidates from hybrid search

        Cross-encoder scores:
          Doc 1: 8.5 (highly relevant)
          Doc 2: 7.2 (relevant)
          Doc 3: 5.8 (somewhat relevant)
          ...
          Doc 10: -2.3 (not relevant)

        Returns: Top 3 docs with scores [8.5, 7.2, 5.8]
    """
```

---

### Transcript Chunker (Hierarchical)

**File**: `app/core/transcript_chunker.py`

#### Purpose

Processes VTT video transcripts into hierarchical parent-child chunks for parenting knowledge base.

#### Class Definition

```python
class TranscriptChunker:
    """
    Processes VTT transcripts into parent-child hierarchy.

    Chunking Strategy:
        Parent Chunks: ~750 tokens (~3 min video context)
            - Provides broad context
            - Used for parent document retrieval
            - Contains child_ids for fine-grained access

        Child Chunks: ~150 tokens (~35 sec fine-grained)
            - Enables precise retrieval
            - Embedded for vector search
            - Contains parent_id reference

        Overlap: ~30 tokens
            - Preserves context across boundaries
            - Prevents information loss at splits

    Metadata Tracking:
        - Timestamps: HH:MM:SS.mmm format for video linking
        - Speakers: Extracted from VTT tags
        - Character positions: For precise timestamp mapping
        - Parent-child relationships: Hierarchical structure

    Attributes:
        child_chunk_size: int              # Child size in tokens (150)
        parent_chunk_size: int             # Parent size in tokens (750)
        overlap: int                       # Overlap in tokens (30)
        _model: SentenceTransformer        # For child embeddings
        _device: str                       # "mps" or "cpu"
    """
```

#### Initialization

```python
def __init__(
    self,
    child_chunk_size: int = 150,
    parent_chunk_size: int = 750,
    overlap: int = 30,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
):
    """
    Initialize transcript chunker.

    Args:
        child_chunk_size: Tokens per child chunk
        parent_chunk_size: Tokens per parent chunk
        overlap: Token overlap between chunks
        model_name: Embedding model for children

    Configuration:
        - Token approximation: 1 token ≈ 4 characters
        - RecursiveCharacterTextSplitter for sentence boundaries
        - Device detection (MPS/CPU)
    """
```

#### Main Pipeline

```python
def create_chunks(
    self,
    vtt_path: str,
    video_metadata: dict
) -> dict:
    """
    Process VTT file into hierarchical chunks.

    Args:
        vtt_path: Path to .vtt transcript file
        video_metadata: Dict with video info (title, url, etc.)

    Returns:
        Dict with:
            'parents': List[dict] - Parent chunk metadata
            'children': List[dict] - Child chunk metadata + embeddings

    Pipeline:
        1. Parse VTT file:
           - Extract captions with timestamps
           - Detect speakers from tags
           - Clean caption text

        2. Merge captions by speaker:
           - Consolidate consecutive same-speaker segments
           - Preserve timestamp ranges

        3. Build full transcript:
           - Concatenate all captions
           - Create character-to-timestamp mapping

        4. Create parent chunks:
           - Split on sentence boundaries
           - ~750 tokens per chunk
           - Track character positions

        5. For each parent:
           a. Create child chunks (~150 tokens)
           b. Generate embeddings for children
           c. Map character ranges to timestamps
           d. Extract unique speakers
           e. Link parent-child relationships

        6. Return structured output

    Performance: ~1-2s per 30-minute video transcript

    Output Structure:
        {
            'parents': [
                {
                    'parent_id': 'parent_0',
                    'text': '...',
                    'time_start': '00:00:01.000',
                    'time_end': '00:03:15.500',
                    'speakers': ['Dr. Smith', 'Jane'],
                    'char_start': 0,
                    'char_end': 2500,
                    'child_count': 5,
                    'child_ids': ['child_0', 'child_1', ...],
                    ...video_metadata
                }
            ],
            'children': [
                {
                    'child_id': 'child_0',
                    'parent_id': 'parent_0',
                    'text': '...',
                    'embedding': np.ndarray,  # [384]
                    'time_start': '00:00:01.000',
                    'time_end': '00:00:35.500',
                    'speakers': ['Dr. Smith'],
                    'char_start': 0,
                    'char_end': 500,
                    ...video_metadata
                }
            ]
        }
    """
```

#### VTT Parsing

```python
def parse_vtt(self, vtt_path: str) -> List[dict]:
    """
    Parse VTT file extracting captions with timestamps.

    Args:
        vtt_path: Path to VTT file

    Returns:
        List of caption dicts:
            {
                'start_seconds': float,
                'end_seconds': float,
                'speaker': str or None,
                'text': str (cleaned)
            }

    Process:
        1. Load VTT using webvtt-py library
        2. For each caption:
           - Extract timestamps
           - Detect speaker from text
           - Clean caption text
           - Convert timestamps to seconds
        3. Return chronological list

    Speaker Detection:
        Format 1: "Name: text content"
        Format 2: "<v Name>text content"
        Format 3: No speaker tag → None
    """

def merge_captions_by_speaker(self, captions: List[dict]) -> List[dict]:
    """
    Merge consecutive same-speaker captions.

    Args:
        captions: List from parse_vtt

    Returns:
        Merged caption list with consolidated segments

    Logic:
        - Consecutive captions with same speaker → merge
        - Speaker change or None speaker → new segment
        - Timestamps span from first to last in sequence

    Benefit: Reduces fragmentation, preserves speaker turns
    """
```

#### Timestamp Mapping

```python
def _build_text_and_mapping(
    self,
    merged_captions: List[dict]
) -> Tuple[str, List[Tuple[int, int, float, float]]]:
    """
    Build full transcript and character-to-time mapping.

    Args:
        merged_captions: Output from merge_captions_by_speaker

    Returns:
        Tuple of:
            - full_text: Concatenated transcript
            - mapping: List of (char_start, char_end, time_start, time_end)

    Process:
        1. Concatenate all caption texts
        2. Track character positions for each caption
        3. Store corresponding timestamps
        4. Return full text + position mapping

    Use Case: Map chunk character ranges → video timestamps
    """

def _get_time_range(
    self,
    char_start: int,
    char_end: int,
    mapping: List[Tuple]
) -> Tuple[str, str]:
    """
    Map character range to video timestamps.

    Args:
        char_start: Chunk start character position
        char_end: Chunk end character position
        mapping: Output from _build_text_and_mapping

    Returns:
        Tuple of (start_timestamp, end_timestamp) in HH:MM:SS.mmm

    Algorithm:
        1. Find overlapping captions for character range
        2. Extract earliest start time
        3. Extract latest end time
        4. Format as HH:MM:SS.mmm strings

    Edge Cases:
        - No overlap: returns ("00:00:00.000", "00:00:00.000")
        - Partial overlap: uses intersecting range
    """

def _extract_speakers_from_range(
    self,
    char_start: int,
    char_end: int,
    merged_captions: List[dict]
) -> List[str]:
    """
    Extract unique speakers in character range.

    Args:
        char_start: Chunk start position
        char_end: Chunk end position
        merged_captions: Merged captions with speaker info

    Returns:
        List of unique speaker names (or empty list)

    Process:
        1. Find captions overlapping character range
        2. Collect speakers (excluding None)
        3. Return unique speaker list
    """
```

#### Embedding Generation

```python
def _generate_embedding(self, text: str) -> np.ndarray:
    """
    Generate embedding for child chunk.

    Args:
        text: Child chunk text

    Returns:
        NumPy array of embeddings [embedding_dim]

    Process:
        1. Encode text using SentenceTransformer
        2. Return normalized embedding vector

    Performance: ~10-30ms per chunk
    Model: Same as FAISSRetriever for consistency
    """
```

---

## State Management

### Graph State

**File**: `app/graph/state.py`

```python
class MedicalChatState(MessagesState):
    """
    Main state for medical chatbot LangGraph.

    Inherits from MessagesState:
        messages: List[BaseMessage]       # Conversation history

    Additional Attributes:
        session_id: str                   # Unique session identifier
        assigned_agent: Optional[str]     # Agent handling conversation
        metadata: dict                    # Session-level metadata

    Usage:
        - Passed through graph execution
        - Checkpointed by MemorySaver
        - Updated by nodes via Command pattern

    Serialization:
        - All fields must be msgpack-serializable
        - Non-serializable objects (agents, retrievers) in closure
    """
```

### Session Storage

**File**: `app/core/session_store.py`

#### Session Data

```python
@dataclass
class SessionData:
    """
    Session information stored between requests.

    Attributes:
        session_id: str                   # Unique identifier
        assigned_agent: Optional[str]     # Assigned agent name
        metadata: Dict                    # Custom metadata
        created_at: datetime              # Creation timestamp
        updated_at: datetime              # Last update timestamp
    """
```

#### SessionStore Interface

```python
class SessionStore(ABC):
    """
    Abstract interface for session persistence.

    Methods:
        get_session(session_id) -> Optional[SessionData]
        save_session(session_id, data) -> None
        delete_session(session_id) -> None

    Implementations:
        - InMemorySessionStore: Development/testing
        - PostgresSessionStore: Production (future)
        - RedisSessionStore: Production high-performance (future)
    """
```

#### In-Memory Implementation

```python
class InMemorySessionStore(SessionStore):
    """
    In-memory session storage with TTL.

    Attributes:
        _sessions: Dict[str, SessionData] # Session storage
        _lock: asyncio.Lock               # Thread safety
        _ttl_seconds: int                 # Time-to-live

    Features:
        - Thread-safe operations with locks
        - Automatic expiration after TTL
        - Periodic cleanup of expired sessions
        - O(1) lookup, insert, delete

    Limitations:
        - Not persistent across restarts
        - Single-server only (no distribution)
        - Memory-bound capacity

    Methods:
        get_session(session_id) -> Optional[SessionData]
            - Returns session if exists and not expired
            - Returns None if not found or expired

        save_session(session_id, data) -> None
            - Stores or updates session
            - Updates updated_at timestamp

        delete_session(session_id) -> None
            - Removes session from storage

        clear_expired_sessions() -> int
            - Removes sessions past TTL
            - Returns count of cleared sessions
            - Can be called periodically
    """
```

---

## Graph Orchestration

**File**: `app/graph/builder.py`

### Graph Architecture

```
START
  ↓
check_assignment (route_based_on_assignment)
  │
  ├─ [assigned_agent == None] → supervisor
  │   │
  │   └─ Classifies intent → Routes to agent
  │       ↓
  │   [emotional_support | rag_agent | parenting]
  │       ↓
  │      END
  │
  └─ [assigned_agent != None] → Direct to assigned agent
      │
      └─ [emotional_support | rag_agent | parenting]
          ↓
         END
```

### Key Functions

#### Routing Logic

```python
def route_based_on_assignment(state: MedicalChatState) -> str:
    """
    Implements session-sticky routing.

    Args:
        state: MedicalChatState with assigned_agent field

    Returns:
        Node name to route to

    Logic:
        if assigned_agent is None:
            return "supervisor"  # First message
        else:
            return assigned_agent  # Subsequent messages

    Effect: Ensures consistent agent handling per session

    Example:
        Message 1: assigned_agent=None → routes to supervisor → sets assigned_agent="rag_agent"
        Message 2: assigned_agent="rag_agent" → routes directly to rag_agent
        Message 3: assigned_agent="rag_agent" → routes directly to rag_agent
    """
```

#### Graph Builder

```python
def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: Optional[DocumentRetriever] = None,
    parenting_reranker: Optional[CrossEncoderReranker] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None
) -> CompiledGraph:
    """
    Builds compiled LangGraph for medical chatbot.

    Args:
        retriever: FAISSRetriever for medical knowledge
        parenting_retriever: HybridRetriever for parenting (optional)
        parenting_reranker: CrossEncoderReranker for parenting (optional)
        checkpointer: Custom checkpointer or None for default

    Returns:
        CompiledGraph ready for ainvoke()

    Architecture Pattern: Closure + Wrapper Nodes
        Problem:
            - Agents and retrievers are not serializable
            - MemorySaver uses msgpack (requires serialization)

        Solution:
            - Capture non-serializable objects in closure scope
            - Create wrapper nodes that inject objects into state
            - Only serialize MedicalChatState (messages, session_id, etc.)

        Example:
            # Captured in closure (not in state)
            rag_agent = create_rag_agent(retriever)

            # Wrapper node
            def rag_node_wrapper(state):
                # Access rag_agent from closure
                state_with_retriever = {**state, "retriever": retriever}
                return rag_agent.invoke(state_with_retriever)

    Graph Structure:
        1. Add "check_assignment" node (route_based_on_assignment)
        2. Add "supervisor" node (supervisor_node)
        3. Add "emotional_support" node (wrapper)
        4. Add "rag_agent" node (wrapper with retriever injection)
        5. Add "parenting" node (wrapper with retriever + reranker) [if available]
        6. Set entry point: "check_assignment"
        7. Add conditional edges from "check_assignment" to all agents
        8. Add edges from supervisor to all agents
        9. Add edges from all agents to END
        10. Compile with checkpointer

    Checkpointer Logic:
        - If None provided: Uses MemorySaver() for production
        - If provided: Uses custom checkpointer (for tests)

    Features:
        - Session-aware routing
        - Conversation memory via checkpointer
        - Optional parenting agent with graceful degradation
        - Closure-based dependency injection

    Performance: <1ms for routing, variable for agent execution
    """
```

#### Checkpointer Helper

```python
def _get_checkpointer() -> BaseCheckpointSaver:
    """
    Returns default checkpointer for production.

    Returns:
        MemorySaver instance

    Usage:
        - Called by build_medical_chatbot_graph when checkpointer=None
        - Tests provide AsyncSqliteSaver directly to avoid conflicts

    MemorySaver:
        - In-memory conversation persistence
        - Keyed by thread_id (session_id)
        - Not persistent across restarts
        - Suitable for single-server deployments
    """
```

---

## Data Models

**File**: `app/models.py`

### Request/Response Models

```python
class ChatRequest(BaseModel):
    """
    Chat endpoint request payload.

    Attributes:
        session_id: str          # Unique session identifier
        message: str             # User message (min_length=1)

    Validation:
        - session_id: Required, non-empty string
        - message: Required, min_length=1

    Example:
        {
            "session_id": "user_12345",
            "message": "What are the side effects of aspirin?"
        }
    """

class ChatResponse(BaseModel):
    """
    Chat endpoint response payload.

    Attributes:
        session_id: str          # Echo of request session_id
        message: str             # Agent response text
        agent: str               # Agent that handled request
        metadata: Optional[dict] # Additional information

    Agent Values:
        - "supervisor": Intent classification (should not appear in response)
        - "emotional_support": Empathetic support
        - "rag_agent": Medical information
        - "parenting": Parenting advice

    Metadata Examples:
        {
            "reasoning": "User expressing emotional distress",
            "confidence": 0.85,
            "sources": [{"title": "...", "url": "..."}]
        }

    Example:
        {
            "session_id": "user_12345",
            "message": "Aspirin commonly causes...",
            "agent": "rag_agent",
            "metadata": {
                "sources": [
                    {"name": "Aspirin Information", "content": "..."}
                ]
            }
        }
    """

class HealthResponse(BaseModel):
    """
    Health check endpoint response.

    Attributes:
        status: str = "healthy"
        version: str = "0.1.0"
    """
```

---

## System Prompts

**File**: `app/utils/prompts.py`

### Prompt Overview

| Prompt | Agent | Purpose |
|--------|-------|---------|
| `SUPERVISOR_PROMPT` | Supervisor | Intent classification |
| `EMOTIONAL_SUPPORT_PROMPT` | Emotional Support | Empathetic responses |
| `RAG_AGENT_PROMPT` | RAG Agent | Medical Q&A with retrieval |
| `PARENTING_AGENT_PROMPT` | Parenting Agent | Parenting advice |

### SUPERVISOR_PROMPT

```
Purpose: Route user queries to appropriate agent

Routing Logic:
  - Emotional support: Feelings, stress, anxiety, emotional distress
  - RAG agent: Medical questions, medications, treatments, conditions
  - Parenting: Child development, parenting, toddler/infant care

Output: JSON with agent, reasoning, confidence
```

### EMOTIONAL_SUPPORT_PROMPT

```
Purpose: Provide empathetic, non-clinical emotional support

Guidelines:
  - Active listening and validation
  - No medical advice or diagnosis
  - Encourage professional help for serious concerns
  - Crisis resources (988 hotline, Crisis Text Line)
  - Boundaries: Not a therapist, limited scope

Tone: Warm, empathetic, supportive
```

### RAG_AGENT_PROMPT

```
Purpose: Answer medical questions using knowledge base

Requirements:
  - MUST use search_medical_docs tool before answering
  - Educational information only (not medical advice)
  - Cite sources from retrieved documents
  - Encourage consulting healthcare providers

Disclaimers:
  - Not a replacement for professional medical advice
  - Consult doctor for diagnosis and treatment

Format: Structured, evidence-based, cited
```

### PARENTING_AGENT_PROMPT

```
Purpose: Provide expert parenting and child development advice

Requirements:
  - Use search_parenting_knowledge tool
  - Age-appropriate guidance
  - Evidence-based recommendations
  - Developmental context

Guidelines:
  - Consider child's age and stage
  - Practical, actionable advice
  - Respect parenting approaches
  - Acknowledge individual differences

Tone: Supportive, informative, non-judgmental
```

---

## Data Flow

### Chat Request Processing

```
1. POST /chat
   ├─ Input: {session_id, message}
   └─ FastAPI handler: chat()

2. Session Management
   ├─ Load session from SessionStore
   └─ Create session if not exists

3. Construct State
   ├─ MedicalChatState:
   │   ├─ messages: [HumanMessage(message)]
   │   ├─ session_id: from request
   │   ├─ assigned_agent: from session or None
   │   └─ metadata: {}
   └─ Config: {configurable: {thread_id: session_id}}

4. Graph Invocation
   ├─ graph.ainvoke(state, config)
   ├─ check_assignment → route
   │   ├─ First message: → supervisor → classify → route to agent
   │   └─ Subsequent: → assigned_agent directly
   └─ Agent execution → response

5. Response Extraction
   ├─ Last message from result["messages"]
   ├─ Agent name from state or message metadata
   └─ Metadata from state

6. Session Update
   ├─ Update assigned_agent
   ├─ Update metadata
   ├─ Update updated_at timestamp
   └─ Save to SessionStore

7. Return Response
   └─ ChatResponse {session_id, message, agent, metadata}
```

### Parenting Agent Internal Flow

```
1. parenting_agent_node receives MedicalChatState

2. Transform to ParentingRAGState
   ├─ Extract question from last message
   ├─ Initialize: documents=[], filtered_documents=[]
   ├─ Set: retrieval_attempts=0, confidence=0.0
   └─ Copy messages

3. Agent Decision
   ├─ LLM analyzes question
   ├─ Decides: retrieve or answer directly?
   └─ Returns messages with or without tool_calls

4. If tool_calls: Execute retrieval
   ├─ search_parenting_knowledge(query)
   ├─ Hybrid search (FAISS + BM25)
   ├─ Cross-encoder reranking
   ├─ Store documents in state
   └─ Continue to grading

5. Grade Documents
   ├─ For each document:
   │   ├─ LLM grades relevance
   │   └─ Returns score [0.0-1.0]
   ├─ Filter: score >= 0.5
   └─ Store filtered_documents + relevance_scores

6. Check Quality
   ├─ Criteria: docs >= 1, avg_score >= 0.6, attempts < 2
   ├─ Good quality: → generate_answer
   └─ Poor quality: → rewrite_query → retry (back to step 3)

7. Generate Answer
   ├─ LLM synthesizes from filtered_documents
   ├─ Age-appropriate, evidence-based
   ├─ Extract sources
   └─ Return generation

8. Confidence Check
   ├─ Calculate: avg_relevance*0.7 + doc_coverage*0.3
   ├─ High (>= 0.6): → Return answer
   └─ Low (< 0.6): → insufficient_info (fallback response)

9. Return to Main Graph
   ├─ Extract final messages
   ├─ Update MedicalChatState
   └─ Return Command(goto=END)
```

---

## Key Architectural Patterns

### 1. Serialization Problem & Solution

**Problem**: LangGraph's MemorySaver uses msgpack serialization
- FAISSRetriever, agents are not serializable
- Cannot store in graph state
- Checkpointing fails with serialization errors

**Solution: Closure Pattern**

```python
# In builder.py
def build_medical_chatbot_graph(retriever, ...):
    # Create agents (captured in closure, not in state)
    rag_agent = create_rag_agent(retriever)
    parenting_agent = create_parenting_rag_agent(retriever, reranker)

    # Wrapper nodes access closure variables
    def rag_node_wrapper(state: MedicalChatState):
        # rag_agent accessible via closure
        # retriever accessible via closure
        state_with_retriever = {**state, "retriever": retriever}
        response = rag_agent.invoke(state_with_retriever)
        return Command(goto=END, update={"messages": response["messages"]})

    # Add wrapper to graph (closure captured)
    builder.add_node("rag_agent", rag_node_wrapper)

    # Only MedicalChatState gets checkpointed (serializable)
    return builder.compile(checkpointer=MemorySaver())
```

**Key Points**:
- Non-serializable objects live in closure scope
- Wrapper nodes inject objects into state during execution
- Only serializable state (messages, session_id) gets checkpointed
- Conversation history persists correctly

---

### 2. Two-Layer Checkpointing

```
Outer Layer (Main Graph):
  ├─ Checkpointer: MemorySaver()
  ├─ State: MedicalChatState (serializable)
  ├─ Persists: messages, session_id, assigned_agent, metadata
  └─ Thread ID: session_id

Inner Layers (Agent Graphs):
  ├─ RAG Agent: checkpointer=False (stateless)
  ├─ Parenting Agent: Nested graph, no checkpointing
  └─ Emotional Support: Direct invocation, no state
```

**Rationale**:
- Outer graph manages conversation memory
- Inner agents are stateless (recalculate each invocation)
- Prevents nested checkpointing conflicts
- Simplifies agent design

---

### 3. Session-Sticky Routing

```
First Message in Session:
  1. assigned_agent = None
  2. Route to supervisor
  3. Supervisor classifies intent
  4. Returns Command(goto=<agent>, update={assigned_agent: <agent>})
  5. Routed to appropriate agent
  6. Response generated
  7. State checkpointed with assigned_agent

Subsequent Messages:
  1. Load state: assigned_agent = "rag_agent"
  2. route_based_on_assignment checks assigned_agent
  3. Routes directly to "rag_agent" (skip supervisor)
  4. Agent processes message with conversation context
  5. Response generated
  6. State updated and checkpointed
```

**Benefits**:
- Consistent agent handling per session
- Reduces classification overhead
- Maintains conversation continuity
- Prevents agent switching mid-conversation

---

### 4. Graceful Degradation

**Medical Embeddings** (REQUIRED):
```python
# In main.py lifespan
try:
    medical_retriever = await _load_medical_retriever()
except FileNotFoundError:
    logger.error("Medical embeddings not found - CANNOT START")
    raise  # Fail-fast
```

**Parenting Embeddings** (OPTIONAL):
```python
try:
    parenting_retriever, reranker = await _load_parenting_system()
except FileNotFoundError:
    parenting_retriever, reranker = None, None
    logger.warning("Parenting agent disabled - graceful degradation")

# Build graph with optional parenting
graph = build_medical_chatbot_graph(
    retriever=medical_retriever,
    parenting_retriever=parenting_retriever,  # May be None
    parenting_reranker=reranker  # May be None
)
```

**Result**: Application runs with reduced functionality rather than crashing

---

### 5. Parent-Child Document Hierarchy

**Purpose**: Balance context and precision

```
Parent Document:
  ├─ ID: "parent_0"
  ├─ Content: ~750 tokens (~3 min video)
  ├─ Child IDs: ["child_0", "child_1", "child_2", "child_3", "child_4"]
  └─ Use: Provides broad context when retrieved

Child Documents (embedded):
  ├─ ID: "child_0"
  ├─ Parent ID: "parent_0"
  ├─ Content: ~150 tokens (~35 sec video)
  ├─ Embedding: [384] vector
  └─ Use: Precise retrieval, returns parent for full context
```

**Retrieval Flow**:
```
1. User query: "toddler sleep training"
2. Vector search on child embeddings (precise)
3. Top child matches: child_5, child_12, child_23
4. Map to parents: parent_1, parent_2, parent_4
5. Return parent documents (full context)
6. Deduplication if multiple children share parent
```

**Benefits**:
- Precise retrieval (child granularity)
- Rich context (parent content)
- Reduced redundancy (deduplicated parents)

---

## Deployment Guide

### Pre-deployment Checklist

**1. Medical Embeddings (REQUIRED)**

```bash
python -m src.precompute_embeddings
```

Creates in `data/embeddings/`:
- `faiss_index.pkl` - FAISS index
- `documents.pkl` - Document objects
- `embeddings.npy` - Embedding vectors
- `metadata.json` - Index metadata

**2. Parenting Embeddings (OPTIONAL)**

```bash
python -m src.precompute_parenting_embeddings --force
```

Creates in `data/parenting_index/`:
- `child_documents.pkl` - Child documents with embeddings
- `parent_chunks.pkl` - Parent documents
- `bm25_index.pkl` - BM25 index for keyword search

**3. Environment Variables**

Required:
```bash
OPENAI_API_KEY=your-openrouter-api-key
OPENAI_API_BASE=https://openrouter.ai/api/v1
```

Optional (with defaults):
```bash
MODEL_NAME=qwen/qwen3-max
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
INDEX_PATH=data/embeddings/
PARENTING_INDEX_PATH=data/parenting_index
TOP_K_DOCUMENTS=3
ENVIRONMENT=production
```

**4. Dependencies**

```bash
pip install -r requirements.txt
```

Key dependencies:
- langgraph
- langchain
- langchain-openai
- sentence-transformers
- faiss-cpu (or faiss-gpu)
- rank-bm25
- webvtt-py
- fastapi
- uvicorn
- pydantic

**5. Start Application**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production:
```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

---

### Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Health check | ~1ms | No I/O |
| Session lookup | ~1-5ms | In-memory dict lookup |
| Supervisor classification | 500-1000ms | LLM structured output |
| Emotional support | 2-5s | LLM generation (high temp) |
| Medical RAG (no retrieval) | 2-3s | Direct LLM generation |
| Medical RAG (with retrieval) | 3-8s | FAISS search + LLM |
| Parenting RAG (optimal) | 5-10s | Hybrid + rerank + generation |
| Parenting RAG (with rewrite) | 10-20s | Up to 2 retry cycles |

**Bottlenecks**:
- LLM inference (OpenRouter API)
- Network latency (API calls)
- Cross-encoder reranking (O(n) documents)

**Optimizations**:
- Pre-computed embeddings (offline)
- Caching (future enhancement)
- Batch API requests (future)
- GPU acceleration for embeddings (optional)

---

### Monitoring & Logging

**Log Levels**:
- `DEBUG`: Detailed execution flow
- `INFO`: Key events (startup, routing decisions, performance)
- `WARNING`: Non-critical issues (missing optional components)
- `ERROR`: Failures requiring attention

**Key Metrics to Monitor**:
- Request latency (p50, p95, p99)
- Agent distribution (supervisor classifications)
- Error rates by agent
- Session store size and expiration
- LLM API costs and latency
- Retrieval quality (relevance scores)

**Health Check**:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "0.1.0"}
```

---

## Summary

This backend API provides a sophisticated multi-agent medical chatbot with:

**Core Capabilities**:
- Intent-based routing to specialized agents
- Session-aware conversation memory
- Retrieval-augmented generation with quality checks
- Hybrid vector + keyword search
- Hierarchical document processing

**Key Design Patterns**:
- Closure-based dependency injection
- Graceful degradation
- Session-sticky routing
- Parent-child document hierarchy
- Two-layer checkpointing

**Production Ready Features**:
- FastAPI with async handlers
- Configurable via environment
- Pre-computed embeddings
- Health monitoring
- Comprehensive error handling

For questions or issues, refer to specific sections above or consult the source code.
