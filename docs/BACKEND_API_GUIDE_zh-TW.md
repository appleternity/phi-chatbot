# 後端 API 指南

> **後端功能與架構的完整開發者指南**

## 目錄

1. [概覽](#概覽)
2. [API 端點](#api-端點)
3. [配置系統](#配置系統)
4. [代理系統](#代理系統)
5. [檢索系統](#檢索系統)
6. [狀態管理](#狀態管理)
7. [圖編排](#圖編排)
8. [數據模型](#數據模型)
9. [系統提示詞](#系統提示詞)
10. [數據流](#數據流)
11. [關鍵架構模式](#關鍵架構模式)
12. [部署指南](#部署指南)

---

## 概覽

### 系統架構

這是一個使用 LangGraph 構建的**多代理醫療聊天機器人**,能夠智能地將用戶查詢路由到專業代理:

- **情緒支持代理**: 同理心傾聽與情緒驗證
- **RAG 代理**: 透過知識庫搜索提供醫療資訊檢索
- **育兒代理**: 使用進階 RAG 提供專業兒童發展建議

**核心功能**:
- 會話感知的對話記憶
- 混合向量 + 關鍵字搜索
- 跨編碼器重排序以提高精確度
- 視頻轉錄的層次化文檔分塊
- 可選組件不可用時的優雅降級

**技術堆疊**:
- **框架**: LangGraph, LangChain, FastAPI
- **大語言模型**: OpenRouter API (qwen/qwen3-max)
- **嵌入**: sentence-transformers/all-MiniLM-L6-v2
- **向量搜索**: FAISS
- **關鍵字搜索**: BM25
- **重排序**: Cross-encoder/ms-marco-MiniLM-L-6-v2

---

## API 端點

**文件**: `app/main.py`

### 健康檢查端點

```python
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    用於監控和負載均衡器的健康檢查端點。

    回傳:
        HealthResponse: {"status": "healthy", "version": "0.1.0"}

    性能: ~1ms (無 I/O)
    """
```

### 聊天端點

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_store: Annotated[SessionStore, Depends(get_session_store)]
) -> ChatResponse:
    """
    處理用戶訊息的主要聊天接口。

    參數:
        request: 包含 session_id 和 message 的 ChatRequest
        session_store: 注入的會話儲存依賴

    回傳:
        包含代理回應和元數據的 ChatResponse

    處理流程:
        1. 從 session_store 載入或創建會話
        2. 使用訊息 + 會話元數據構建 MedicalChatState
        3. 使用 thread_id 調用 LangGraph 以實現對話記憶
        4. 從結果的最後一條訊息中提取回應
        5. 更新會話的 assigned_agent 和元數據
        6. 回傳 ChatResponse

    性能: 2-20s,取決於代理和複雜度
    """
```

**請求模型**:
```python
class ChatRequest(BaseModel):
    session_id: str          # 唯一的會話識別碼
    message: str             # 用戶訊息 (最小長度=1)
```

**回應模型**:
```python
class ChatResponse(BaseModel):
    session_id: str          # 回送請求的 session_id
    message: str             # 代理回應
    agent: str               # "supervisor", "emotional_support", "rag_agent", "parenting"
    metadata: Optional[dict] # 分類詳情、來源等
```

### 應用程式生命週期

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命週期處理器 - 在啟動時初始化組件。

    啟動流程:
        1. 使用可配置的 TTL 初始化 InMemorySessionStore
        2. 載入醫療嵌入 (必需 - 若缺失則快速失敗)
        3. 載入育兒嵌入 (可選 - 優雅降級)
        4. 使用所有可用代理構建 LangGraph
        5. 記錄成功啟動日誌

    清理:
        - 在關閉時進行上下文管理器清理
    """
```

**輔助函數**:

| 函數 | 用途 | 行為 |
|------|------|------|
| `_initialize_session_store()` | 創建會話儲存 | 帶 TTL 的記憶體儲存 |
| `_load_medical_retriever()` | 載入醫療知識庫 | 若未找到則快速失敗 |
| `_load_parenting_system()` | 載入育兒知識庫 | 優雅降級 |

---

## 配置系統

**文件**: `app/config.py`

### Settings 類別

```python
class Settings(BaseSettings):
    """
    從環境變數載入的應用程式配置。

    屬性:
        # LLM 配置
        openai_api_base: str              # OpenRouter API 端點
        openai_api_key: str               # API 金鑰 (必需)
        model_name: str                   # "qwen/qwen3-max" (預設)

        # 應用程式設定
        log_level: str                    # "INFO", "DEBUG", "WARNING" 等
        session_ttl_seconds: int          # 會話過期時間 (預設: 3600)
        environment: str                  # "development", "production"

        # 嵌入配置
        embedding_model: str              # 嵌入模型名稱
        embedding_dim: int                # 嵌入維度 (384)

        # 持久化路徑
        index_path: str                   # 醫療嵌入路徑
        parenting_index_path: str         # 育兒嵌入路徑

        # 檢索設定
        top_k_documents: int              # 要檢索的文檔數 (預設: 3)

    配置:
        env_file = ".env"
        env_file_encoding = "utf-8"
    """
```

**用法**:
```python
from app.config import settings

# 存取配置
api_key = settings.openai_api_key
model = settings.model_name
```

**必需的環境變數**:
```bash
OPENAI_API_KEY=your-openrouter-api-key
OPENAI_API_BASE=https://openrouter.ai/api/v1
```

**可選的環境變數**:
```bash
MODEL_NAME=qwen/qwen3-max
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
TOP_K_DOCUMENTS=3
```

---

## 代理系統

### 基礎代理工具

**文件**: `app/agents/base.py`

#### LLM 工廠函數

```python
def create_llm(temperature: float = 0.7) -> BaseChatModel:
    """
    根據環境創建 LLM 實例的工廠函數。

    參數:
        temperature: 回應隨機性 [0.0=確定性, 1.0=創造性]

    回傳:
        BaseChatModel 實例 (測試用 FakeChatModel,生產用 ChatOpenAI)

    行為:
        測試模式 (TESTING=true):
            - 回傳 FakeChatModel (確定性回應)
            - 快 50-100 倍的執行速度
            - 無 API 成本

        生產模式:
            - 回傳配置 OpenRouter 的 ChatOpenAI
            - 真實的 LLM 推理
            - 產生 API 成本

    用法:
        llm = create_llm(temperature=0.1)  # 確定性
        llm = create_llm(temperature=1.0)  # 創造性
    """
```

---

### 監督代理

**文件**: `app/agents/supervisor.py`

#### 目的

使用基於 LLM 的意圖分類將初始用戶訊息路由到最合適的代理。

#### 數據結構

```python
class AgentClassification(BaseModel):
    """
    監督分類的結構化輸出。

    屬性:
        agent: ["emotional_support", "rag_agent", "parenting"] 之一
        reasoning: 分類決策的解釋
        confidence: 分類確定性的評分 [0.0, 1.0]
    """
```

#### 節點函數

```python
def supervisor_node(state: MedicalChatState) -> Command[Literal["emotional_support", "rag_agent", "parenting"]]:
    """
    分類用戶意圖並路由到合適的代理。

    參數:
        state: 包含對話訊息的 MedicalChatState

    回傳:
        包含 goto=<agent_name> 和更新元數據的 Command

    處理流程:
        1. 從狀態中提取最後一條用戶訊息
        2. 使用 SUPERVISOR_PROMPT 調用 LLM 進行分類
        3. 解析結構化輸出 (agent, reasoning, confidence)
        4. 記錄分類決策
        5. 回傳路由到指定代理的 Command

    LLM 配置:
        - Temperature: 0.1 (確定性分類)
        - 結構化輸出: with_structured_output(AgentClassification)

    執行上下文:
        - 僅在會話的第一條訊息時運行
        - 後續訊息直接路由到 assigned_agent

    性能: ~500-1000ms
    """
```

**範例流程**:
```
用戶: "我對我的藥物感到焦慮"
  ↓ supervisor_node
  ↓ LLM 分類
代理: "emotional_support"
理由: "用戶表達情緒困擾"
信心: 0.85
```

---

### 情緒支持代理

**文件**: `app/agents/emotional_support.py`

#### 目的

提供富有同理心的非臨床情緒支持和主動傾聽,無需知識庫檢索。

#### 節點函數

```python
def emotional_support_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    為情緒支持生成富有同理心的回應。

    參數:
        state: 包含對話歷史的 MedicalChatState

    回傳:
        包含代理回應和 goto=END 的 Command

    處理流程:
        1. 使用 EMOTIONAL_SUPPORT_PROMPT 作為系統訊息構建訊息
        2. 使用高溫度調用 LLM 以獲得自然回應
        3. 將回應包裝在 AIMessage 中
        4. 回傳終止對話輪的 Command

    LLM 配置:
        - Temperature: 1.0 (創造性、多樣化、自然的回應)
        - 無工具 (直接生成)

    指導原則:
        - 主動傾聽和同理心
        - 不提供醫療建議
        - 適當時轉介危機資源
        - 鼓勵尋求專業幫助處理嚴重問題

    性能: ~2-5s
    """
```

---

### RAG 代理 (醫療資訊)

**文件**: `app/agents/rag_agent.py`

#### 目的

使用檢索增強生成和知識庫搜索回答醫療問題。

#### 工具定義

```python
@tool
async def search_medical_docs(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """
    搜索醫療知識庫以獲取藥物/治療資訊。

    參數:
        query: 搜索查詢 (藥物名稱、病症、治療等)
        state: 包含檢索器實例的注入狀態

    回傳:
        帶有元數據的檢索文檔格式化字串

    處理流程:
        1. 從注入狀態中提取檢索器
        2. 執行非同步搜索以獲取 top_k 文檔
        3. 使用元數據格式化文檔:
           - 文檔名稱/標題
           - 內容文字
           - 來源資訊
        4. 回傳 LLM 上下文的格式化字串

    代理使用方式:
        代理根據用戶查詢決定何時調用此工具
        工具結果注入到 LLM 上下文中以合成答案

    性能: ~100-300ms (FAISS 搜索)
    """
```

#### 代理創建

```python
def create_rag_agent(retriever: DocumentRetriever):
    """
    使用 search_medical_docs 工具綁定創建 ReAct 代理。

    參數:
        retriever: 醫療知識庫的 FAISSRetriever 實例

    回傳:
        編譯好的 ReAct 代理

    關鍵設計決策: checkpointer=False
        - RAG 代理是無狀態的 (內部圖)
        - 外部圖 (主聊天機器人) 處理對話持久化
        - 防止不可序列化檢索器的序列化錯誤

    架構:
        - ReAct 模式: 推理 + 行動
        - 代理決定何時使用搜索工具
        - 從檢索文檔合成答案

    配置:
        - Temperature: 1.0 (自然語言生成)
        - 系統提示詞: RAG_AGENT_PROMPT
        - 工具: [search_medical_docs]
    """
```

#### 節點函數

```python
def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    使用檢索器注入調用 RAG 代理的包裝器。

    參數:
        state: 包含 rag_agent 和 retriever 的 MedicalChatState

    回傳:
        包含代理回應訊息的 Command

    處理流程:
        1. 從狀態提取 rag_agent (透過閉包捕獲)
        2. 從狀態提取 retriever (透過閉包捕獲)
        3. 為工具注入創建臨時 state_with_retriever
        4. 使用注入狀態調用代理
        5. 提取回應訊息
        6. 回傳 Command(goto=END, update={"messages": response})

    模式: 基於閉包的依賴注入
        - 不可序列化對象 (agent, retriever) 在閉包中
        - 僅可序列化狀態被檢查點儲存

    性能: ~3-8s (檢索 + LLM 合成)
    """
```

**範例流程**:
```
用戶: "美特福明的副作用是什麼?"
  ↓ rag_agent_node
  ↓ 代理決策: 需要搜索
  ↓ search_medical_docs("美特福明副作用")
  ↓ 檢索到 3 篇關於美特福明的文檔
  ↓ LLM 合成帶引用的答案
回應: "美特福明常見的副作用包括胃腸道問題..."
```

---

### 育兒代理 (進階 RAG)

**文件**: `app/agents/parenting_agent.py`

#### 目的

使用具有品質檢查和糾正機制的多步驟檢索增強生成提供專業育兒建議。

#### 架構

```
開始
  ↓
agent_decision (LLM 決定: 檢索或回答?)
  ├─ has_tool_calls → tools (執行搜索)
  │                    ↓
  │                  grade_documents (按相關性過濾)
  │                    ↓
  │                  check_quality (評估檢索)
  │                    ├─ good → generate_answer
  │                    └─ poor → rewrite_query → agent_decision (重試,最多 2 次)
  │
  └─ no_tool_calls → generate_answer (直接回答)

generate_answer
  ↓
confidence_check
  ├─ high (≥0.6) → END
  └─ low → insufficient_info → END
```

#### 狀態定義

**文件**: `app/graph/parenting_state.py`

```python
class ParentingRAGState(MessagesState):
    """
    多步驟育兒 RAG 代理的狀態。

    查詢處理:
        question: str                      # 原始用戶問題
        queries: List[str]                 # 多查詢變體 (未來使用)

    檢索:
        documents: List[Document]          # 原始搜索結果
        filtered_documents: List[Document] # 評分後的文檔

    生成:
        generation: str                    # 最終回應文字

    控制流:
        retrieval_attempts: int            # 當前嘗試次數 (最多 3 次)
        should_rewrite: bool               # 查詢重寫標誌

    品質指標:
        relevance_scores: List[float]      # 每個文檔的評分 [0.0-1.0]
        confidence: float                  # 整體信心 [0.0-1.0]

    元數據:
        sources: List[dict]                # 引用資訊
        user_context: dict                 # 孩子年齡、偏好、歷史
    """
```

#### 節點函數

**1. 代理決策節點**

```python
def agent_decision_node(state: ParentingRAGState) -> dict:
    """
    LLM 決定是否檢索文檔或直接回答。

    參數:
        state: 包含當前問題的 ParentingRAGState

    回傳:
        包含更新訊息的字典 (可能包含工具調用)

    處理流程:
        1. 從狀態提取問題
        2. 使用工具綁定調用 LLM (search_parenting_knowledge)
        3. LLM 決定:
           - 如需知識則調用搜索工具
           - 如問題可直接回答則直接回答
        4. 回傳訊息 (有或無工具調用)

    配置:
        - Temperature: 0.3 (平衡推理)
        - 工具選擇: "auto" (LLM 決定)
    """
```

**2. 工具節點**

```python
def tools_node_factory(retriever, reranker):
    """
    使用依賴注入創建工具執行節點。

    參數:
        retriever: HybridRetriever 實例
        reranker: CrossEncoderReranker 實例

    回傳:
        執行 search_parenting_knowledge 工具的節點函數

    處理流程:
        1. 從訊息中提取工具調用
        2. 將 retriever 和 reranker 注入狀態
        3. 執行工具 (執行混合搜索 + 重排序)
        4. 將文檔儲存在狀態中供下游評分使用
        5. 回傳帶有格式化結果的工具訊息
    """
```

**3. 文檔評分節點**

```python
def grade_documents_node(state: ParentingRAGState) -> dict:
    """
    使用 LLM 評分按相關性過濾檢索到的文檔。

    參數:
        state: 包含檢索文檔的 ParentingRAGState

    回傳:
        包含 filtered_documents 和 relevance_scores 的字典

    處理流程:
        1. 對每個文檔:
           a. 創建 (問題, 文檔) 對
           b. 調用 LLM 進行相關性評分
           c. 解析結構化輸出 (score, reasoning, relevant)
        2. 過濾 score >= 0.5 的文檔
        3. 在狀態中儲存 filtered_documents 和 relevance_scores

    LLM 配置:
        - Temperature: 0.1 (確定性評分)
        - 結構化輸出: RelevanceGrade 模型

    性能: 每個文檔 ~200ms
    """
```

**4. 品質檢查節點**

```python
def check_quality_node(state: ParentingRAGState) -> dict:
    """
    評估檢索品質並決定下一步行動。

    參數:
        state: 包含 filtered_documents 和 scores 的 ParentingRAGState

    回傳:
        包含 should_rewrite 標誌的字典

    品質標準 (所有條件必須為真才是 "good"):
        - 至少 1 個過濾文檔
        - 平均相關性評分 >= 0.6
        - 檢索嘗試次數 < 2

    決策:
        品質好 → should_rewrite = False → 進行生成
        品質差 → should_rewrite = True → 重寫查詢並重試

    性能: <1ms (簡單邏輯)
    """
```

**5. 重寫查詢節點**

```python
def rewrite_query_node(state: ParentingRAGState) -> dict:
    """
    使用 LLM 改進表現不佳的查詢。

    參數:
        state: 包含原始問題的 ParentingRAGState

    回傳:
        包含改進問題和遞增 retrieval_attempts 的字典

    處理流程:
        1. 提取原始問題
        2. 使用查詢改進提示調用 LLM
        3. 生成增強查詢 (更具體、更好的關鍵字)
        4. 使用新問題更新狀態
        5. 遞增 retrieval_attempts 計數器

    LLM 配置:
        - Temperature: 0.3 (受控創造性)

    最大嘗試次數: 2 (防止無限循環)

    性能: ~500-1000ms
    """
```

**6. 生成答案節點**

```python
def generate_answer_node(state: ParentingRAGState) -> dict:
    """
    使用 LLM 從過濾文檔合成答案。

    參數:
        state: 包含 filtered_documents 或為空的 ParentingRAGState

    回傳:
        包含 generation (答案文字) 和 sources 的字典

    處理流程:
        1. 提取問題和 filtered_documents
        2. 將文檔格式化為上下文
        3. 使用 PARENTING_AGENT_PROMPT 調用 LLM
        4. 生成適齡的、基於證據的答案
        5. 提取來源引用
        6. 回傳答案和元數據

    LLM 配置:
        - Temperature: 0.7 (平衡創造性)

    功能:
        - 引用文檔來源
        - 適齡語言
        - 發展背景
        - 可操作的建議

    性能: ~2-5s
    """
```

**7. 信心檢查節點**

```python
def confidence_check_node(state: ParentingRAGState) -> dict:
    """
    使用綜合評分驗證答案信心。

    參數:
        state: 包含 relevance_scores 和 filtered_documents 的 ParentingRAGState

    回傳:
        包含 confidence 評分的字典

    公式:
        confidence = (平均相關性評分 * 0.7) + (min(文檔數/3, 1.0) * 0.3)

    權重:
        - 相關性: 70% (文檔品質)
        - 覆蓋率: 30% (文檔數量,上限為 3)

    閾值:
        - 高信心: >= 0.6 → 回傳答案
        - 低信心: < 0.6 → 回傳 insufficient_info

    性能: <1ms
    """
```

**8. 資訊不足節點**

```python
def insufficient_info_node(state: ParentingRAGState) -> dict:
    """
    信心低時的後備回應。

    參數:
        state: ParentingRAGState

    回傳:
        包含後備訊息的字典

    訊息:
        - 確認問題
        - 解釋資訊有限
        - 建議諮詢兒科醫生或育兒專家
        - 鼓勵提供更多背景資訊後續詢問

    性能: <1ms (靜態回應)
    """
```

#### 工具定義

**文件**: `app/agents/parenting_tools.py`

```python
@tool
async def search_parenting_knowledge(
    query: str,
    state: Annotated[dict, "InjectedState"]
) -> str:
    """
    使用混合檢索 + 重排序搜索育兒知識庫。

    參數:
        query: 育兒相關問題
        state: 包含 retriever 和 reranker 實例的注入狀態

    回傳:
        帶有元數據的 top_k 文檔格式化字串

    處理流程:
        1. 從注入狀態提取 retriever 和 reranker
        2. 混合搜索 (FAISS + BM25):
           - 檢索 top_k * 2 個候選
           - 結合語義和關鍵字匹配
        3. 跨編碼器重排序:
           - 重新評分候選以提高精確度
           - 按相關性保留 top_k
        4. 將文檔儲存在狀態中供下游評分使用
        5. 格式化並回傳文檔,包括:
           - 標題/來源
           - 內容
           - 時間戳 (如果可用)
           - 發言者 (如果來自視頻轉錄)

    配置:
        - top_k: 從設定中獲取 (預設 3)
        - 混合 alpha: 0.5 (平衡向量 + 關鍵字)

    性能: ~500-1500ms (混合搜索 + 重排序)
    """
```

#### 代理創建

```python
def create_parenting_rag_agent(
    retriever: DocumentRetriever,
    reranker: CrossEncoderReranker
) -> StateGraph:
    """
    使用糾正 RAG 創建編譯的多節點 LangGraph。

    參數:
        retriever: HybridRetriever 實例
        reranker: CrossEncoderReranker 實例

    回傳:
        編譯的 StateGraph[ParentingRAGState]

    功能:
        - 8 節點管道帶條件路由
        - 查詢重寫最多 2 次嘗試
        - 基於信心的後備
        - 父子文檔支援
        - 結構化品質檢查

    路由邏輯:
        - agent_decision → [tools OR generate_answer]
        - tools → grade_documents
        - grade_documents → check_quality
        - check_quality → [generate_answer OR rewrite_query]
        - rewrite_query → agent_decision (重試)
        - generate_answer → confidence_check
        - confidence_check → [END OR insufficient_info]

    性能: 5-20s,取決於查詢品質和檢索週期
    """
```

#### 與主圖的整合

```python
def parenting_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """
    主圖整合的包裝器。

    參數:
        state: 來自主圖的 MedicalChatState

    回傳:
        包含更新訊息和 goto=END 的 Command

    處理流程:
        1. 從狀態提取 parenting_agent, retriever, reranker (閉包)
        2. 從 MedicalChatState 創建 ParentingRAGState:
           - 從最後一條訊息提取問題
           - 初始化空欄位
        3. 調用育兒 RAG 代理
        4. 從結果提取最終訊息
        5. 回傳包含更新訊息的 Command

    模式: 圖之間的狀態轉換
        - 主圖使用 MedicalChatState
        - 育兒代理使用 ParentingRAGState
        - 包裝器處理轉換
    """
```

---

## 檢索系統

### FAISS 檢索器 (向量搜索)

**文件**: `app/core/retriever.py`

#### 文檔數據結構

```python
@dataclass
class Document:
    """
    通用文檔表示。

    屬性:
        content: str                      # 文檔文字
        metadata: dict                    # 來源、時間戳等
        id: Optional[str]                 # 唯一識別碼
        parent_id: Optional[str]          # 父塊的參考
        child_ids: List[str]              # 子塊 ID (用於父文檔)
        timestamp_start: Optional[str]    # 視頻時間戳 "HH:MM:SS.mmm"
        timestamp_end: Optional[str]      # 視頻時間戳 "HH:MM:SS.mmm"
    """
```

#### FAISSRetriever 類別

```python
class FAISSRetriever(DocumentRetriever):
    """
    使用 FAISS 和 SentenceTransformers 的向量相似度搜索。

    屬性:
        _model: SentenceTransformer              # 嵌入模型
        _documents: List[Document]               # 已索引文檔
        _embeddings: np.ndarray                  # 嵌入 [N, dim]
        _index: faiss.Index                      # FAISS 索引
        _device: str                             # "mps" 或 "cpu"

    架構:
        - 雙編碼器: 分別編碼查詢和文檔
        - L2 距離度量: 歐氏距離計算相似性
        - Apple Silicon 優化: 支援 MPS 設備
    """
```

#### 關鍵方法

**初始化**

```python
def __init__(self, embedding_model: str):
    """
    使用嵌入模型初始化檢索器。

    參數:
        embedding_model: HuggingFace 模型名稱

    設備檢測:
        1. 檢查 Apple Silicon (MPS) 可用性
        2. 如果 MPS 不可用則退回到 CPU
        3. 記錄設備選擇日誌

    索引狀態: 在添加文檔前為空
    """
```

**添加文檔**

```python
async def add_documents(self, documents: List[Document]) -> None:
    """
    遞增地向索引添加文檔。

    參數:
        documents: 要索引的 Document 對象列表

    處理流程:
        1. 使用 SentenceTransformer 編碼文檔:
           - 批量編碼以提高效率
           - 標準化嵌入 (L2 範數)
        2. 創建或更新 FAISS 索引:
           - IndexFlatL2 用於精確搜索
           - 向索引添加嵌入
        3. 儲存文檔以進行檢索映射
        4. 記錄添加計數日誌

    性能: 每 100 個文檔 ~100ms
    遞增: 可以多次調用
    """
```

**搜索**

```python
async def search(self, query: str, top_k: int = 3) -> List[Document]:
    """
    向量相似度搜索相關文檔。

    參數:
        query: 搜索查詢文字
        top_k: 要檢索的文檔數

    回傳:
        top_k 個最相似的 Document 對象列表

    處理流程:
        1. 使用相同嵌入模型編碼查詢
        2. FAISS 搜索:
           - 查找 k-最近鄰 (L2 距離)
           - 回傳距離和索引
        3. 將索引映射到 Document 對象
        4. 按相似性排序回傳 (距離升序)

    性能: ~10-50ms,取決於索引大小
    算法: 精確搜索 (暴力搜索以確保準確性)
    """
```

**保存索引**

```python
async def save_index(self, path: str) -> None:
    """
    將 FAISS 索引和元數據持久化到磁碟。

    參數:
        path: 保存索引文件的目錄路徑

    保存:
        - faiss_index.pkl: FAISS 索引對象
        - documents.pkl: Document 對象列表
        - embeddings.npy: 嵌入的 NumPy 陣列
        - metadata.json: 模型名稱、時間戳、維度

    處理流程:
        1. 如果目錄不存在則創建
        2. 序列化並保存所有組件
        3. 寫入帶時間戳的元數據
        4. 記錄保存位置日誌

    用例: 為生產部署預計算嵌入
    """
```

**載入索引**

```python
@classmethod
async def load_index(
    cls,
    path: str,
    embedding_model: str
) -> "FAISSRetriever":
    """
    從磁碟載入預計算的 FAISS 索引。

    參數:
        path: 包含索引文件的目錄
        embedding_model: 模型名稱 (必須與保存的索引匹配)

    回傳:
        載入索引的 FAISSRetriever

    驗證:
        - 所有必需文件存在
        - 文檔數 == 嵌入數
        - 嵌入維度一致
        - 模型名稱兼容性 (不匹配時警告)

    引發:
        FileNotFoundError: 如果缺少必需文件
        ValueError: 如果驗證失敗

    性能: ~100-500ms,取決於索引大小
    """
```

---

### 混合檢索器 (向量 + 關鍵字)

**文件**: `app/core/hybrid_retriever.py`

#### 目的

結合 FAISS 向量搜索 (語義) 和 BM25 關鍵字搜索 (詞彙) 以提高召回率和精確度。

#### 類別定義

```python
class HybridRetriever(DocumentRetriever):
    """
    結合語義和詞彙匹配的混合搜索。

    屬性:
        _faiss_retriever: FAISSRetriever       # 語義搜索
        _documents: List[Document]             # 所有已索引文檔
        _bm25_index: BM25Okapi                 # 關鍵字搜索
        _tokenized_corpus: List[List[str]]     # 分詞文檔
        _alpha: float                          # 組合權重 [0, 1]
        _doc_id_to_idx: dict                   # 文檔 ID → 索引映射

    Alpha 參數:
        - 0.0: 純 BM25 (僅關鍵字)
        - 0.5: 平衡混合 (預設)
        - 1.0: 純 FAISS (僅語義)
    """
```

#### 初始化

```python
def __init__(
    self,
    faiss_retriever: FAISSRetriever,
    documents: List[Document],
    alpha: float = 0.5
):
    """
    初始化混合檢索器。

    參數:
        faiss_retriever: 預初始化的 FAISSRetriever
        documents: 所有文檔 (與 FAISS 中相同)
        alpha: 評分組合的權重 (預設 0.5)

    處理流程:
        1. 儲存 FAISS 檢索器和文檔
        2. 為 BM25 分詞文檔
        3. 構建 BM25 索引
        4. 創建 doc_id_to_idx 映射以快速查找

    性能: 1000 個文檔 ~100ms
    """
```

#### 搜索算法

```python
async def search(self, query: str, top_k: int = 3) -> List[Document]:
    """
    結合 FAISS 和 BM25 的混合搜索。

    參數:
        query: 搜索查詢文字
        top_k: 要回傳的文檔數

    回傳:
        按綜合評分排序的 top_k 文檔列表

    算法:
        1. 計算 effective_top_k:
           min(top_k * 3, total_documents)
           - 過度檢索以獲得更好的覆蓋率

        2. FAISS 語義搜索:
           - 獲取 effective_top_k 候選
           - 從 L2 距離獲取評分

        3. BM25 關鍵字搜索:
           - 分詞查詢
           - 獲取 effective_top_k 候選
           - 從 BM25 算法獲取評分

        4. 將評分標準化到 [0, 1]:
           - 最小-最大標準化
           - 處理不同的評分範圍

        5. 組合評分:
           combined = alpha * faiss_score + (1-alpha) * bm25_score

        6. 按綜合評分排序 (降序)

        7. 父子解析:
           - 如果文檔有 parent_id,則回傳父文檔
           - 當多個子文檔匹配時去重

        8. 回傳 top_k 文檔

    性能: ~100-500ms,取決於索引大小

    評分範例:
        查詢: "睡眠訓練方法"

        文檔 A (FAISS=0.8, BM25=0.4):
          combined = 0.5*0.8 + 0.5*0.4 = 0.6

        文檔 B (FAISS=0.6, BM25=0.7):
          combined = 0.5*0.6 + 0.5*0.7 = 0.65

        結果: 文檔 B 排名更高 (更好的關鍵字匹配)
    """
```

#### 輔助方法

```python
def _tokenize_documents(documents: List[Document]) -> List[List[str]]:
    """
    為 BM25 進行簡單的空白分詞。

    參數:
        documents: Document 對象列表

    回傳:
        分詞內容列表 (詞列表的列表)

    處理流程:
        - 按空白分割
        - 小寫轉換
        - 無詞幹提取或停用詞移除 (保持準確性)
    """

def _bm25_search(self, query: str, top_k: int) -> Dict[str, float]:
    """
    BM25 關鍵字搜索。

    參數:
        query: 搜索查詢
        top_k: 結果數

    回傳:
        將 document_id 映射到 BM25 評分的字典

    算法: BM25Okapi (最佳匹配排名函數)
    """

def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
    """
    最小-最大標準化到 [0, 1]。

    參數:
        scores: 將 document_id 映射到原始評分的字典

    回傳:
        標準化評分的字典

    公式:
        normalized = (score - min) / (max - min)

    邊緣情況:
        - 單一評分: 回傳 {doc: 1.0}
        - 所有評分相同: 回傳 {doc: 1.0 for all}
    """

def _combine_scores(
    self,
    faiss_scores: Dict[str, float],
    bm25_scores: Dict[str, float]
) -> Dict[str, float]:
    """
    評分的加權線性組合。

    參數:
        faiss_scores: 標準化的 FAISS 評分
        bm25_scores: 標準化的 BM25 評分

    回傳:
        綜合評分的字典

    公式:
        combined = alpha * faiss + (1-alpha) * bm25

    缺失評分:
        - 如果文檔僅在 FAISS 中: bm25 = 0.0
        - 如果文檔僅在 BM25 中: faiss = 0.0
    """

def _get_parent_document(self, doc: Document) -> Document:
    """
    如果子文檔有 parent_id 則檢索父文檔。

    參數:
        doc: Document (可能是子文檔)

    回傳:
        如果 parent_id 存在則回傳父文檔,否則回傳原始文檔

    查找策略:
        1. 嘗試透過 doc_id_to_idx 快速查找
        2. 如果 ID 未找到則退回到線性搜索
        3. 如果未找到父文檔則回傳原始文檔

    用例: 子文檔提供上下文,父文檔提供完整內容
    """
```

#### 配置方法

```python
def set_alpha(self, alpha: float) -> None:
    """
    動態調整 FAISS/BM25 權重。

    參數:
        alpha: 新權重 [0.0, 1.0]

    引發:
        ValueError: 如果 alpha 不在 [0, 1] 範圍內

    用例: 根據查詢特徵調整平衡
        - 更多語義查詢 → 更高的 alpha
        - 更多關鍵字查詢 → 更低的 alpha
    """

def get_stats(self) -> dict:
    """
    回傳檢索器統計資訊。

    回傳:
        包含元數據的字典:
            - total_documents: int
            - alpha: float
            - faiss_index_size: int
            - bm25_corpus_size: int
    """
```

---

### 跨編碼器重排序器

**文件**: `app/core/reranker.py`

#### 目的

使用跨編碼器模型重新排序檢索到的文檔,以獲得更準確的相關性評分。

#### 類別定義

```python
class CrossEncoderReranker:
    """
    用於提高 top-k 精確度的跨編碼器重排序。

    架構比較:
        雙編碼器 (FAISS):
            - 分別編碼查詢和文檔
            - 比較向量表示
            - 快速: O(1) 每次比較 (預計算)
            - 對微妙相關性準確度較低

        跨編碼器 (重排序器):
            - 聯合編碼 (查詢, 文檔) 對
            - 查詢和文檔之間的注意力機制
            - 較慢: O(n) 對需要評估
            - 相關性評分更準確

    屬性:
        _model: CrossEncoder              # 跨編碼器模型
        _max_length: int                  # 最大標記長度 (512)
        _device: str                      # "mps" 或 "cpu"

    用例: 從快速檢索中重新排序前候選
    """
```

#### 初始化

```python
def __init__(
    self,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    max_length: int = 512
):
    """
    初始化跨編碼器重排序器。

    參數:
        model_name: HuggingFace 跨編碼器模型
        max_length: 最大序列長度

    設備檢測:
        1. 檢查 Apple Silicon (MPS)
        2. 退回到 CPU
        3. 記錄設備選擇日誌

    預設模型: ms-marco-MiniLM-L-6-v2
        - 在 MS MARCO 段落排名上訓練
        - 速度和準確性的良好平衡
        - ~80MB 模型大小
    """
```

#### 重排序方法

```python
def rerank(
    self,
    query: str,
    documents: List[Document],
    top_k: int
) -> List[Document]:
    """
    重新排序文檔並按相關性回傳 top_k。

    參數:
        query: 搜索查詢文字
        documents: 檢索到的文檔 (來自 FAISS/混合)
        top_k: 要回傳的文檔數

    回傳:
        按跨編碼器評分排序的 top_k 文檔列表 (降序)

    處理流程:
        1. 邊緣情況處理:
           - 空文檔 → 回傳 []
           - 單一文檔 → 回傳它
           - top_k > len(documents) → 回傳全部

        2. 創建 (查詢, 文檔內容) 對

        3. 跨編碼器推理:
           - 聯合編碼對
           - 生成相關性評分 (logits)
           - 更高評分 = 更相關

        4. 將評分附加到文檔

        5. 按評分排序 (降序)

        6. 回傳 top_k 文檔

        7. 記錄統計:
           - 評分範圍 (最小值、最大值、平均值)
           - 最高文檔元數據

    性能: 每個文檔 ~50-200ms

    評分解釋:
        - 評分是 logits (不是概率)
        - 相對排序重要,絕對值不重要
        - 典型範圍: -10 到 +10
        - 正評分通常表示相關性

    範例:
        查詢: "幼兒睡眠倒退"
        文檔: 來自混合搜索的 10 個候選

        跨編碼器評分:
          文檔 1: 8.5 (高度相關)
          文檔 2: 7.2 (相關)
          文檔 3: 5.8 (有些相關)
          ...
          文檔 10: -2.3 (不相關)

        回傳: 評分為 [8.5, 7.2, 5.8] 的前 3 個文檔
    """
```

---

### 轉錄分塊器 (層次化)

**文件**: `app/core/transcript_chunker.py`

#### 目的

將 VTT 視頻轉錄處理成層次化的父子塊,用於育兒知識庫。

#### 類別定義

```python
class TranscriptChunker:
    """
    將 VTT 轉錄處理成父子層次結構。

    分塊策略:
        父塊: ~750 個標記 (~3 分鐘視頻上下文)
            - 提供廣泛的上下文
            - 用於父文檔檢索
            - 包含 child_ids 以進行細粒度訪問

        子塊: ~150 個標記 (~35 秒細粒度)
            - 實現精確檢索
            - 嵌入用於向量搜索
            - 包含 parent_id 參考

        重疊: ~30 個標記
            - 保留邊界處的上下文
            - 防止分割處的資訊丟失

    元數據追蹤:
        - 時間戳: HH:MM:SS.mmm 格式用於視頻連結
        - 發言者: 從 VTT 標籤提取
        - 字符位置: 用於精確時間戳映射
        - 父子關係: 層次結構

    屬性:
        child_chunk_size: int              # 子塊大小(標記) (150)
        parent_chunk_size: int             # 父塊大小(標記) (750)
        overlap: int                       # 重疊(標記) (30)
        _model: SentenceTransformer        # 用於子嵌入
        _device: str                       # "mps" 或 "cpu"
    """
```

#### 初始化

```python
def __init__(
    self,
    child_chunk_size: int = 150,
    parent_chunk_size: int = 750,
    overlap: int = 30,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
):
    """
    初始化轉錄分塊器。

    參數:
        child_chunk_size: 每個子塊的標記數
        parent_chunk_size: 每個父塊的標記數
        overlap: 塊之間的標記重疊
        model_name: 子塊的嵌入模型

    配置:
        - 標記近似: 1 個標記 ≈ 4 個字符
        - RecursiveCharacterTextSplitter 用於句子邊界
        - 設備檢測 (MPS/CPU)
    """
```

#### 主要管道

```python
def create_chunks(
    self,
    vtt_path: str,
    video_metadata: dict
) -> dict:
    """
    將 VTT 文件處理成層次化塊。

    參數:
        vtt_path: .vtt 轉錄文件的路徑
        video_metadata: 包含視頻資訊的字典 (標題、URL 等)

    回傳:
        包含以下內容的字典:
            'parents': List[dict] - 父塊元數據
            'children': List[dict] - 子塊元數據 + 嵌入

    管道:
        1. 解析 VTT 文件:
           - 提取帶時間戳的字幕
           - 從標籤檢測發言者
           - 清理字幕文字

        2. 按發言者合併字幕:
           - 合併連續的相同發言者段
           - 保留時間戳範圍

        3. 構建完整轉錄:
           - 連接所有字幕
           - 創建字符到時間戳的映射

        4. 創建父塊:
           - 在句子邊界分割
           - 每塊 ~750 個標記
           - 追蹤字符位置

        5. 對於每個父塊:
           a. 創建子塊 (~150 個標記)
           b. 為子塊生成嵌入
           c. 將字符範圍映射到時間戳
           d. 提取唯一的發言者
           e. 連結父子關係

        6. 回傳結構化輸出

    性能: 每 30 分鐘視頻轉錄 ~1-2s

    輸出結構:
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

#### VTT 解析

```python
def parse_vtt(self, vtt_path: str) -> List[dict]:
    """
    解析 VTT 文件,提取帶時間戳的字幕。

    參數:
        vtt_path: VTT 文件的路徑

    回傳:
        字幕字典列表:
            {
                'start_seconds': float,
                'end_seconds': float,
                'speaker': str or None,
                'text': str (已清理)
            }

    處理流程:
        1. 使用 webvtt-py 庫載入 VTT
        2. 對於每個字幕:
           - 提取時間戳
           - 從文字檢測發言者
           - 清理字幕文字
           - 將時間戳轉換為秒
        3. 回傳按時間排序的列表

    發言者檢測:
        格式 1: "名稱: 文字內容"
        格式 2: "<v 名稱>文字內容"
        格式 3: 無發言者標籤 → None
    """

def merge_captions_by_speaker(self, captions: List[dict]) -> List[dict]:
    """
    合併連續的相同發言者字幕。

    參數:
        captions: 來自 parse_vtt 的列表

    回傳:
        帶有合併段的字幕列表

    邏輯:
        - 相同發言者的連續字幕 → 合併
        - 發言者變化或 None 發言者 → 新段
        - 時間戳跨越序列中的第一個到最後一個

    好處: 減少碎片化,保留發言者輪次
    """
```

#### 時間戳映射

```python
def _build_text_and_mapping(
    self,
    merged_captions: List[dict]
) -> Tuple[str, List[Tuple[int, int, float, float]]]:
    """
    構建完整轉錄和字符到時間的映射。

    參數:
        merged_captions: 來自 merge_captions_by_speaker 的輸出

    回傳:
        元組包含:
            - full_text: 連接的轉錄
            - mapping: (char_start, char_end, time_start, time_end) 的列表

    處理流程:
        1. 連接所有字幕文字
        2. 追蹤每個字幕的字符位置
        3. 儲存對應的時間戳
        4. 回傳完整文字 + 位置映射

    用例: 將塊字符範圍 → 視頻時間戳映射
    """

def _get_time_range(
    self,
    char_start: int,
    char_end: int,
    mapping: List[Tuple]
) -> Tuple[str, str]:
    """
    將字符範圍映射到視頻時間戳。

    參數:
        char_start: 塊開始字符位置
        char_end: 塊結束字符位置
        mapping: 來自 _build_text_and_mapping 的輸出

    回傳:
        HH:MM:SS.mmm 格式的 (start_timestamp, end_timestamp) 元組

    算法:
        1. 查找字符範圍的重疊字幕
        2. 提取最早的開始時間
        3. 提取最晚的結束時間
        4. 格式化為 HH:MM:SS.mmm 字串

    邊緣情況:
        - 無重疊: 回傳 ("00:00:00.000", "00:00:00.000")
        - 部分重疊: 使用相交範圍
    """

def _extract_speakers_from_range(
    self,
    char_start: int,
    char_end: int,
    merged_captions: List[dict]
) -> List[str]:
    """
    提取字符範圍內的唯一發言者。

    參數:
        char_start: 塊開始位置
        char_end: 塊結束位置
        merged_captions: 帶發言者資訊的合併字幕

    回傳:
        唯一發言者名稱列表 (或空列表)

    處理流程:
        1. 查找重疊字符範圍的字幕
        2. 收集發言者 (排除 None)
        3. 回傳唯一發言者列表
    """
```

#### 嵌入生成

```python
def _generate_embedding(self, text: str) -> np.ndarray:
    """
    為子塊生成嵌入。

    參數:
        text: 子塊文字

    回傳:
        嵌入的 NumPy 陣列 [embedding_dim]

    處理流程:
        1. 使用 SentenceTransformer 編碼文字
        2. 回傳標準化的嵌入向量

    性能: 每塊 ~10-30ms
    模型: 與 FAISSRetriever 相同以保持一致性
    """
```

---

## 狀態管理

### 圖狀態

**文件**: `app/graph/state.py`

```python
class MedicalChatState(MessagesState):
    """
    醫療聊天機器人 LangGraph 的主狀態。

    繼承自 MessagesState:
        messages: List[BaseMessage]       # 對話歷史

    附加屬性:
        session_id: str                   # 唯一會話識別碼
        assigned_agent: Optional[str]     # 處理對話的代理
        metadata: dict                    # 會話層級元數據

    用法:
        - 通過圖執行傳遞
        - 由 MemorySaver 檢查點儲存
        - 通過 Command 模式由節點更新

    序列化:
        - 所有欄位必須可序列化為 msgpack
        - 不可序列化對象 (代理、檢索器) 在閉包中
    """
```

### 會話儲存

**文件**: `app/core/session_store.py`

#### 會話數據

```python
@dataclass
class SessionData:
    """
    請求之間儲存的會話資訊。

    屬性:
        session_id: str                   # 唯一識別碼
        assigned_agent: Optional[str]     # 指派的代理名稱
        metadata: Dict                    # 自訂元數據
        created_at: datetime              # 創建時間戳
        updated_at: datetime              # 最後更新時間戳
    """
```

#### SessionStore 介面

```python
class SessionStore(ABC):
    """
    會話持久化的抽象介面。

    方法:
        get_session(session_id) -> Optional[SessionData]
        save_session(session_id, data) -> None
        delete_session(session_id) -> None

    實作:
        - InMemorySessionStore: 開發/測試
        - PostgresSessionStore: 生產 (未來)
        - RedisSessionStore: 生產高性能 (未來)
    """
```

#### 記憶體實作

```python
class InMemorySessionStore(SessionStore):
    """
    帶 TTL 的記憶體會話儲存。

    屬性:
        _sessions: Dict[str, SessionData] # 會話儲存
        _lock: asyncio.Lock               # 執行緒安全
        _ttl_seconds: int                 # 生存時間

    功能:
        - 帶鎖的執行緒安全操作
        - TTL 後自動過期
        - 定期清理過期會話
        - O(1) 查找、插入、刪除

    限制:
        - 重啟後不持久
        - 僅限單伺服器 (無分散式)
        - 記憶體容量受限

    方法:
        get_session(session_id) -> Optional[SessionData]
            - 如果存在且未過期則回傳會話
            - 如果未找到或已過期則回傳 None

        save_session(session_id, data) -> None
            - 儲存或更新會話
            - 更新 updated_at 時間戳

        delete_session(session_id) -> None
            - 從儲存中移除會話

        clear_expired_sessions() -> int
            - 移除超過 TTL 的會話
            - 回傳已清理會話的計數
            - 可定期調用
    """
```

---

## 圖編排

**文件**: `app/graph/builder.py`

### 圖架構

```
開始
  ↓
check_assignment (route_based_on_assignment)
  │
  ├─ [assigned_agent == None] → supervisor
  │   │
  │   └─ 分類意圖 → 路由到代理
  │       ↓
  │   [emotional_support | rag_agent | parenting]
  │       ↓
  │      結束
  │
  └─ [assigned_agent != None] → 直接到指派的代理
      │
      └─ [emotional_support | rag_agent | parenting]
          ↓
         結束
```

### 關鍵函數

#### 路由邏輯

```python
def route_based_on_assignment(state: MedicalChatState) -> str:
    """
    實作會話粘性路由。

    參數:
        state: 包含 assigned_agent 欄位的 MedicalChatState

    回傳:
        要路由到的節點名稱

    邏輯:
        if assigned_agent is None:
            return "supervisor"  # 第一條訊息
        else:
            return assigned_agent  # 後續訊息

    效果: 確保每個會話的一致代理處理

    範例:
        訊息 1: assigned_agent=None → 路由到 supervisor → 設定 assigned_agent="rag_agent"
        訊息 2: assigned_agent="rag_agent" → 直接路由到 rag_agent
        訊息 3: assigned_agent="rag_agent" → 直接路由到 rag_agent
    """
```

#### 圖構建器

```python
def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: Optional[DocumentRetriever] = None,
    parenting_reranker: Optional[CrossEncoderReranker] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None
) -> CompiledGraph:
    """
    為醫療聊天機器人構建編譯的 LangGraph。

    參數:
        retriever: 醫療知識的 FAISSRetriever
        parenting_retriever: 育兒的 HybridRetriever (可選)
        parenting_reranker: 育兒的 CrossEncoderReranker (可選)
        checkpointer: 自訂檢查點儲存器或 None 使用預設

    回傳:
        準備好 ainvoke() 的 CompiledGraph

    架構模式: 閉包 + 包裝器節點
        問題:
            - 代理和檢索器不可序列化
            - MemorySaver 使用 msgpack (需要序列化)

        解決方案:
            - 在閉包範圍中捕獲不可序列化對象
            - 創建將對象注入狀態的包裝器節點
            - 僅序列化 MedicalChatState (訊息、session_id 等)

        範例:
            # 在閉包中捕獲 (不在狀態中)
            rag_agent = create_rag_agent(retriever)

            # 包裝器節點
            def rag_node_wrapper(state):
                # 從閉包存取 rag_agent
                state_with_retriever = {**state, "retriever": retriever}
                return rag_agent.invoke(state_with_retriever)

    圖結構:
        1. 添加 "check_assignment" 節點 (route_based_on_assignment)
        2. 添加 "supervisor" 節點 (supervisor_node)
        3. 添加 "emotional_support" 節點 (包裝器)
        4. 添加 "rag_agent" 節點 (帶檢索器注入的包裝器)
        5. 添加 "parenting" 節點 (帶檢索器 + 重排序器的包裝器) [如果可用]
        6. 設定入口點: "check_assignment"
        7. 從 "check_assignment" 到所有代理添加條件邊
        8. 從 supervisor 到所有代理添加邊
        9. 從所有代理到 END 添加邊
        10. 使用檢查點儲存器編譯

    檢查點儲存器邏輯:
        - 如果提供 None: 生產環境使用 MemorySaver()
        - 如果提供: 使用自訂檢查點儲存器 (用於測試)

    功能:
        - 會話感知路由
        - 透過檢查點儲存器實現對話記憶
        - 可選育兒代理帶優雅降級
        - 基於閉包的依賴注入

    性能: 路由 <1ms,代理執行時間可變
    """
```

#### 檢查點儲存器輔助函數

```python
def _get_checkpointer() -> BaseCheckpointSaver:
    """
    回傳生產環境的預設檢查點儲存器。

    回傳:
        MemorySaver 實例

    用法:
        - 當 checkpointer=None 時由 build_medical_chatbot_graph 調用
        - 測試直接提供 AsyncSqliteSaver 以避免衝突

    MemorySaver:
        - 記憶體對話持久化
        - 由 thread_id (session_id) 鍵控
        - 重啟後不持久
        - 適合單伺服器部署
    """
```

---

## 數據模型

**文件**: `app/models.py`

### 請求/回應模型

```python
class ChatRequest(BaseModel):
    """
    聊天端點請求載荷。

    屬性:
        session_id: str          # 唯一會話識別碼
        message: str             # 用戶訊息 (最小長度=1)

    驗證:
        - session_id: 必需,非空字串
        - message: 必需,最小長度=1

    範例:
        {
            "session_id": "user_12345",
            "message": "阿斯匹靈的副作用是什麼?"
        }
    """

class ChatResponse(BaseModel):
    """
    聊天端點回應載荷。

    屬性:
        session_id: str          # 回送請求的 session_id
        message: str             # 代理回應文字
        agent: str               # 處理請求的代理
        metadata: Optional[dict] # 附加資訊

    代理值:
        - "supervisor": 意圖分類 (不應出現在回應中)
        - "emotional_support": 情緒支持
        - "rag_agent": 醫療資訊
        - "parenting": 育兒建議

    元數據範例:
        {
            "reasoning": "用戶表達情緒困擾",
            "confidence": 0.85,
            "sources": [{"title": "...", "url": "..."}]
        }

    範例:
        {
            "session_id": "user_12345",
            "message": "阿斯匹靈常見副作用包括...",
            "agent": "rag_agent",
            "metadata": {
                "sources": [
                    {"name": "阿斯匹靈資訊", "content": "..."}
                ]
            }
        }
    """

class HealthResponse(BaseModel):
    """
    健康檢查端點回應。

    屬性:
        status: str = "healthy"
        version: str = "0.1.0"
    """
```

---

## 系統提示詞

**文件**: `app/utils/prompts.py`

### 提示詞概覽

| 提示詞 | 代理 | 用途 |
|--------|------|------|
| `SUPERVISOR_PROMPT` | Supervisor | 意圖分類 |
| `EMOTIONAL_SUPPORT_PROMPT` | Emotional Support | 同理心回應 |
| `RAG_AGENT_PROMPT` | RAG Agent | 帶檢索的醫療問答 |
| `PARENTING_AGENT_PROMPT` | Parenting Agent | 育兒建議 |

### SUPERVISOR_PROMPT

```
用途: 將用戶查詢路由到合適的代理

路由邏輯:
  - 情緒支持: 感受、壓力、焦慮、情緒困擾
  - RAG 代理: 醫療問題、藥物、治療、病症
  - 育兒: 兒童發展、育兒、幼兒/嬰兒護理

輸出: 包含 agent、reasoning、confidence 的 JSON
```

### EMOTIONAL_SUPPORT_PROMPT

```
用途: 提供富有同理心的非臨床情緒支持

指導原則:
  - 主動傾聽和驗證
  - 不提供醫療建議或診斷
  - 鼓勵尋求專業幫助處理嚴重問題
  - 危機資源 (988 熱線、危機文字熱線)
  - 邊界: 不是治療師,範圍有限

語氣: 溫暖、同理心、支持性
```

### RAG_AGENT_PROMPT

```
用途: 使用知識庫回答醫療問題

要求:
  - 必須在回答前使用 search_medical_docs 工具
  - 僅教育資訊 (不是醫療建議)
  - 從檢索文檔引用來源
  - 鼓勵諮詢醫療保健提供者

免責聲明:
  - 不能替代專業醫療建議
  - 諮詢醫生進行診斷和治療

格式: 結構化、基於證據、帶引用
```

### PARENTING_AGENT_PROMPT

```
用途: 提供專業育兒和兒童發展建議

要求:
  - 使用 search_parenting_knowledge 工具
  - 適齡指導
  - 基於證據的建議
  - 發展背景

指導原則:
  - 考慮孩子的年齡和階段
  - 實用、可操作的建議
  - 尊重育兒方法
  - 承認個體差異

語氣: 支持性、資訊性、不評判
```

---

## 數據流

### 聊天請求處理

```
1. POST /chat
   ├─ 輸入: {session_id, message}
   └─ FastAPI 處理器: chat()

2. 會話管理
   ├─ 從 SessionStore 載入會話
   └─ 如果不存在則創建會話

3. 構建狀態
   ├─ MedicalChatState:
   │   ├─ messages: [HumanMessage(message)]
   │   ├─ session_id: 來自請求
   │   ├─ assigned_agent: 來自會話或 None
   │   └─ metadata: {}
   └─ 配置: {configurable: {thread_id: session_id}}

4. 圖調用
   ├─ graph.ainvoke(state, config)
   ├─ check_assignment → 路由
   │   ├─ 第一條訊息: → supervisor → 分類 → 路由到代理
   │   └─ 後續: → 直接到 assigned_agent
   └─ 代理執行 → 回應

5. 回應提取
   ├─ 從 result["messages"] 的最後一條訊息
   ├─ 從狀態或訊息元數據獲取代理名稱
   └─ 從狀態獲取元數據

6. 會話更新
   ├─ 更新 assigned_agent
   ├─ 更新元數據
   ├─ 更新 updated_at 時間戳
   └─ 保存到 SessionStore

7. 回傳回應
   └─ ChatResponse {session_id, message, agent, metadata}
```

### 育兒代理內部流程

```
1. parenting_agent_node 接收 MedicalChatState

2. 轉換為 ParentingRAGState
   ├─ 從最後一條訊息提取問題
   ├─ 初始化: documents=[], filtered_documents=[]
   ├─ 設定: retrieval_attempts=0, confidence=0.0
   └─ 複製訊息

3. 代理決策
   ├─ LLM 分析問題
   ├─ 決定: 檢索或直接回答?
   └─ 回傳有或無 tool_calls 的訊息

4. 如果 tool_calls: 執行檢索
   ├─ search_parenting_knowledge(query)
   ├─ 混合搜索 (FAISS + BM25)
   ├─ 跨編碼器重排序
   ├─ 在狀態中儲存文檔
   └─ 繼續到評分

5. 文檔評分
   ├─ 對每個文檔:
   │   ├─ LLM 評分相關性
   │   └─ 回傳評分 [0.0-1.0]
   ├─ 過濾: score >= 0.5
   └─ 儲存 filtered_documents + relevance_scores

6. 品質檢查
   ├─ 標準: docs >= 1, avg_score >= 0.6, attempts < 2
   ├─ 品質好: → generate_answer
   └─ 品質差: → rewrite_query → 重試 (回到步驟 3)

7. 生成答案
   ├─ LLM 從 filtered_documents 合成
   ├─ 適齡、基於證據
   ├─ 提取來源
   └─ 回傳 generation

8. 信心檢查
   ├─ 計算: avg_relevance*0.7 + doc_coverage*0.3
   ├─ 高 (>= 0.6): → 回傳答案
   └─ 低 (< 0.6): → insufficient_info (後備回應)

9. 回傳到主圖
   ├─ 提取最終訊息
   ├─ 更新 MedicalChatState
   └─ 回傳 Command(goto=END)
```

---

## 關鍵架構模式

### 1. 序列化問題與解決方案

**問題**: LangGraph 的 MemorySaver 使用 msgpack 序列化
- FAISSRetriever、代理不可序列化
- 無法儲存在圖狀態中
- 檢查點儲存會因序列化錯誤失敗

**解決方案: 閉包模式**

```python
# 在 builder.py 中
def build_medical_chatbot_graph(retriever, ...):
    # 創建代理 (在閉包中捕獲,不在狀態中)
    rag_agent = create_rag_agent(retriever)
    parenting_agent = create_parenting_rag_agent(retriever, reranker)

    # 包裝器節點存取閉包變數
    def rag_node_wrapper(state: MedicalChatState):
        # rag_agent 透過閉包可存取
        # retriever 透過閉包可存取
        state_with_retriever = {**state, "retriever": retriever}
        response = rag_agent.invoke(state_with_retriever)
        return Command(goto=END, update={"messages": response["messages"]})

    # 將包裝器添加到圖 (閉包被捕獲)
    builder.add_node("rag_agent", rag_node_wrapper)

    # 僅 MedicalChatState 被檢查點儲存 (可序列化)
    return builder.compile(checkpointer=MemorySaver())
```

**關鍵點**:
- 不可序列化對象存在於閉包範圍
- 包裝器節點在執行期間將對象注入狀態
- 僅可序列化狀態 (訊息、session_id) 被檢查點儲存
- 對話歷史正確持久化

---

### 2. 雙層檢查點儲存

```
外層 (主圖):
  ├─ 檢查點儲存器: MemorySaver()
  ├─ 狀態: MedicalChatState (可序列化)
  ├─ 持久化: messages, session_id, assigned_agent, metadata
  └─ 執行緒 ID: session_id

內層 (代理圖):
  ├─ RAG 代理: checkpointer=False (無狀態)
  ├─ 育兒代理: 嵌套圖,無檢查點儲存
  └─ 情緒支持: 直接調用,無狀態
```

**理由**:
- 外部圖管理對話記憶
- 內部代理是無狀態的 (每次調用重新計算)
- 防止嵌套檢查點儲存衝突
- 簡化代理設計

---

### 3. 會話粘性路由

```
會話中的第一條訊息:
  1. assigned_agent = None
  2. 路由到 supervisor
  3. Supervisor 分類意圖
  4. 回傳 Command(goto=<agent>, update={assigned_agent: <agent>})
  5. 路由到合適的代理
  6. 生成回應
  7. 使用 assigned_agent 檢查點儲存狀態

後續訊息:
  1. 載入狀態: assigned_agent = "rag_agent"
  2. route_based_on_assignment 檢查 assigned_agent
  3. 直接路由到 "rag_agent" (跳過 supervisor)
  4. 代理使用對話上下文處理訊息
  5. 生成回應
  6. 更新並檢查點儲存狀態
```

**好處**:
- 每個會話的一致代理處理
- 減少分類開銷
- 維持對話連續性
- 防止對話中途切換代理

---

### 4. 優雅降級

**醫療嵌入** (必需):
```python
# 在 main.py lifespan 中
try:
    medical_retriever = await _load_medical_retriever()
except FileNotFoundError:
    logger.error("未找到醫療嵌入 - 無法啟動")
    raise  # 快速失敗
```

**育兒嵌入** (可選):
```python
try:
    parenting_retriever, reranker = await _load_parenting_system()
except FileNotFoundError:
    parenting_retriever, reranker = None, None
    logger.warning("育兒代理已停用 - 優雅降級")

# 使用可選育兒構建圖
graph = build_medical_chatbot_graph(
    retriever=medical_retriever,
    parenting_retriever=parenting_retriever,  # 可能為 None
    parenting_reranker=reranker  # 可能為 None
)
```

**結果**: 應用程式以減少的功能運行,而不是崩潰

---

### 5. 父子文檔層次結構

**用途**: 平衡上下文和精確性

```
父文檔:
  ├─ ID: "parent_0"
  ├─ 內容: ~750 個標記 (~3 分鐘視頻)
  ├─ 子 ID: ["child_0", "child_1", "child_2", "child_3", "child_4"]
  └─ 用途: 檢索時提供廣泛上下文

子文檔 (已嵌入):
  ├─ ID: "child_0"
  ├─ 父 ID: "parent_0"
  ├─ 內容: ~150 個標記 (~35 秒視頻)
  ├─ 嵌入: [384] 向量
  └─ 用途: 精確檢索,回傳完整上下文的父文檔
```

**檢索流程**:
```
1. 用戶查詢: "幼兒睡眠訓練"
2. 在子嵌入上進行向量搜索 (精確)
3. 最匹配的子文檔: child_5, child_12, child_23
4. 映射到父文檔: parent_1, parent_2, parent_4
5. 回傳父文檔 (完整上下文)
6. 如果多個子文檔共享父文檔則去重
```

**好處**:
- 精確檢索 (子粒度)
- 豐富上下文 (父內容)
- 減少冗餘 (去重的父文檔)

---

## 部署指南

### 部署前檢查清單

**1. 醫療嵌入 (必需)**

```bash
python -m src.precompute_embeddings
```

在 `data/embeddings/` 中創建:
- `faiss_index.pkl` - FAISS 索引
- `documents.pkl` - Document 對象
- `embeddings.npy` - 嵌入向量
- `metadata.json` - 索引元數據

**2. 育兒嵌入 (可選)**

```bash
python -m src.precompute_parenting_embeddings --force
```

在 `data/parenting_index/` 中創建:
- `child_documents.pkl` - 帶嵌入的子文檔
- `parent_chunks.pkl` - 父文檔
- `bm25_index.pkl` - 關鍵字搜索的 BM25 索引

**3. 環境變數**

必需:
```bash
OPENAI_API_KEY=your-openrouter-api-key
OPENAI_API_BASE=https://openrouter.ai/api/v1
```

可選 (帶預設值):
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

**4. 依賴**

```bash
pip install -r requirements.txt
```

關鍵依賴:
- langgraph
- langchain
- langchain-openai
- sentence-transformers
- faiss-cpu (或 faiss-gpu)
- rank-bm25
- webvtt-py
- fastapi
- uvicorn
- pydantic

**5. 啟動應用程式**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

生產環境:
```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

---

### 性能特徵

| 操作 | 延遲 | 備註 |
|------|------|------|
| 健康檢查 | ~1ms | 無 I/O |
| 會話查找 | ~1-5ms | 記憶體字典查找 |
| 監督分類 | 500-1000ms | LLM 結構化輸出 |
| 情緒支持 | 2-5s | LLM 生成 (高溫度) |
| 醫療 RAG (無檢索) | 2-3s | 直接 LLM 生成 |
| 醫療 RAG (帶檢索) | 3-8s | FAISS 搜索 + LLM |
| 育兒 RAG (最佳) | 5-10s | 混合 + 重排序 + 生成 |
| 育兒 RAG (帶重寫) | 10-20s | 最多 2 個重試週期 |

**瓶頸**:
- LLM 推理 (OpenRouter API)
- 網路延遲 (API 調用)
- 跨編碼器重排序 (O(n) 文檔)

**優化**:
- 預計算嵌入 (離線)
- 快取 (未來增強)
- 批量 API 請求 (未來)
- GPU 加速嵌入 (可選)

---

### 監控與日誌

**日誌級別**:
- `DEBUG`: 詳細執行流程
- `INFO`: 關鍵事件 (啟動、路由決策、性能)
- `WARNING`: 非關鍵問題 (缺失可選組件)
- `ERROR`: 需要注意的失敗

**監控關鍵指標**:
- 請求延遲 (p50, p95, p99)
- 代理分佈 (監督分類)
- 按代理的錯誤率
- 會話儲存大小和過期
- LLM API 成本和延遲
- 檢索品質 (相關性評分)

**健康檢查**:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "0.1.0"}
```

---

## 總結

此後端 API 提供了一個複雜的多代理醫療聊天機器人,具有:

**核心能力**:
- 基於意圖的專業代理路由
- 會話感知的對話記憶
- 帶品質檢查的檢索增強生成
- 混合向量 + 關鍵字搜索
- 層次化文檔處理

**關鍵設計模式**:
- 基於閉包的依賴注入
- 優雅降級
- 會話粘性路由
- 父子文檔層次結構
- 雙層檢查點儲存

**生產就緒功能**:
- 帶非同步處理器的 FastAPI
- 透過環境配置
- 預計算嵌入
- 健康監控
- 完善的錯誤處理

如有問題或疑問,請參考上述具體章節或查閱原始碼。
