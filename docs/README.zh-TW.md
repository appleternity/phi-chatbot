# 醫療聊天機器人 - 基於 LangGraph 的多代理系統

使用 **LangGraph 0.6.0** 打造的生產就緒多代理醫療聊天機器人，專為心理健康支援和藥物資訊檢索而設計。

## 🎯 功能特色

- **🤖 多代理架構**：基於監督者的路由系統，引導至專業代理
- **💬 情緒支援代理**：為心理健康支援提供同理心對話
- **📚 RAG 代理**：使用向量搜尋（FAISS）進行醫療資訊檢索
- **🔄 會話管理**：持久化對話狀態與會話黏性路由
- **⚡ FastAPI 後端**：高效能非同步 API，提供 OpenAPI 文件
- **🧪 完整測試**：使用 pytest 進行單元和整合測試
- **🔌 可擴展設計**：抽象介面讓後端切換更容易

## 🏗️ 架構

```
使用者訊息 → FastAPI
    ↓
會話管理器（檢查會話是否存在）
    ↓
LangGraph 路由器
    ├─ 首次訊息 → 監督者（分類意圖）
    │   ├─ 需要情緒支援 → 情緒支援代理
    │   └─ 需要醫療資訊 → RAG 代理（搜尋知識庫）
    └─ 後續訊息 → 直接路由至已指派的代理
```

**核心設計模式**：
- **會話黏性路由**：一旦分類完成，所有訊息都會路由至相同代理
- **抽象介面**：從記憶體儲存輕鬆遷移至生產環境資料庫
- **依賴注入**：清晰的架構與可測試元件

## 📋 前置需求

- Python 3.11+
- OpenRouter API 金鑰（或相容 OpenAI 的端點）
- Poetry（推薦）或 pip

## 🚀 快速開始

### 1. 安裝

```bash
# 切換至專案目錄
cd langgraph/

# 使用 Poetry 安裝依賴
poetry install

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置

```bash
# 複製環境變數範本
cp .env.example .env

# 編輯 .env 填入您的憑證
nano .env
```

**必要的環境變數**：
```bash
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=your-openrouter-api-key-here
MODEL_NAME=qwen/qwen3-max

# 選用
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
```

### 3. 執行應用程式

```bash
# 使用 Poetry
poetry run uvicorn app.main:app --reload --port 8000

# 或直接執行
python -m uvicorn app.main:app --reload --port 8000
```

API 將可在以下位址存取：
- **API**：http://localhost:8000
- **文件**：http://localhost:8000/docs (Swagger UI)
- **ReDoc**：http://localhost:8000/redoc

## 📖 使用範例

### 健康檢查

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 聊天 - 情緒支援

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-123",
    "message": "我今天感到非常焦慮"
  }'
```

```json
{
  "session_id": "user-123",
  "message": "我聽到您的感受了，感到焦慮是完全可以理解的。您願意談談是什麼讓您有這樣的感覺嗎？我在這裡傾聽。",
  "agent": "emotional_support",
  "metadata": {
    "classification_reasoning": "使用者表達情緒困擾",
    "classification_confidence": 0.95
  }
}
```

### 聊天 - 醫療資訊

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-456",
    "message": "Sertraline 是用來治療什麼的？"
  }'
```

```json
{
  "session_id": "user-456",
  "message": "根據知識庫：\n\nSertraline（商品名 Zoloft）是一種 SSRI（選擇性血清素回收抑制劑），用於治療：\n- 重度憂鬱症\n- 焦慮症\n- 強迫症（OCD）\n- 創傷後壓力症候群（PTSD）\n- 恐慌症\n\n典型劑量：每日 50-200mg\n\n⚕️ 免責聲明：這僅為教育資訊...",
  "agent": "rag_agent",
  "metadata": {...}
}
```

### Python 客戶端範例

```python
import httpx
import asyncio

async def chat_example():
    async with httpx.AsyncClient() as client:
        # 情緒支援對話
        response1 = await client.post(
            "http://localhost:8000/chat",
            json={
                "session_id": "python-user-1",
                "message": "我正在與憂鬱症奮鬥"
            }
        )
        print(response1.json()["message"])

        # 同一會話中的後續訊息
        response2 = await client.post(
            "http://localhost:8000/chat",
            json={
                "session_id": "python-user-1",
                "message": "最近真的很艱難"
            }
        )
        print(response2.json()["message"])

asyncio.run(chat_example())
```

## 🧪 測試

```bash
# 執行所有測試
poetry run pytest

# 執行並產生覆蓋率報告
poetry run pytest --cov=app --cov-report=html

# 僅執行單元測試
poetry run pytest tests/unit/

# 僅執行整合測試
poetry run pytest tests/integration/ -m integration

# 執行特定測試檔案
poetry run pytest tests/unit/test_session_store.py -v
```

**測試覆蓋率**：
- ✅ 會話儲存操作（建立、更新、過期、刪除）
- ✅ 文件檢索器（搜尋、相關性、top-k）
- ✅ 圖執行流程（分類、路由、持久化）
- ✅ API 端點（健康檢查、聊天、多輪對話、並發會話）

## 📁 專案結構

```
langgraph/
├── app/
│   ├── main.py                 # FastAPI 應用程式
│   ├── config.py               # 環境配置
│   ├── models.py               # Pydantic API 模型
│   ├── agents/
│   │   ├── supervisor.py       # 意圖分類器
│   │   ├── emotional_support.py # 同理心代理
│   │   ├── rag_agent.py        # 醫療資訊代理
│   │   └── base.py             # 共用工具
│   ├── graph/
│   │   ├── state.py            # 狀態定義
│   │   └── builder.py          # 圖建構
│   ├── core/
│   │   ├── session_store.py    # 會話管理
│   │   └── retriever.py        # 文件檢索
│   └── utils/
│       ├── prompts.py          # 代理提示詞
│       └── data_loader.py      # 資料載入
├── tests/
│   ├── unit/                   # 單元測試
│   └── integration/            # 整合測試
├── data/
│   └── mental_health_meds.json # 範例藥物資料
├── docs/
│   ├── ARCHITECTURE.md         # 架構文件
│   └── IMPLEMENTATION.md       # 實作指南
├── pyproject.toml              # 依賴套件
└── README.md                   # 本檔案
```

## 🔧 配置選項

| 變數 | 預設值 | 說明 |
|----------|---------|-------------|
| `OPENAI_API_BASE` | https://openrouter.ai/api/v1 | LLM API 端點 |
| `OPENAI_API_KEY` | *必填* | API 金鑰 |
| `MODEL_NAME` | qwen/qwen3-max | 模型識別碼 |
| `LOG_LEVEL` | INFO | 日誌等級 |
| `SESSION_TTL_SECONDS` | 3600 | 會話過期時間 |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Sentence transformer 模型 |
| `TOP_K_DOCUMENTS` | 3 | 檢索文件數量 |

## 🎨 自訂

### 新增代理

1. **建立代理檔案**：`app/agents/diagnosis_agent.py`

```python
def diagnosis_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    # 您的代理邏輯
    return Command(goto=END, update={"messages": [response]})
```

2. **更新監督者**：在分類類型中新增 "diagnosis"

3. **加入圖中**：在 `app/graph/builder.py`：

```python
builder.add_node("diagnosis", diagnosis_agent_node)
builder.add_conditional_edges("supervisor", ...)
```

### 切換至 PostgreSQL 會話

實作 `PostgresSessionStore`：

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

更新 `app/main.py`：

```python
if settings.use_postgres:
    app_state["session_store"] = PostgresSessionStore(settings.database_url)
```

### 切換至 BM25 檢索

在 `app/core/retriever.py` 中實作 `BM25Retriever`，遵循抽象介面。

## 📊 監控與日誌

應用程式使用結構化日誌：

```python
# 日誌格式
2025-01-20 10:30:45 - app.main - INFO - 📨 收到來自會話的訊息：user-123
2025-01-20 10:30:45 - app.agents.supervisor - INFO - 會話 user-123：分類為 rag_agent（信心度：0.95）
2025-01-20 10:30:46 - app.main - INFO - ✅ rag_agent 已為會話 user-123 產生回應
```

**監控指標**：
- 每個代理的回應延遲
- 會話建立/檢索率
- 代理分類分布
- RAG 檢索成功率

## 🚢 部署

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# 複製應用程式
COPY . .

# 執行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

建構並執行：

```bash
docker build -t medical-chatbot .
docker run -p 8000:8000 --env-file .env medical-chatbot
```

### 生產環境考量

- **會話儲存**：使用 Redis 或 PostgreSQL 進行持久化
- **速率限制**：為 API 新增速率限制中介層
- **CORS**：適當配置允許的來源
- **HTTPS**：生產環境務必使用 TLS
- **監控**：設定日誌聚合（ELK、Datadog）
- **擴展**：使用 gunicorn + 多個 uvicorn workers 進行部署

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## 🔐 安全注意事項

- ⚠️ 切勿將 `.env` 或 API 金鑰提交至版本控制
- 🔒 驗證所有使用者輸入（由 Pydantic 處理）
- 🛡️ 在生產環境中新增速率限制
- 🔑 定期輪換 API 金鑰
- 📝 為生產環境實作適當的身份驗證

## 📚 文件

- **[ARCHITECTURE.md](ARCHITECTURE.md)**：詳細的系統架構
- **[ARCHITECTURE.zh-TW.md](ARCHITECTURE.zh-TW.md)**：系統架構（繁體中文）
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**：逐步實作指南
- **[IMPLEMENTATION.zh-TW.md](IMPLEMENTATION.zh-TW.md)**：實作指南（繁體中文）
- **API 文件**：http://localhost:8000/docs（執行時）

## 🤝 貢獻

1. Fork 此儲存庫
2. 建立功能分支
3. 實作您的變更
4. 新增測試
5. 執行測試套件：`pytest`
6. 提交 pull request

## 📝 授權

MIT License - 詳見 LICENSE 檔案

## 🙏 致謝

- **LangGraph**：編排框架
- **FastAPI**：Web 框架
- **FAISS**：向量相似度搜尋
- **OpenRouter**：LLM API 閘道

## 📧 支援

如有問題或疑問：
- 📋 在 GitHub 上開啟 issue
- 📖 查看 `ARCHITECTURE.md` 和 `IMPLEMENTATION.md` 中的文件
- 💬 在 `/docs` 端點查看 API 文件

---

使用 LangGraph 0.6.0 和 FastAPI 以 ❤️ 打造
