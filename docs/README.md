# Medical Chatbot - Multi-Agent System with LangGraph

A production-ready multi-agent medical chatbot built with **LangGraph 0.6.0**, designed for mental health support and medication information retrieval.

## 🎯 Features

- **🤖 Multi-Agent Architecture**: Supervisor-based routing to specialized agents
- **💬 Emotional Support Agent**: Empathetic conversation for mental health support
- **📚 RAG Agent**: Medical information retrieval with vector search (FAISS)
- **🔄 Session Management**: Persistent conversation state with session-sticky routing
- **⚡ FastAPI Backend**: High-performance async API with OpenAPI documentation
- **🧪 Comprehensive Tests**: Unit and integration tests with pytest
- **🔌 Extensible Design**: Abstract interfaces for easy backend swapping

## 🏗️ Architecture

```
User Message → FastAPI
    ↓
Session Manager (checks if session exists)
    ↓
LangGraph Router
    ├─ First message → Supervisor (classifies intent)
    │   ├─ Emotional support needed → Emotional Support Agent
    │   └─ Medical info needed → RAG Agent (searches knowledge base)
    └─ Subsequent messages → Assigned Agent directly
```

**Key Design Patterns**:
- **Session-Sticky Routing**: Once classified, all messages go to the same agent
- **Abstract Interfaces**: Easy migration from in-memory to production databases
- **Dependency Injection**: Clean architecture with testable components

## 📋 Prerequisites

- Python 3.11+
- OpenRouter API key (or OpenAI-compatible endpoint)
- Poetry (recommended) or pip

## 🚀 Quick Start

### 1. Installation

```bash
# Clone and navigate to directory
cd langgraph/

# Install dependencies with Poetry
poetry install

# Or with pip
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required environment variables**:
```bash
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=your-openrouter-api-key-here
MODEL_NAME=qwen/qwen3-max

# Optional
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
```

### 3. Run the Application

```bash
# With Poetry
poetry run uvicorn app.main:app --reload --port 8000

# Or directly
python -m uvicorn app.main:app --reload --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

## 📖 Usage Examples

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Chat - Emotional Support

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-123",
    "message": "I'\''m feeling really anxious today"
  }'
```

```json
{
  "session_id": "user-123",
  "message": "I hear you, and it's completely understandable to feel anxious sometimes. Would you like to talk about what's contributing to these feelings? I'm here to listen.",
  "agent": "emotional_support",
  "metadata": {
    "classification_reasoning": "User expressing emotional distress",
    "classification_confidence": 0.95
  }
}
```

### Chat - Medical Information

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-456",
    "message": "What is Sertraline used for?"
  }'
```

```json
{
  "session_id": "user-456",
  "message": "Based on the knowledge base:\n\nSertraline (brand name Zoloft) is an SSRI (Selective Serotonin Reuptake Inhibitor) used to treat:\n- Major depressive disorder\n- Anxiety disorders\n- Obsessive-compulsive disorder (OCD)\n- Post-traumatic stress disorder (PTSD)\n- Panic disorder\n\nTypical dosage: 50-200mg daily\n\n⚕️ Disclaimer: This is educational information only...",
  "agent": "rag_agent",
  "metadata": {...}
}
```

### Python Client Example

```python
import httpx
import asyncio

async def chat_example():
    async with httpx.AsyncClient() as client:
        # Emotional support conversation
        response1 = await client.post(
            "http://localhost:8000/chat",
            json={
                "session_id": "python-user-1",
                "message": "I'm struggling with depression"
            }
        )
        print(response1.json()["message"])

        # Follow-up in same session
        response2 = await client.post(
            "http://localhost:8000/chat",
            json={
                "session_id": "python-user-1",
                "message": "It's been really hard lately"
            }
        )
        print(response2.json()["message"])

asyncio.run(chat_example())
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/ -m integration

# Run specific test file
poetry run pytest tests/unit/test_session_store.py -v
```

**Test Coverage**:
- ✅ Session store operations (create, update, expire, delete)
- ✅ Document retriever (search, relevance, top-k)
- ✅ Graph execution flow (classification, routing, persistence)
- ✅ API endpoints (health, chat, multi-turn, concurrent sessions)

## 📁 Project Structure

```
langgraph/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Environment configuration
│   ├── models.py               # Pydantic API models
│   ├── agents/
│   │   ├── supervisor.py       # Intent classifier
│   │   ├── emotional_support.py # Empathy agent
│   │   ├── rag_agent.py        # Medical info agent
│   │   └── base.py             # Shared utilities
│   ├── graph/
│   │   ├── state.py            # State definitions
│   │   └── builder.py          # Graph construction
│   ├── core/
│   │   ├── session_store.py    # Session management
│   │   └── retriever.py        # Document retrieval
│   └── utils/
│       ├── prompts.py          # Agent prompts
│       └── data_loader.py      # Data loading
├── tests/
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── data/
│   └── mental_health_meds.json # Sample medications
├── ARCHITECTURE.md             # Architecture documentation
├── IMPLEMENTATION.md           # Implementation guide
├── pyproject.toml              # Dependencies
└── README.md                   # This file
```

## 🔧 Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_BASE` | https://openrouter.ai/api/v1 | LLM API endpoint |
| `OPENAI_API_KEY` | *required* | API key |
| `MODEL_NAME` | qwen/qwen3-max | Model identifier |
| `LOG_LEVEL` | INFO | Logging level |
| `SESSION_TTL_SECONDS` | 3600 | Session expiration time |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Sentence transformer model |
| `TOP_K_DOCUMENTS` | 3 | Number of docs to retrieve |

## 🎨 Customization

### Adding a New Agent

1. **Create agent file**: `app/agents/diagnosis_agent.py`

```python
def diagnosis_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    # Your agent logic
    return Command(goto=END, update={"messages": [response]})
```

2. **Update supervisor**: Add "diagnosis" to classification types

3. **Add to graph**: In `app/graph/builder.py`:

```python
builder.add_node("diagnosis", diagnosis_agent_node)
builder.add_conditional_edges("supervisor", ...)
```

### Switching to PostgreSQL Sessions

Implement `PostgresSessionStore`:

```python
class PostgresSessionStore(SessionStore):
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_id = $1",
                session_id
            )
            return SessionData(**row) if row else None
```

Update `app/main.py`:

```python
if settings.use_postgres:
    app_state["session_store"] = PostgresSessionStore(settings.database_url)
```

### Switching to BM25 Retrieval

Implement `BM25Retriever` in `app/core/retriever.py` following the abstract interface.

## 📊 Monitoring & Logging

The application uses structured logging:

```python
# Log format
2025-01-20 10:30:45 - app.main - INFO - 📨 Received message from session: user-123
2025-01-20 10:30:45 - app.agents.supervisor - INFO - Session user-123: Classified as rag_agent (confidence: 0.95)
2025-01-20 10:30:46 - app.main - INFO - ✅ Response generated by rag_agent for session: user-123
```

**Metrics to monitor**:
- Response latency per agent
- Session creation/retrieval rates
- Agent classification distribution
- RAG retrieval success rates

## 🚢 Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# Copy application
COPY . .

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t medical-chatbot .
docker run -p 8000:8000 --env-file .env medical-chatbot
```

### Production Considerations

- **Session Store**: Use Redis or PostgreSQL for persistence
- **Rate Limiting**: Add middleware for API rate limits
- **CORS**: Configure allowed origins appropriately
- **HTTPS**: Always use TLS in production
- **Monitoring**: Set up logging aggregation (ELK, Datadog)
- **Scaling**: Deploy with gunicorn + multiple uvicorn workers

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## 🔐 Security Notes

- ⚠️ Never commit `.env` or API keys to version control
- 🔒 Validate all user input (handled by Pydantic)
- 🛡️ Add rate limiting in production
- 🔑 Rotate API keys regularly
- 📝 Implement proper authentication for production

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Detailed system architecture
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Step-by-step implementation guide
- **API Docs**: http://localhost:8000/docs (when running)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests
5. Run test suite: `pytest`
6. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **LangGraph**: Orchestration framework
- **FastAPI**: Web framework
- **FAISS**: Vector similarity search
- **OpenRouter**: LLM API gateway

## 📧 Support

For issues or questions:
- 📋 Open an issue on GitHub
- 📖 Check documentation in `ARCHITECTURE.md` and `IMPLEMENTATION.md`
- 💬 Review API docs at `/docs` endpoint

---

Built with ❤️ using LangGraph 0.6.0 and FastAPI
