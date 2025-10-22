# Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd langgraph/
pip install -r requirements.txt
# Or with Poetry: poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:
```
OPENAI_API_KEY=your-key-here
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

You should see:
```
🚀 Initializing Medical Chatbot application...
✅ Session store initialized
📚 Loading medical documents...
✅ Loaded 5 medical documents into retriever
✅ Medical chatbot graph compiled
🎉 Application startup complete!
```

### 4. Test It!

**Option A: Web Browser**
- Open http://localhost:8000/docs
- Click "Try it out" on `/chat` endpoint
- Use this request:
```json
{
  "session_id": "test-1",
  "message": "What is Sertraline?"
}
```

**Option B: Command Line**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-1","message":"What is Sertraline?"}'
```

**Option C: Python Script**
```bash
python example_usage.py
```

## What to Test

### 1. Medical Information (Routes to RAG Agent)
```json
{
  "session_id": "test-medical-1",
  "message": "What is Sertraline used for?"
}
```

### 2. Emotional Support (Routes to Emotional Agent)
```json
{
  "session_id": "test-emotional-1",
  "message": "I'm feeling anxious today"
}
```

### 3. Multi-turn Conversation
Send multiple messages with same `session_id` - agent assignment persists!

## Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific tests
pytest tests/unit/test_session_store.py -v
```

## Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### "Connection refused" when testing
Make sure server is running:
```bash
uvicorn app.main:app --reload --port 8000
```

### LLM errors
Check your `.env` file has correct `OPENAI_API_KEY`

## Next Steps

- 📖 Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- 🛠️ Check [IMPLEMENTATION.md](IMPLEMENTATION.md) for customization
- 📋 Review [README.md](README.md) for full documentation

## Quick Architecture Overview

```
User Message
    ↓
FastAPI /chat endpoint
    ↓
Session Check (first message or returning?)
    ↓
    ├─ First Message → Supervisor classifies intent
    │                   ↓
    │   ┌──────────────┴──────────────┐
    │   ↓                              ↓
    │   Emotional Support          RAG Agent
    │   (empathy, listening)       (searches medical docs)
    │
    └─ Subsequent Messages → Direct to assigned agent

All responses saved with session_id
```

## File Structure
```
langgraph/
├── app/               # Application code
│   ├── main.py       # FastAPI app (START HERE)
│   ├── agents/       # Supervisor, emotional, RAG agents
│   ├── graph/        # LangGraph state & builder
│   └── core/         # Session store, retriever
├── tests/            # Unit & integration tests
├── data/             # Mental health meds (5 sample docs)
├── .env              # Your config (create from .env.example)
└── README.md         # Full documentation
```

## Example Output

**Emotional Support:**
```
User: "I'm feeling anxious"
Agent: "I hear you, and it's completely understandable to feel
        anxious sometimes. Would you like to talk about what's
        contributing to these feelings? I'm here to listen."
```

**Medical Info:**
```
User: "What is Sertraline?"
Agent: "Sertraline (Zoloft) is an SSRI used to treat depression,
        anxiety disorders, OCD, PTSD, and panic disorder. Typical
        dosage: 50-200mg daily. ⚕️ Disclaimer: This is educational
        information only..."
```

---

**You're all set!** 🚀 Start the server and try the examples.
