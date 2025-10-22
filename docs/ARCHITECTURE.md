# Medical Chatbot Architecture

## Overview

This is a multi-agent medical chatbot system built with LangGraph 0.6.0, designed for mental health support and medication information retrieval. The system uses a session-sticky routing pattern where the first message classifies the user's intent and assigns an appropriate agent for the entire session.

## Core Principles

1. **Session-Sticky Routing**: Once a session is classified, all subsequent messages go directly to the assigned agent
2. **Abstract Interfaces**: Easy migration from in-memory to production databases
3. **Extensible Retrieval**: Swap FAISS → BM25 → Hybrid without changing agent code
4. **Type Safety**: Full Pydantic v2 models and mypy compliance
5. **Async-First**: All I/O operations are asynchronous for high performance

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  POST /chat                                                  │
│  GET /health                                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Session Manager│
        │ (SessionStore) │
        └───┬────────────┘
            │
            ▼
   ┌────────────────────┐
   │ Is session new?    │
   └─────┬──────┬───────┘
         │      │
    YES  │      │ NO
         │      │
         ▼      ▼
   ┌──────┐   ┌────────────────────┐
   │Sup   │   │ Route to assigned  │
   │ervi  │   │ agent directly     │
   │sor   │   └────────┬───────────┘
   └──┬───┘            │
      │                │
      ├────────────────┴───────────────┐
      │                                │
      ▼                                ▼
┌──────────────┐              ┌────────────────┐
│ Emotional    │              │  RAG Agent     │
│ Support      │              │  (Medical Info)│
│ Agent        │              └───┬────────────┘
└──────────────┘                  │
                                  ▼
                          ┌───────────────┐
                          │DocumentRetriever│
                          │  (FAISS/BM25)  │
                          └────────────────┘
```

## Component Architecture

### 1. Session Management Layer

**Purpose**: Track user sessions and assigned agents across requests

**Interface**: `SessionStore` (abstract base class)
```python
class SessionStore(ABC):
    async def get_session(session_id: str) -> Optional[SessionData]
    async def save_session(session_id: str, data: SessionData) -> None
    async def delete_session(session_id: str) -> None
```

**Implementations**:
- **InMemorySessionStore** (POC): Dict with threading.Lock, TTL-based expiration
- **RedisSessionStore** (Future): Fast, distributed, TTL support
- **PostgresSessionStore** (Future): Structured queries, ACID compliance

**SessionData Structure**:
```python
@dataclass
class SessionData:
    session_id: str
    assigned_agent: Optional[str]  # "emotional_support" | "rag_agent" | None
    metadata: Dict
    created_at: datetime
    updated_at: datetime
```

### 2. Document Retrieval Layer

**Purpose**: Flexible search over medical knowledge base

**Interface**: `DocumentRetriever` (abstract base class)
```python
class DocumentRetriever(ABC):
    async def search(query: str, top_k: int = 3) -> List[Document]
    async def add_documents(docs: List[Document]) -> None
```

**Implementations**:
- **FAISSRetriever** (POC): Vector similarity with sentence-transformers
- **BM25Retriever** (Future): Keyword-based exact matching
- **HybridRetriever** (Future): FAISS + BM25 + reranking

**Document Structure**:
```python
@dataclass
class Document:
    content: str
    metadata: dict
    id: Optional[str] = None
```

### 3. LangGraph State Management

**State Schema**:
```python
class MedicalChatState(MessagesState):
    session_id: str
    assigned_agent: Optional[str]
    metadata: dict
```

**State Flow**:
1. Request arrives with session_id + message
2. Load session from SessionStore
3. If assigned_agent is None → route to supervisor
4. If assigned_agent is set → route directly to agent
5. Agent processes and returns response
6. Update session and save

### 4. Agent System

#### Supervisor Agent
**Responsibility**: Classify user intent on first message

**Input**: User's first message
**Output**: Agent assignment ("emotional_support" | "rag_agent")

**Logic**:
- Uses LLM with structured output (Pydantic model)
- Classification categories:
  - Emotional support: "I'm feeling sad", "Need someone to talk to"
  - Medical information: "What is Sertraline?", "Side effects of Lexapro"

**Implementation Pattern**:
```python
class AgentClassification(BaseModel):
    agent: Literal["emotional_support", "rag_agent"]
    reasoning: str

def supervisor_node(state: MedicalChatState) -> Command:
    response = llm.with_structured_output(AgentClassification).invoke(...)
    return Command(
        update={"assigned_agent": response.agent},
        goto=response.agent
    )
```

#### Emotional Support Agent
**Responsibility**: Provide empathetic, supportive conversation

**System Prompt**: Focus on empathy, active listening, validation
**Tools**: None (conversational only)
**Pattern**: ReAct agent or simple LLM call

**Key Behaviors**:
- Acknowledge emotions
- Validate feelings
- Provide coping suggestions
- Encourage professional help when appropriate

#### RAG Agent
**Responsibility**: Answer medical questions using knowledge base

**System Prompt**: Professional, evidence-based, cite sources
**Tools**: `search_medical_docs` (uses DocumentRetriever)
**Pattern**: ReAct agent with tool calling

**Key Behaviors**:
- Search knowledge base for relevant info
- Synthesize from multiple sources
- Include disclaimers (not medical advice)
- Provide structured information

**Tool Definition**:
```python
@tool
async def search_medical_docs(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """Search medical knowledge base for information."""
    retriever = state["retriever"]
    docs = await retriever.search(query, top_k=3)
    return format_documents(docs)
```

### 5. Graph Construction

**Graph Flow**:
```python
builder = StateGraph(MedicalChatState)

# Add nodes
builder.add_node("check_assignment", check_assignment_node)
builder.add_node("supervisor", supervisor_node)
builder.add_node("emotional_support", emotional_support_node)
builder.add_node("rag_agent", rag_agent_node)

# Define routing
builder.add_edge(START, "check_assignment")
builder.add_conditional_edges(
    "check_assignment",
    route_based_on_assignment,
    {
        "supervisor": "supervisor",
        "emotional_support": "emotional_support",
        "rag_agent": "rag_agent"
    }
)
builder.add_edge("supervisor", END)
builder.add_edge("emotional_support", END)
builder.add_edge("rag_agent", END)

graph = builder.compile(checkpointer=MemorySaver())
```

**Routing Logic**:
```python
def route_based_on_assignment(state: MedicalChatState) -> str:
    if state["assigned_agent"] is None:
        return "supervisor"
    return state["assigned_agent"]
```

### 6. FastAPI Integration

**Endpoints**:
- `POST /chat`: Main conversation endpoint
- `GET /health`: Service health check

**Request Flow**:
1. Receive ChatRequest (session_id + message)
2. Load session from SessionStore
3. Construct graph state
4. Invoke graph with state
5. Extract response from graph output
6. Update session in SessionStore
7. Return ChatResponse

**Session Management**:
- Thread ID for LangGraph = session_id
- Checkpointer maintains message history
- SessionStore maintains assigned_agent

## Data Flow

### First Message (New Session)
```
User Message
    ↓
FastAPI /chat endpoint
    ↓
SessionStore.get_session(session_id) → None
    ↓
Create initial state: assigned_agent=None
    ↓
Graph.invoke(state, thread_id=session_id)
    ↓
check_assignment → "supervisor"
    ↓
supervisor_node → classify → assign agent
    ↓
SessionStore.save_session(session_id, assigned_agent="rag_agent")
    ↓
Return response
```

### Subsequent Messages
```
User Message
    ↓
FastAPI /chat endpoint
    ↓
SessionStore.get_session(session_id) → SessionData(assigned_agent="rag_agent")
    ↓
Create state with assigned_agent="rag_agent"
    ↓
Graph.invoke(state, thread_id=session_id)
    ↓
check_assignment → "rag_agent" (direct routing)
    ↓
rag_agent_node → search docs → respond
    ↓
SessionStore.save_session(session_id, updated_at=now)
    ↓
Return response
```

## Extension Points

### Adding New Agents

1. Create agent module in `app/agents/`
2. Define agent function with signature:
   ```python
   def new_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
       ...
   ```
3. Update supervisor classification to include new agent
4. Add node to graph builder
5. Update routing logic

**Example**: Adding diagnosis agent:
```python
# app/agents/diagnosis.py
def diagnosis_agent_node(state: MedicalChatState) -> Command:
    # Diagnosis logic
    return Command(goto=END, update={"messages": [response]})

# app/graph/builder.py
builder.add_node("diagnosis", diagnosis_agent_node)
# Update supervisor to classify "diagnosis" intent
# Update routing to include "diagnosis" option
```

### Switching Storage Backends

**Redis Example**:
```python
# app/core/session_store.py
class RedisSessionStore(SessionStore):
    def __init__(self, redis_url: str, ttl: int = 3600):
        self.redis = aioredis.from_url(redis_url)
        self.ttl = ttl

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        data = await self.redis.get(f"session:{session_id}")
        return SessionData.parse_raw(data) if data else None

    async def save_session(self, session_id: str, data: SessionData) -> None:
        await self.redis.setex(
            f"session:{session_id}",
            self.ttl,
            data.json()
        )
```

**Usage** (dependency injection in FastAPI):
```python
# app/main.py
def get_session_store() -> SessionStore:
    if settings.use_redis:
        return RedisSessionStore(settings.redis_url)
    return InMemorySessionStore()
```

### Switching Retrieval Methods

**BM25 Example**:
```python
from rank_bm25 import BM25Okapi

class BM25Retriever(DocumentRetriever):
    def __init__(self):
        self.documents: List[Document] = []
        self.bm25: Optional[BM25Okapi] = None

    async def add_documents(self, docs: List[Document]) -> None:
        self.documents = docs
        tokenized = [doc.content.split() for doc in docs]
        self.bm25 = BM25Okapi(tokenized)

    async def search(self, query: str, top_k: int = 3) -> List[Document]:
        scores = self.bm25.get_scores(query.split())
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [self.documents[i] for i in top_indices]
```

## Performance Considerations

### Async Operations
- All I/O operations (session, retriever, LLM) are async
- FastAPI handles concurrent requests efficiently
- No blocking calls in critical path

### Caching
- LangGraph checkpointer caches message history
- Embedding model loaded once at startup
- Session data cached in memory (or Redis)

### Scalability
- Stateless FastAPI (horizontal scaling ready)
- Session state in external store (Redis/Postgres)
- LangGraph checkpointer can use Postgres backend

### Resource Management
- Use FastAPI lifespan for model initialization
- Lazy load embedding models
- Connection pooling for database backends

## Security Considerations

1. **API Key Management**: Environment variables, never commit
2. **Session Validation**: Verify session_id format
3. **Rate Limiting**: Add middleware for production
4. **Input Sanitization**: Validate message content
5. **HTTPS**: Always use in production
6. **CORS**: Configure allowed origins

## Testing Strategy

### Unit Tests
- Agent classification logic
- Session store operations
- Retriever search accuracy
- State transitions

### Integration Tests
- Full graph execution flow
- Multi-turn conversations
- Session persistence
- API endpoints

### Test Fixtures
- Mock LLM responses
- Sample documents
- Predefined sessions
- Test database instances

## Deployment

### Development
```bash
uvicorn app.main:app --reload --port 8000
```

### Production
```bash
# With gunicorn + uvicorn workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Monitoring & Observability

### Metrics to Track
- Response latency per agent
- Session creation rate
- Agent assignment distribution
- Retrieval accuracy
- LLM token usage

### Logging
- Structured JSON logs
- Request/response correlation IDs
- Agent transitions
- Error traces

### Health Checks
- LLM connectivity
- Retriever model loaded
- Session store accessible
- Database connections

## Future Enhancements

1. **Additional Agents**: Diagnosis, Find Doctor, Appointment Booking
2. **Hybrid Retrieval**: FAISS + BM25 + reranking
3. **Conversation Memory**: Long-term user preferences
4. **Multi-turn Context**: Better context tracking
5. **Streaming Responses**: Real-time token streaming
6. **User Authentication**: Secure user sessions
7. **Analytics Dashboard**: Usage insights
8. **A/B Testing**: Agent performance comparison
