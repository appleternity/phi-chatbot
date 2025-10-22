# Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing each component of the medical chatbot system. Follow this guide to build the system from scratch or extend it with new features.

## Prerequisites

- Python 3.11+
- Poetry or pip for dependency management
- OpenRouter API key (or other OpenAI-compatible endpoint)
- Basic understanding of async Python and FastAPI

## Implementation Checklist

- [x] Project structure and dependencies
- [x] Configuration management
- [x] Abstract interfaces (SessionStore, DocumentRetriever)
- [ ] Sample medical data (mental health medications)
- [ ] State definitions for LangGraph
- [ ] Supervisor agent with classification
- [ ] Emotional support agent
- [ ] RAG agent with retriever tool
- [ ] Graph construction with routing logic
- [ ] FastAPI application and endpoints
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation and examples

## Step-by-Step Implementation

### 1. Project Setup

**Status**: ✅ Complete

**Files**:
- `pyproject.toml`: Dependencies and build configuration
- `.env.example`: Environment variable template
- `app/config.py`: Configuration management with pydantic-settings

**Setup**:
```bash
# Install dependencies
poetry install

# Copy environment file
cp .env.example .env

# Edit .env with your OpenRouter API key
nano .env
```

### 2. Create Sample Medical Data

**Status**: ⏳ Pending

**File**: `data/mental_health_meds.json`

**Requirements**:
- 5 mental health medications
- Each with: name, class, uses, dosage, side effects
- JSON format for easy loading

**Implementation**:
```json
[
  {
    "id": "sertraline",
    "name": "Sertraline (Zoloft)",
    "class": "SSRI",
    "uses": "Depression, anxiety disorders, OCD, PTSD, panic disorder",
    "dosage": "50-200mg daily, taken once daily",
    "side_effects": "Nausea, diarrhea, insomnia, sexual dysfunction, dry mouth",
    "warnings": "May increase suicidal thoughts in young adults initially. Do not stop abruptly.",
    "interactions": "MAOIs, blood thinners, NSAIDs"
  },
  ...
]
```

**Loader Function** (`app/utils/data_loader.py`):
```python
import json
from pathlib import Path
from typing import List
from app.core.retriever import Document

async def load_medical_documents() -> List[Document]:
    """Load mental health medication documents from JSON file."""
    data_path = Path(__file__).parent.parent.parent / "data" / "mental_health_meds.json"

    with open(data_path, 'r') as f:
        raw_data = json.load(f)

    documents = []
    for item in raw_data:
        # Create searchable content
        content = f"""
        Medication: {item['name']}
        Class: {item['class']}
        Uses: {item['uses']}
        Dosage: {item['dosage']}
        Side Effects: {item['side_effects']}
        Warnings: {item.get('warnings', '')}
        Interactions: {item.get('interactions', '')}
        """.strip()

        doc = Document(
            id=item['id'],
            content=content,
            metadata=item
        )
        documents.append(doc)

    return documents
```

### 3. Define LangGraph State

**Status**: ⏳ Pending

**File**: `app/graph/state.py`

**Requirements**:
- Extend MessagesState from LangGraph
- Add session tracking fields
- Add assigned agent field

**Implementation**:
```python
from typing import Optional, Annotated
from langgraph.graph import MessagesState, add_messages
from langchain_core.messages import BaseMessage

class MedicalChatState(MessagesState):
    """State for medical chatbot graph.

    Extends MessagesState with session management fields.
    """

    # Session identification
    session_id: str

    # Agent assignment (sticky routing)
    assigned_agent: Optional[str] = None  # "emotional_support" | "rag_agent" | None

    # Additional metadata
    metadata: dict = {}
```

**Usage Notes**:
- `messages` field inherited from MessagesState
- `add_messages` automatically merges new messages
- `session_id` used as LangGraph thread_id
- `assigned_agent` determines routing after first message

### 4. Implement Supervisor Agent

**Status**: ⏳ Pending

**File**: `app/agents/supervisor.py`

**Requirements**:
- Classify user intent from first message
- Use structured output for reliability
- Return agent assignment

**Implementation**:
```python
from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.config import settings

class AgentClassification(BaseModel):
    """Structured output for agent classification."""

    agent: Literal["emotional_support", "rag_agent"] = Field(
        description="The agent to assign based on user intent"
    )
    reasoning: str = Field(
        description="Brief explanation of why this agent was chosen"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in classification (0-1)"
    )

# Initialize LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.1  # Low temperature for consistent classification
)

SUPERVISOR_PROMPT = """You are a medical chatbot supervisor that routes users to the appropriate agent.

Analyze the user's message and determine which agent should handle their conversation:

1. **emotional_support**: For users who need empathy, emotional support, or someone to talk to
   - Examples: "I'm feeling depressed", "I need someone to talk to", "I'm anxious"

2. **rag_agent**: For users seeking medical information about medications or treatments
   - Examples: "What is Sertraline?", "Side effects of Lexapro", "How does Zoloft work?"

User message: {message}

Classify the user's intent and provide your reasoning."""

def supervisor_node(state: MedicalChatState) -> Command[Literal["emotional_support", "rag_agent"]]:
    """Supervisor agent that classifies user intent and assigns appropriate agent.

    This node only runs on the first message in a session.
    """
    # Get the last user message
    last_message = state["messages"][-1]

    # Classify with structured output
    classification = llm.with_structured_output(AgentClassification).invoke(
        SUPERVISOR_PROMPT.format(message=last_message.content)
    )

    # Log classification (useful for debugging)
    print(f"Supervisor classification: {classification.agent} (confidence: {classification.confidence:.2f})")
    print(f"Reasoning: {classification.reasoning}")

    # Return command with assigned agent
    return Command(
        goto=classification.agent,
        update={
            "assigned_agent": classification.agent,
            "metadata": {
                "classification_reasoning": classification.reasoning,
                "classification_confidence": classification.confidence
            }
        }
    )
```

**Testing the Supervisor**:
```python
# Test cases
test_messages = [
    "I'm feeling really sad today",  # Should route to emotional_support
    "What are the side effects of Sertraline?",  # Should route to rag_agent
    "I need someone to talk to",  # Should route to emotional_support
    "Tell me about Lexapro",  # Should route to rag_agent
]
```

### 5. Implement Emotional Support Agent

**Status**: ⏳ Pending

**File**: `app/agents/emotional_support.py`

**Requirements**:
- Empathetic, supportive responses
- Active listening
- Encourage professional help when appropriate
- No tools needed (conversational only)

**Implementation**:
```python
from typing import Literal
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.config import settings

# Initialize LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.7  # Higher temperature for more empathetic, natural responses
)

EMOTIONAL_SUPPORT_PROMPT = """You are a compassionate mental health support companion.

Your role is to:
1. Listen actively and validate feelings
2. Provide empathetic, supportive responses
3. Offer gentle coping strategies when appropriate
4. Encourage professional help for serious concerns
5. Never diagnose or provide medical advice

Guidelines:
- Use warm, understanding language
- Acknowledge emotions without judgment
- Ask thoughtful follow-up questions
- Respect boundaries
- If user mentions self-harm or crisis, encourage immediate professional help (988 Suicide & Crisis Lifeline)

Remember: You are a supportive companion, not a therapist or doctor."""

def emotional_support_node(state: MedicalChatState) -> Command[Literal[END]]:
    """Emotional support agent that provides empathetic conversation.

    This agent focuses on active listening and emotional validation.
    """
    # Construct messages with system prompt
    messages = [
        {"role": "system", "content": EMOTIONAL_SUPPORT_PROMPT}
    ] + state["messages"]

    # Generate response
    response = llm.invoke(messages)

    # Return command with response
    return Command(
        goto=END,
        update={"messages": [response]}
    )
```

**Example Responses**:
```
User: "I'm feeling really anxious today"
Agent: "I hear you, and it's completely understandable to feel anxious sometimes.
       Would you like to talk about what's contributing to these feelings?
       I'm here to listen."

User: "Nobody understands what I'm going through"
Agent: "Feeling isolated and misunderstood can be really painful. Your feelings
       are valid, and I want you to know that you're not alone in experiencing
       these challenges. What's been weighing on your mind?"
```

### 6. Implement RAG Agent

**Status**: ⏳ Pending

**File**: `app/agents/rag_agent.py`

**Requirements**:
- Answer medical questions using knowledge base
- Use DocumentRetriever as tool
- Cite sources
- Include disclaimers

**Implementation**:
```python
from typing import Literal, Annotated, List
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.core.retriever import DocumentRetriever, Document
from app.config import settings

# Initialize LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.3  # Low temperature for factual accuracy
)

@tool
async def search_medical_docs(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """Search the medical knowledge base for information about medications.

    Use this tool to find information about:
    - Medication names and classifications
    - Uses and indications
    - Dosage information
    - Side effects
    - Warnings and interactions

    Args:
        query: Search query (medication name, condition, or question)

    Returns:
        Formatted information from relevant documents
    """
    retriever: DocumentRetriever = state["retriever"]
    docs = await retriever.search(query, top_k=settings.top_k_documents)

    if not docs:
        return "No relevant information found in the knowledge base."

    # Format documents for LLM
    formatted = "# Retrieved Information\n\n"
    for i, doc in enumerate(docs, 1):
        formatted += f"## Source {i}: {doc.metadata.get('name', 'Unknown')}\n\n"
        formatted += f"{doc.content}\n\n"
        formatted += "---\n\n"

    return formatted

RAG_AGENT_PROMPT = """You are a medical information assistant that provides factual information about mental health medications.

Your role is to:
1. Search the knowledge base for relevant information
2. Provide accurate, evidence-based answers
3. Cite sources from the knowledge base
4. Include appropriate disclaimers

Guidelines:
- Always search the knowledge base before answering
- Synthesize information from multiple sources when available
- Be clear about what information comes from which source
- Include disclaimer: "This is educational information only, not medical advice. Consult a healthcare provider for medical decisions."
- If information is not in knowledge base, say so clearly
- Never make up information

Use the search_medical_docs tool to find information."""

def create_rag_agent(retriever: DocumentRetriever):
    """Create RAG agent with access to document retriever."""
    return create_react_agent(
        llm,
        tools=[search_medical_docs],
        prompt=RAG_AGENT_PROMPT,
        state_modifier="You have access to a medical knowledge base. Use the search tool to find accurate information."
    )

def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """RAG agent that answers medical questions using knowledge base.

    This agent uses retrieval-augmented generation to provide accurate information.
    """
    # Inject retriever into state for tool access
    state_with_retriever = {
        **state,
        "retriever": state.get("retriever")  # Retriever injected by graph builder
    }

    # Get RAG agent (created once and cached)
    rag_agent = state.get("_rag_agent")
    if not rag_agent:
        raise ValueError("RAG agent not initialized in state")

    # Invoke agent
    response = rag_agent.invoke(state_with_retriever)

    # Return command with response
    return Command(
        goto=END,
        update={"messages": response["messages"]}
    )
```

**Example Interaction**:
```
User: "What is Sertraline used for?"
Agent: [searches knowledge base]
       "Based on the knowledge base:

        Sertraline (brand name Zoloft) is an SSRI (Selective Serotonin Reuptake Inhibitor)
        used to treat:
        - Major depressive disorder
        - Anxiety disorders
        - Obsessive-compulsive disorder (OCD)
        - Post-traumatic stress disorder (PTSD)
        - Panic disorder

        Typical dosage: 50-200mg daily, taken once per day.

        Source: Medical Knowledge Base - Sertraline entry

        Disclaimer: This is educational information only, not medical advice.
        Consult a healthcare provider for medical decisions."
```

### 7. Build the LangGraph

**Status**: ⏳ Pending

**File**: `app/graph/builder.py`

**Requirements**:
- Construct graph with all nodes
- Implement routing logic
- Handle session assignment
- Initialize with checkpointer

**Implementation**:
```python
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import MedicalChatState
from app.agents.supervisor import supervisor_node
from app.agents.emotional_support import emotional_support_node
from app.agents.rag_agent import rag_agent_node, create_rag_agent
from app.core.retriever import DocumentRetriever

def route_based_on_assignment(
    state: MedicalChatState
) -> Literal["supervisor", "emotional_support", "rag_agent"]:
    """Route to supervisor if no agent assigned, otherwise route to assigned agent."""
    if state.get("assigned_agent") is None:
        return "supervisor"
    return state["assigned_agent"]

def build_medical_chatbot_graph(retriever: DocumentRetriever):
    """Build and compile the medical chatbot graph.

    Args:
        retriever: Document retriever instance for RAG agent

    Returns:
        Compiled LangGraph ready for invocation
    """
    # Create graph builder
    builder = StateGraph(MedicalChatState)

    # Create RAG agent with retriever
    rag_agent = create_rag_agent(retriever)

    # Add nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)

    # Wrap RAG agent node to inject agent instance
    def rag_node_wrapper(state: MedicalChatState):
        state["_rag_agent"] = rag_agent
        state["retriever"] = retriever
        return rag_agent_node(state)

    builder.add_node("rag_agent", rag_node_wrapper)

    # Define edges
    builder.add_edge(START, "supervisor")  # Always start at supervisor for classification

    # Supervisor routes to assigned agent
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        {
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # All agents go to END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)

    # Compile with checkpointer for conversation memory
    graph = builder.compile(checkpointer=MemorySaver())

    return graph
```

**Alternative: Session-Aware Routing**

If you want to skip supervisor on subsequent messages (more efficient):

```python
def build_medical_chatbot_graph_v2(retriever: DocumentRetriever):
    """Build graph with session-aware routing that bypasses supervisor after first message."""
    builder = StateGraph(MedicalChatState)

    # Add routing node
    def check_assignment_node(state: MedicalChatState):
        # Don't modify state, just return current state
        return state

    builder.add_node("check_assignment", check_assignment_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)
    builder.add_node("rag_agent", rag_agent_node)

    # Start at routing node
    builder.add_edge(START, "check_assignment")

    # Route based on assignment
    builder.add_conditional_edges(
        "check_assignment",
        route_based_on_assignment,
        {
            "supervisor": "supervisor",
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # Supervisor assigns and routes
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        {
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # Agents go to END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)

    return builder.compile(checkpointer=MemorySaver())
```

### 8. Implement FastAPI Application

**Status**: ⏳ Pending

**File**: `app/main.py`

**Requirements**:
- POST /chat endpoint
- GET /health endpoint
- Session management integration
- Lifespan for resource management

**Implementation**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.config import settings
from app.core.session_store import SessionStore, InMemorySessionStore, SessionData
from app.core.retriever import DocumentRetriever, FAISSRetriever
from app.graph.builder import build_medical_chatbot_graph
from app.graph.state import MedicalChatState
from app.utils.data_loader import load_medical_documents
import logging

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Global state
app_state = {
    "graph": None,
    "session_store": None,
    "retriever": None
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("Initializing application...")

    # Initialize session store
    app_state["session_store"] = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
    logger.info("Session store initialized")

    # Initialize retriever and load documents
    retriever = FAISSRetriever(embedding_model=settings.embedding_model)
    docs = await load_medical_documents()
    await retriever.add_documents(docs)
    app_state["retriever"] = retriever
    logger.info(f"Loaded {len(docs)} medical documents into retriever")

    # Build graph
    app_state["graph"] = build_medical_chatbot_graph(retriever)
    logger.info("Medical chatbot graph compiled")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    # Cleanup if needed

# Create FastAPI app
app = FastAPI(
    title="Medical Chatbot API",
    description="Multi-agent medical chatbot with emotional support and RAG",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
def get_session_store() -> SessionStore:
    return app_state["session_store"]

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store)
):
    """Main chat endpoint.

    Handles conversation with session-aware routing.
    """
    try:
        # Load or create session
        session = await session_store.get_session(request.session_id)
        if session is None:
            session = SessionData(session_id=request.session_id)
            logger.info(f"Created new session: {request.session_id}")
        else:
            logger.info(f"Loaded existing session: {request.session_id}, assigned_agent: {session.assigned_agent}")

        # Construct graph state
        state = MedicalChatState(
            messages=[{"role": "user", "content": request.message}],
            session_id=request.session_id,
            assigned_agent=session.assigned_agent,
            metadata=session.metadata
        )

        # Invoke graph
        config = {"configurable": {"thread_id": request.session_id}}
        result = await app_state["graph"].ainvoke(state, config)

        # Extract response
        last_message = result["messages"][-1]
        response_text = last_message.content
        assigned_agent = result.get("assigned_agent", session.assigned_agent)

        # Update session
        session.assigned_agent = assigned_agent
        session.metadata = result.get("metadata", session.metadata)
        await session_store.save_session(request.session_id, session)

        return ChatResponse(
            session_id=request.session_id,
            message=response_text,
            agent=assigned_agent or "supervisor",
            metadata=result.get("metadata")
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 9. Testing

#### Unit Tests

**File**: `tests/unit/test_supervisor.py`
```python
import pytest
from app.agents.supervisor import supervisor_node, AgentClassification
from app.graph.state import MedicalChatState

@pytest.mark.asyncio
async def test_supervisor_emotional_classification():
    """Test supervisor classifies emotional support requests correctly."""
    state = MedicalChatState(
        messages=[{"role": "user", "content": "I'm feeling really depressed"}],
        session_id="test-1"
    )

    result = supervisor_node(state)
    assert result.update["assigned_agent"] == "emotional_support"

@pytest.mark.asyncio
async def test_supervisor_rag_classification():
    """Test supervisor classifies medical info requests correctly."""
    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}],
        session_id="test-2"
    )

    result = supervisor_node(state)
    assert result.update["assigned_agent"] == "rag_agent"
```

**File**: `tests/unit/test_session_store.py`
```python
import pytest
from app.core.session_store import InMemorySessionStore, SessionData

@pytest.mark.asyncio
async def test_session_create_and_retrieve():
    """Test creating and retrieving sessions."""
    store = InMemorySessionStore()
    session = SessionData(session_id="test-123", assigned_agent="rag_agent")

    await store.save_session("test-123", session)
    retrieved = await store.get_session("test-123")

    assert retrieved is not None
    assert retrieved.session_id == "test-123"
    assert retrieved.assigned_agent == "rag_agent"

@pytest.mark.asyncio
async def test_session_expiration():
    """Test session TTL expiration."""
    store = InMemorySessionStore(ttl_seconds=1)
    session = SessionData(session_id="test-expire")

    await store.save_session("test-expire", session)

    import asyncio
    await asyncio.sleep(2)

    retrieved = await store.get_session("test-expire")
    assert retrieved is None
```

#### Integration Tests

**File**: `tests/integration/test_graph_flow.py`
```python
import pytest
from app.graph.builder import build_medical_chatbot_graph
from app.core.retriever import FAISSRetriever, Document
from app.graph.state import MedicalChatState

@pytest.fixture
async def mock_retriever():
    """Create mock retriever with sample documents."""
    retriever = FAISSRetriever()
    docs = [
        Document(
            id="sertraline",
            content="Sertraline (Zoloft) is an SSRI used for depression and anxiety. Dosage: 50-200mg daily.",
            metadata={"name": "Sertraline"}
        )
    ]
    await retriever.add_documents(docs)
    return retriever

@pytest.mark.asyncio
async def test_full_conversation_flow(mock_retriever):
    """Test complete conversation flow with classification and response."""
    graph = build_medical_chatbot_graph(mock_retriever)

    # First message
    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}],
        session_id="test-conv-1"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-conv-1"}})

    assert result["assigned_agent"] == "rag_agent"
    assert len(result["messages"]) > 1
    assert "Sertraline" in result["messages"][-1].content
```

**File**: `tests/integration/test_api_endpoints.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_chat_endpoint_new_session(client):
    """Test chat endpoint with new session."""
    response = client.post(
        "/chat",
        json={
            "session_id": "test-api-1",
            "message": "I'm feeling anxious"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-api-1"
    assert data["agent"] in ["emotional_support", "supervisor"]
    assert len(data["message"]) > 0
```

## Common Implementation Patterns

### Adding a New Agent

1. Create agent file: `app/agents/new_agent.py`
2. Define agent function with return type `Command[Literal[END]]`
3. Update supervisor classification to include new agent type
4. Add node to graph in `app/graph/builder.py`
5. Update routing logic
6. Add tests

### Switching to Production Database

1. Implement `PostgresSessionStore` or `RedisSessionStore`
2. Update dependency injection in `app/main.py`:
```python
def get_session_store() -> SessionStore:
    if settings.environment == "production":
        return PostgresSessionStore(settings.database_url)
    return InMemorySessionStore()
```

### Adding Streaming Support

1. Modify graph invocation to use `astream`:
```python
async for chunk in app_state["graph"].astream(state, config):
    yield f"data: {json.dumps(chunk)}\n\n"
```

2. Update endpoint to return `StreamingResponse`

## Troubleshooting

### Issue: Supervisor always classifies wrong
- Check LLM temperature (should be low, 0.1-0.3)
- Verify prompt clarity
- Test with structured output validation

### Issue: RAG agent doesn't find documents
- Verify documents loaded: check startup logs
- Test retriever directly with sample queries
- Check embedding model initialization

### Issue: Sessions not persisting
- Verify TTL settings
- Check SessionStore save operations
- Add logging to track session operations

## Next Steps

1. Complete pending implementations (marked ⏳)
2. Run all tests: `pytest tests/`
3. Test manually with different conversation scenarios
4. Deploy to development environment
5. Monitor and iterate

## Additional Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
