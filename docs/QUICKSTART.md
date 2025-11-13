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

Edit `.env` and add your OpenRouter API key and API bearer token:
```
OPENAI_API_KEY=your-key-here
API_BEARER_TOKEN=your-secure-token-here
```

**Generate API Bearer Token**:
```bash
# Generate a secure 128-character token
openssl rand -hex 64
```

Copy the generated token and paste it as the value for `API_BEARER_TOKEN` in your `.env` file.

### 3. Pre-compute Embeddings (Required)

**⚠️ IMPORTANT**: You must pre-compute embeddings before first run. This takes 10-30 seconds once, then startup is <1 second.

```bash
# Pre-compute medical document embeddings
python -m src.precompute_embeddings

# Pre-compute parenting video embeddings (if using parenting agent)
python -m src.precompute_parenting_embeddings --force
```

Expected output:
```
🚀 Starting embedding pre-computation...
   Model: sentence-transformers/all-MiniLM-L6-v2
   Output: data/embeddings/
📚 Loading documents...
   ✓ Loaded 5 documents
🔢 Computing embeddings...
   ✓ Computed embeddings for 5 documents
💾 Saving artifacts...
   ✓ Saved FAISS index, documents, embeddings, metadata
🎉 Pre-computation completed successfully!
```

These embeddings are saved to disk and loaded instantly on every server startup.

### 4. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

You should see:
```
🚀 Initializing Medical Chatbot application...
✅ Session store initialized
📚 Loading pre-computed medical document embeddings...
✅ Loaded pre-computed medical embeddings from disk
📊 Index contains 5 documents
📚 Loading pre-computed parenting knowledge base...
✅ Loaded parenting knowledge base: 2,847 chunks
✅ Medical chatbot graph compiled with all agents
🎉 Application startup complete!
```

Startup time: **<1 second** (thanks to pre-computed embeddings!)

### 4. Test It!

**Option A: Web Browser**
- Open http://localhost:8000/docs
- Click the **Authorize** button (🔓 icon) at the top right
- Enter your API token (from `.env` file): `Bearer your-api-token-here`
- Click "Authorize" and close the dialog
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
  -H "Authorization: Bearer your-api-token-here" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-1","message":"What is Sertraline?"}'
```

Replace `your-api-token-here` with your actual token from `.env`.

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

### Authentication errors (401 Unauthorized)
**Error**: `{"detail": "Missing Authorization header"}`
- Make sure you include the `Authorization: Bearer <token>` header in your requests
- For Swagger UI: Click the Authorize button and enter your token
- For curl: Add `-H "Authorization: Bearer your-token-here"`

**Error**: `{"detail": "Invalid token format"}`
- Token must be at least 64 hexadecimal characters
- Regenerate token: `openssl rand -hex 32`
- Update `.env` file with new token and restart server

**Error**: `{"detail": "Field required"}` at startup
- `API_BEARER_TOKEN` is missing from `.env` file
- Generate token: `openssl rand -hex 32`
- Add to `.env`: `API_BEARER_TOKEN=your-generated-token`

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
