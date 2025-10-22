# Medical Chatbot - Multi-Agent System

A production-ready multi-agent medical chatbot built with LangGraph 0.6.0.

## 📚 Documentation

**Choose your language:**
- 🇬🇧 [English Documentation](docs/README.md)
- 🇹🇼 [繁體中文文件](docs/README.zh-TW.md)

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run the server
uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs for API documentation.

## 📖 Full Documentation

All documentation is available in the `/docs` folder:

| Document | English | 繁體中文 |
|----------|---------|----------|
| Quick Start | [QUICKSTART.md](docs/QUICKSTART.md) | [QUICKSTART.zh-TW.md](docs/QUICKSTART.zh-TW.md) |
| README | [README.md](docs/README.md) | [README.zh-TW.md](docs/README.zh-TW.md) |
| Architecture | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [ARCHITECTURE.zh-TW.md](docs/ARCHITECTURE.zh-TW.md) |
| Implementation | [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | [IMPLEMENTATION.zh-TW.md](docs/IMPLEMENTATION.zh-TW.md) |

See [Documentation Index](docs/INDEX.md) ([中文](docs/INDEX.zh-TW.md)) for complete navigation guide.

## 🎯 Features

- 🤖 Multi-Agent Architecture with LangGraph 0.6.0
- 💬 Emotional Support Agent
- 📚 RAG Agent with FAISS vector search
- 🔄 Session Management
- ⚡ FastAPI Backend
- 🧪 Comprehensive Tests

## 📧 Support

- 📖 See [docs/](docs/) for complete documentation
- 📋 Open an issue on GitHub
- 💬 Check API docs at http://localhost:8000/docs

---

Built with ❤️ using LangGraph 0.6.0 and FastAPI
