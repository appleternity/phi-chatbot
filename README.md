# Medical Chatbot - Multi-Agent System

A production-ready multi-agent medical chatbot built with LangGraph 0.6.0.

## 📚 Documentation

**Choose your language:**
- 🇬🇧 [English Documentation](docs/README.md)
- 🇹🇼 [繁體中文文件](docs/README.zh-TW.md)

## 🚀 Quick Start (5-10 minutes)

**Two setup paths:**
1. **Quick Start (Recommended)**: Restore from backup → 5 minutes
2. **Fresh Install**: Index documents from scratch → 25-40 minutes

### Quick Setup (5 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env: Add OPENROUTER_API_KEY and verify PostgreSQL settings

# 3. Start PostgreSQL with pgvector
docker-compose up -d

# 4. Restore database from backup (includes 1247 pre-indexed chunks)
bash scripts/setup_postgres_with_file.sh backups/medical_knowledge-latest.dump

# 5. Start backend server
python -m app.main

# 6. Start frontend (new terminal)
cd frontend && npm install && npm run dev
```

**Access:**
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:3000
- API Docs: http://localhost:8000/docs

📖 **For detailed setup instructions, troubleshooting, and fresh install:** See [QUICKSTART.md](QUICKSTART.md)

## 📖 Full Documentation

All documentation is available in the `/docs` folder:

| Document | English | 繁體中文 |
|----------|---------|----------|
| Quick Start | [QUICKSTART.md](QUICKSTART.md) | [QUICKSTART.zh-TW.md](docs/QUICKSTART.zh-TW.md) |
| README | [README.md](docs/README.md) | [README.zh-TW.md](docs/README.zh-TW.md) |
| Architecture | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [ARCHITECTURE.zh-TW.md](docs/ARCHITECTURE.zh-TW.md) |
| Implementation | [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | [IMPLEMENTATION.zh-TW.md](docs/IMPLEMENTATION.zh-TW.md) |

See [Documentation Index](docs/INDEX.md) ([中文](docs/INDEX.zh-TW.md)) for complete navigation guide.

## 🎯 Features

- 🤖 Multi-Agent Architecture with LangGraph 0.6.0
- 💬 Emotional Support Agent
- 📚 RAG Agent with PostgreSQL + pgvector semantic search
  - 🔍 Qwen3-Embedding-0.6B for embeddings (MPS/CUDA/CPU)
  - 🎯 Qwen3-Reranker-0.6B for 2-stage retrieval (<2s latency)
  - 🗄️ PostgreSQL 15 with pgvector extension
- 🔄 Session Management
- ⚡ FastAPI Backend
- 🎨 React Frontend with TypeScript
- 🧪 Comprehensive Tests

## 📧 Support

- 📖 See [docs/](docs/) for complete documentation
- 📋 Open an issue on GitHub
- 💬 Check API docs at http://localhost:8000/docs

---

Built with ❤️ using LangGraph 0.6.0 and FastAPI
