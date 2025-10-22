# 醫療聊天機器人架構

## 概述

這是一個使用 LangGraph 0.6.0 建構的多代理醫療聊天機器人系統,專為心理健康支援和藥物資訊檢索而設計。該系統使用會話黏性路由模式,其中第一條訊息會分類使用者意圖並為整個會話分配適當的代理。

## 核心原則

1. **會話黏性路由**:一旦會話被分類,所有後續訊息將直接傳送到分配的代理
2. **抽象介面**:輕鬆從記憶體遷移到生產資料庫
3. **可擴展的檢索**:在不更改代理程式碼的情況下切換 FAISS → BM25 → 混合模式
4. **型別安全**:完整的 Pydantic v2 模型和 mypy 合規性
5. **非同步優先**:所有 I/O 操作都是非同步的以實現高效能

## 架構圖

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

## 元件架構

### 1. 會話管理層

**目的**:跨請求追蹤使用者會話和分配的代理

**介面**:`SessionStore`(抽象基底類別)
```python
class SessionStore(ABC):
    async def get_session(session_id: str) -> Optional[SessionData]
    async def save_session(session_id: str, data: SessionData) -> None
    async def delete_session(session_id: str) -> None
```

**實作**:
- **InMemorySessionStore**(概念驗證):使用 threading.Lock 的字典,基於 TTL 的過期
- **RedisSessionStore**(未來):快速、分散式、TTL 支援
- **PostgresSessionStore**(未來):結構化查詢、ACID 合規性

**SessionData 結構**:
```python
@dataclass
class SessionData:
    session_id: str
    assigned_agent: Optional[str]  # "emotional_support" | "rag_agent" | None
    metadata: Dict
    created_at: datetime
    updated_at: datetime
```

### 2. 文件檢索層

**目的**:靈活搜尋醫療知識庫

**介面**:`DocumentRetriever`(抽象基底類別)
```python
class DocumentRetriever(ABC):
    async def search(query: str, top_k: int = 3) -> List[Document]
    async def add_documents(docs: List[Document]) -> None
```

**實作**:
- **FAISSRetriever**(概念驗證):使用 sentence-transformers 的向量相似度
- **BM25Retriever**(未來):基於關鍵字的精確匹配
- **HybridRetriever**(未來):FAISS + BM25 + 重新排序

**Document 結構**:
```python
@dataclass
class Document:
    content: str
    metadata: dict
    id: Optional[str] = None
```

### 3. LangGraph 狀態管理

**狀態模式**:
```python
class MedicalChatState(MessagesState):
    session_id: str
    assigned_agent: Optional[str]
    metadata: dict
```

**狀態流程**:
1. 請求到達,包含 session_id + message
2. 從 SessionStore 載入會話
3. 如果 assigned_agent 為 None → 路由到監督者
4. 如果 assigned_agent 已設定 → 直接路由到代理
5. 代理處理並返回回應
6. 更新會話並儲存

### 4. 代理系統

#### 監督者代理
**責任**:在第一條訊息上分類使用者意圖

**輸入**:使用者的第一條訊息
**輸出**:代理分配("emotional_support" | "rag_agent")

**邏輯**:
- 使用具有結構化輸出的 LLM(Pydantic 模型)
- 分類類別:
  - 情緒支援:「我感到悲傷」、「需要有人聊聊」
  - 醫療資訊:「什麼是血清素?」、「樂復得的副作用」

**實作模式**:
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

#### 情緒支援代理
**責任**:提供同理心、支援性對話

**系統提示**:專注於同理心、積極傾聽、驗證
**工具**:無(僅對話)
**模式**:ReAct 代理或簡單 LLM 呼叫

**關鍵行為**:
- 確認情緒
- 驗證感受
- 提供應對建議
- 在適當時鼓勵尋求專業協助

#### RAG 代理
**責任**:使用知識庫回答醫療問題

**系統提示**:專業、基於證據、引用來源
**工具**:`search_medical_docs`(使用 DocumentRetriever)
**模式**:具有工具呼叫的 ReAct 代理

**關鍵行為**:
- 搜尋知識庫以獲取相關資訊
- 從多個來源綜合資訊
- 包含免責聲明(非醫療建議)
- 提供結構化資訊

**工具定義**:
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

### 5. 圖形建構

**圖形流程**:
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

**路由邏輯**:
```python
def route_based_on_assignment(state: MedicalChatState) -> str:
    if state["assigned_agent"] is None:
        return "supervisor"
    return state["assigned_agent"]
```

### 6. FastAPI 整合

**端點**:
- `POST /chat`:主要對話端點
- `GET /health`:服務健康檢查

**請求流程**:
1. 接收 ChatRequest(session_id + message)
2. 從 SessionStore 載入會話
3. 建構圖形狀態
4. 使用狀態呼叫圖形
5. 從圖形輸出中提取回應
6. 在 SessionStore 中更新會話
7. 返回 ChatResponse

**會話管理**:
- LangGraph 的執行緒 ID = session_id
- Checkpointer 維護訊息歷史
- SessionStore 維護 assigned_agent

## 資料流

### 第一條訊息(新會話)
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

### 後續訊息
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

## 擴展點

### 新增代理

1. 在 `app/agents/` 中建立代理模組
2. 定義具有以下簽章的代理函式:
   ```python
   def new_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
       ...
   ```
3. 更新監督者分類以包含新代理
4. 將節點新增到圖形建構器
5. 更新路由邏輯

**範例**:新增診斷代理:
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

### 切換儲存後端

**Redis 範例**:
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

**使用**(FastAPI 中的依賴注入):
```python
# app/main.py
def get_session_store() -> SessionStore:
    if settings.use_redis:
        return RedisSessionStore(settings.redis_url)
    return InMemorySessionStore()
```

### 切換檢索方法

**BM25 範例**:
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

## 效能考量

### 非同步操作
- 所有 I/O 操作(會話、檢索器、LLM)都是非同步的
- FastAPI 有效處理並發請求
- 關鍵路徑中無阻塞呼叫

### 快取
- LangGraph checkpointer 快取訊息歷史
- 嵌入模型在啟動時載入一次
- 會話資料在記憶體(或 Redis)中快取

### 可擴展性
- 無狀態 FastAPI(準備水平擴展)
- 外部儲存中的會話狀態(Redis/Postgres)
- LangGraph checkpointer 可以使用 Postgres 後端

### 資源管理
- 使用 FastAPI lifespan 進行模型初始化
- 延遲載入嵌入模型
- 資料庫後端的連線池

## 安全性考量

1. **API 金鑰管理**:環境變數,永不提交
2. **會話驗證**:驗證 session_id 格式
3. **速率限制**:為生產環境新增中介軟體
4. **輸入清理**:驗證訊息內容
5. **HTTPS**:在生產環境中始終使用
6. **CORS**:配置允許的來源

## 測試策略

### 單元測試
- 代理分類邏輯
- 會話儲存操作
- 檢索器搜尋準確性
- 狀態轉換

### 整合測試
- 完整圖形執行流程
- 多輪對話
- 會話持久性
- API 端點

### 測試夾具
- 模擬 LLM 回應
- 範例文件
- 預定義會話
- 測試資料庫實例

## 部署

### 開發環境
```bash
uvicorn app.main:app --reload --port 8000
```

### 生產環境
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

## 監控與可觀測性

### 要追蹤的指標
- 每個代理的回應延遲
- 會話建立速率
- 代理分配分布
- 檢索準確性
- LLM token 使用量

### 日誌記錄
- 結構化 JSON 日誌
- 請求/回應相關 ID
- 代理轉換
- 錯誤追蹤

### 健康檢查
- LLM 連線
- 檢索器模型已載入
- 會話儲存可存取
- 資料庫連線

## 未來改進

1. **額外代理**:診斷、尋找醫生、預約掛號
2. **混合檢索**:FAISS + BM25 + 重新排序
3. **對話記憶**:長期使用者偏好
4. **多輪上下文**:更好的上下文追蹤
5. **串流回應**:即時 token 串流
6. **使用者認證**:安全的使用者會話
7. **分析儀表板**:使用洞察
8. **A/B 測試**:代理效能比較
