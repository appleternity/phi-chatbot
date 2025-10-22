# 實作指南

## 概述

本指南提供逐步說明，協助你實作醫療聊天機器人系統的各個元件。按照本指南從頭建立系統或擴充新功能。

## 前置需求

- Python 3.11+
- Poetry 或 pip 用於相依套件管理
- OpenRouter API 金鑰（或其他相容 OpenAI 的端點）
- 基本了解非同步 Python 和 FastAPI

## 實作檢查清單

- [x] 專案結構和相依套件
- [x] 設定管理
- [x] 抽象介面（SessionStore、DocumentRetriever）
- [ ] 範例醫療資料（心理健康藥物）
- [ ] LangGraph 的狀態定義
- [ ] 包含分類功能的監督代理
- [ ] 情緒支援代理
- [ ] 具有檢索工具的 RAG 代理
- [ ] 包含路由邏輯的圖結構建構
- [ ] FastAPI 應用程式和端點
- [ ] 單元測試
- [ ] 整合測試
- [ ] 文件和範例

## 逐步實作

### 1. 專案設定

**狀態**：✅ 完成

**檔案**：
- `pyproject.toml`：相依套件和建置設定
- `.env.example`：環境變數範本
- `app/config.py`：使用 pydantic-settings 的設定管理

**設定步驟**：
```bash
# 安裝相依套件
poetry install

# 複製環境檔案
cp .env.example .env

# 編輯 .env 並填入你的 OpenRouter API 金鑰
nano .env
```

### 2. 建立範例醫療資料

**狀態**：⏳ 待處理

**檔案**：`data/mental_health_meds.json`

**需求**：
- 5 種心理健康藥物
- 每種藥物包含：名稱、類別、用途、劑量、副作用
- JSON 格式以便載入

**實作**：
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

**載入函數**（`app/utils/data_loader.py`）：
```python
import json
from pathlib import Path
from typing import List
from app.core.retriever import Document

async def load_medical_documents() -> List[Document]:
    """從 JSON 檔案載入心理健康藥物文件。"""
    data_path = Path(__file__).parent.parent.parent / "data" / "mental_health_meds.json"

    with open(data_path, 'r') as f:
        raw_data = json.load(f)

    documents = []
    for item in raw_data:
        # 建立可搜尋的內容
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

### 3. 定義 LangGraph 狀態

**狀態**：⏳ 待處理

**檔案**：`app/graph/state.py`

**需求**：
- 從 LangGraph 擴充 MessagesState
- 新增會話追蹤欄位
- 新增指派代理欄位

**實作**：
```python
from typing import Optional, Annotated
from langgraph.graph import MessagesState, add_messages
from langchain_core.messages import BaseMessage

class MedicalChatState(MessagesState):
    """醫療聊天機器人圖的狀態。

    使用會話管理欄位擴充 MessagesState。
    """

    # 會話識別
    session_id: str

    # 代理指派（黏性路由）
    assigned_agent: Optional[str] = None  # "emotional_support" | "rag_agent" | None

    # 額外的中繼資料
    metadata: dict = {}
```

**使用說明**：
- `messages` 欄位繼承自 MessagesState
- `add_messages` 自動合併新訊息
- `session_id` 作為 LangGraph thread_id 使用
- `assigned_agent` 決定第一則訊息後的路由

### 4. 實作監督代理

**狀態**：⏳ 待處理

**檔案**：`app/agents/supervisor.py`

**需求**：
- 從第一則訊息分類使用者意圖
- 使用結構化輸出以提高可靠性
- 回傳代理指派結果

**實作**：
```python
from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.config import settings

class AgentClassification(BaseModel):
    """代理分類的結構化輸出。"""

    agent: Literal["emotional_support", "rag_agent"] = Field(
        description="根據使用者意圖指派的代理"
    )
    reasoning: str = Field(
        description="選擇此代理的簡短說明"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="分類的信心度（0-1）"
    )

# 初始化 LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.1  # 低溫度以確保一致的分類
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
    """監督代理，分類使用者意圖並指派適當的代理。

    此節點僅在會話的第一則訊息時執行。
    """
    # 取得最後一則使用者訊息
    last_message = state["messages"][-1]

    # 使用結構化輸出進行分類
    classification = llm.with_structured_output(AgentClassification).invoke(
        SUPERVISOR_PROMPT.format(message=last_message.content)
    )

    # 記錄分類（對除錯很有用）
    print(f"Supervisor classification: {classification.agent} (confidence: {classification.confidence:.2f})")
    print(f"Reasoning: {classification.reasoning}")

    # 回傳包含指派代理的命令
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

**測試監督代理**：
```python
# 測試案例
test_messages = [
    "I'm feeling really sad today",  # 應該路由到 emotional_support
    "What are the side effects of Sertraline?",  # 應該路由到 rag_agent
    "I need someone to talk to",  # 應該路由到 emotional_support
    "Tell me about Lexapro",  # 應該路由到 rag_agent
]
```

### 5. 實作情緒支援代理

**狀態**：⏳ 待處理

**檔案**：`app/agents/emotional_support.py`

**需求**：
- 同理心、支持性的回應
- 積極傾聽
- 適當時鼓勵尋求專業協助
- 不需要工具（僅對話）

**實作**：
```python
from typing import Literal
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langgraph.graph import END
from app.graph.state import MedicalChatState
from app.config import settings

# 初始化 LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.7  # 較高的溫度以產生更具同理心、自然的回應
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
    """情緒支援代理，提供同理心對話。

    此代理專注於積極傾聽和情緒確認。
    """
    # 建構包含系統提示的訊息
    messages = [
        {"role": "system", "content": EMOTIONAL_SUPPORT_PROMPT}
    ] + state["messages"]

    # 產生回應
    response = llm.invoke(messages)

    # 回傳包含回應的命令
    return Command(
        goto=END,
        update={"messages": [response]}
    )
```

**回應範例**：
```
使用者：「我今天感到非常焦慮」
代理：「我理解你的感受，有時感到焦慮是完全可以理解的。
       你願意談談是什麼造成這些感受嗎？
       我在這裡傾聽。」

使用者：「沒有人了解我正在經歷的事情」
代理：「感到孤立和被誤解可能真的很痛苦。你的感受是有效的，
       我希望你知道，在經歷這些挑戰時你並不孤單。
       是什麼一直困擾著你呢？」
```

### 6. 實作 RAG 代理

**狀態**：⏳ 待處理

**檔案**：`app/agents/rag_agent.py`

**需求**：
- 使用知識庫回答醫療問題
- 使用 DocumentRetriever 作為工具
- 引用來源
- 包含免責聲明

**實作**：
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

# 初始化 LLM
llm = ChatOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
    model=settings.model_name,
    temperature=0.3  # 低溫度以確保事實準確性
)

@tool
async def search_medical_docs(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """在醫療知識庫中搜尋藥物相關資訊。

    使用此工具可找到以下資訊：
    - 藥物名稱和分類
    - 用途和適應症
    - 劑量資訊
    - 副作用
    - 警告和交互作用

    Args:
        query: 搜尋查詢（藥物名稱、病症或問題）

    Returns:
        來自相關文件的格式化資訊
    """
    retriever: DocumentRetriever = state["retriever"]
    docs = await retriever.search(query, top_k=settings.top_k_documents)

    if not docs:
        return "No relevant information found in the knowledge base."

    # 為 LLM 格式化文件
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
    """建立可存取文件檢索器的 RAG 代理。"""
    return create_react_agent(
        llm,
        tools=[search_medical_docs],
        prompt=RAG_AGENT_PROMPT,
        state_modifier="You have access to a medical knowledge base. Use the search tool to find accurate information."
    )

def rag_agent_node(state: MedicalChatState) -> Command[Literal[END]]:
    """RAG 代理，使用知識庫回答醫療問題。

    此代理使用檢索增強生成來提供準確的資訊。
    """
    # 將檢索器注入狀態以供工具存取
    state_with_retriever = {
        **state,
        "retriever": state.get("retriever")  # 檢索器由圖建構器注入
    }

    # 取得 RAG 代理（建立一次並快取）
    rag_agent = state.get("_rag_agent")
    if not rag_agent:
        raise ValueError("RAG agent not initialized in state")

    # 呼叫代理
    response = rag_agent.invoke(state_with_retriever)

    # 回傳包含回應的命令
    return Command(
        goto=END,
        update={"messages": response["messages"]}
    )
```

**互動範例**：
```
使用者：「Sertraline 用於治療什麼？」
代理：[搜尋知識庫]
      「根據知識庫：

       Sertraline（商品名 Zoloft）是一種 SSRI（選擇性血清素再吸收抑制劑），
       用於治療：
       - 重度憂鬱症
       - 焦慮症
       - 強迫症（OCD）
       - 創傷後壓力症候群（PTSD）
       - 恐慌症

       典型劑量：每日 50-200mg，每天服用一次。

       來源：醫療知識庫 - Sertraline 條目

       免責聲明：這僅供教育資訊，非醫療建議。
       請諮詢醫療專業人員以做出醫療決策。」
```

### 7. 建構 LangGraph

**狀態**：⏳ 待處理

**檔案**：`app/graph/builder.py`

**需求**：
- 建構包含所有節點的圖
- 實作路由邏輯
- 處理會話指派
- 使用檢查點初始化

**實作**：
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
    """如果未指派代理則路由到監督者，否則路由到已指派的代理。"""
    if state.get("assigned_agent") is None:
        return "supervisor"
    return state["assigned_agent"]

def build_medical_chatbot_graph(retriever: DocumentRetriever):
    """建構並編譯醫療聊天機器人圖。

    Args:
        retriever: RAG 代理的文件檢索器實例

    Returns:
        已編譯的 LangGraph，可供呼叫
    """
    # 建立圖建構器
    builder = StateGraph(MedicalChatState)

    # 使用檢索器建立 RAG 代理
    rag_agent = create_rag_agent(retriever)

    # 新增節點
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)

    # 包裝 RAG 代理節點以注入代理實例
    def rag_node_wrapper(state: MedicalChatState):
        state["_rag_agent"] = rag_agent
        state["retriever"] = retriever
        return rag_agent_node(state)

    builder.add_node("rag_agent", rag_node_wrapper)

    # 定義邊
    builder.add_edge(START, "supervisor")  # 總是從監督者開始進行分類

    # 監督者路由到指派的代理
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        {
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # 所有代理都導向 END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)

    # 使用檢查點編譯以保留對話記憶
    graph = builder.compile(checkpointer=MemorySaver())

    return graph
```

**替代方案：會話感知路由**

如果你想在後續訊息中跳過監督者（更有效率）：

```python
def build_medical_chatbot_graph_v2(retriever: DocumentRetriever):
    """建構具有會話感知路由的圖，在第一則訊息後繞過監督者。"""
    builder = StateGraph(MedicalChatState)

    # 新增路由節點
    def check_assignment_node(state: MedicalChatState):
        # 不修改狀態，僅回傳目前狀態
        return state

    builder.add_node("check_assignment", check_assignment_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("emotional_support", emotional_support_node)
    builder.add_node("rag_agent", rag_agent_node)

    # 從路由節點開始
    builder.add_edge(START, "check_assignment")

    # 根據指派進行路由
    builder.add_conditional_edges(
        "check_assignment",
        route_based_on_assignment,
        {
            "supervisor": "supervisor",
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # 監督者指派並路由
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state["assigned_agent"],
        {
            "emotional_support": "emotional_support",
            "rag_agent": "rag_agent"
        }
    )

    # 代理導向 END
    builder.add_edge("emotional_support", END)
    builder.add_edge("rag_agent", END)

    return builder.compile(checkpointer=MemorySaver())
```

### 8. 實作 FastAPI 應用程式

**狀態**：⏳ 待處理

**檔案**：`app/main.py`

**需求**：
- POST /chat 端點
- GET /health 端點
- 會話管理整合
- 資源管理的生命週期

**實作**：
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

# 設定日誌
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# 全域狀態
app_state = {
    "graph": None,
    "session_store": None,
    "retriever": None
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動和關閉的生命週期情境管理器。"""
    # 啟動
    logger.info("Initializing application...")

    # 初始化會話儲存
    app_state["session_store"] = InMemorySessionStore(ttl_seconds=settings.session_ttl_seconds)
    logger.info("Session store initialized")

    # 初始化檢索器並載入文件
    retriever = FAISSRetriever(embedding_model=settings.embedding_model)
    docs = await load_medical_documents()
    await retriever.add_documents(docs)
    app_state["retriever"] = retriever
    logger.info(f"Loaded {len(docs)} medical documents into retriever")

    # 建構圖
    app_state["graph"] = build_medical_chatbot_graph(retriever)
    logger.info("Medical chatbot graph compiled")

    logger.info("Application startup complete")

    yield

    # 關閉
    logger.info("Shutting down application...")
    # 如需要進行清理

# 建立 FastAPI 應用程式
app = FastAPI(
    title="Medical Chatbot API",
    description="Multi-agent medical chatbot with emotional support and RAG",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 中介軟體（針對正式環境進行設定）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 針對正式環境適當設定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 相依性注入
def get_session_store() -> SessionStore:
    return app_state["session_store"]

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康檢查端點。"""
    return HealthResponse(status="healthy", version="0.1.0")

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store)
):
    """主要聊天端點。

    處理具有會話感知路由的對話。
    """
    try:
        # 載入或建立會話
        session = await session_store.get_session(request.session_id)
        if session is None:
            session = SessionData(session_id=request.session_id)
            logger.info(f"Created new session: {request.session_id}")
        else:
            logger.info(f"Loaded existing session: {request.session_id}, assigned_agent: {session.assigned_agent}")

        # 建構圖狀態
        state = MedicalChatState(
            messages=[{"role": "user", "content": request.message}],
            session_id=request.session_id,
            assigned_agent=session.assigned_agent,
            metadata=session.metadata
        )

        # 呼叫圖
        config = {"configurable": {"thread_id": request.session_id}}
        result = await app_state["graph"].ainvoke(state, config)

        # 提取回應
        last_message = result["messages"][-1]
        response_text = last_message.content
        assigned_agent = result.get("assigned_agent", session.assigned_agent)

        # 更新會話
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

### 9. 測試

#### 單元測試

**檔案**：`tests/unit/test_supervisor.py`
```python
import pytest
from app.agents.supervisor import supervisor_node, AgentClassification
from app.graph.state import MedicalChatState

@pytest.mark.asyncio
async def test_supervisor_emotional_classification():
    """測試監督者正確分類情緒支援請求。"""
    state = MedicalChatState(
        messages=[{"role": "user", "content": "I'm feeling really depressed"}],
        session_id="test-1"
    )

    result = supervisor_node(state)
    assert result.update["assigned_agent"] == "emotional_support"

@pytest.mark.asyncio
async def test_supervisor_rag_classification():
    """測試監督者正確分類醫療資訊請求。"""
    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}],
        session_id="test-2"
    )

    result = supervisor_node(state)
    assert result.update["assigned_agent"] == "rag_agent"
```

**檔案**：`tests/unit/test_session_store.py`
```python
import pytest
from app.core.session_store import InMemorySessionStore, SessionData

@pytest.mark.asyncio
async def test_session_create_and_retrieve():
    """測試建立和檢索會話。"""
    store = InMemorySessionStore()
    session = SessionData(session_id="test-123", assigned_agent="rag_agent")

    await store.save_session("test-123", session)
    retrieved = await store.get_session("test-123")

    assert retrieved is not None
    assert retrieved.session_id == "test-123"
    assert retrieved.assigned_agent == "rag_agent"

@pytest.mark.asyncio
async def test_session_expiration():
    """測試會話 TTL 過期。"""
    store = InMemorySessionStore(ttl_seconds=1)
    session = SessionData(session_id="test-expire")

    await store.save_session("test-expire", session)

    import asyncio
    await asyncio.sleep(2)

    retrieved = await store.get_session("test-expire")
    assert retrieved is None
```

#### 整合測試

**檔案**：`tests/integration/test_graph_flow.py`
```python
import pytest
from app.graph.builder import build_medical_chatbot_graph
from app.core.retriever import FAISSRetriever, Document
from app.graph.state import MedicalChatState

@pytest.fixture
async def mock_retriever():
    """建立包含範例文件的模擬檢索器。"""
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
    """測試完整的對話流程，包含分類和回應。"""
    graph = build_medical_chatbot_graph(mock_retriever)

    # 第一則訊息
    state = MedicalChatState(
        messages=[{"role": "user", "content": "What is Sertraline?"}],
        session_id="test-conv-1"
    )

    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-conv-1"}})

    assert result["assigned_agent"] == "rag_agent"
    assert len(result["messages"]) > 1
    assert "Sertraline" in result["messages"][-1].content
```

**檔案**：`tests/integration/test_api_endpoints.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    """測試健康檢查端點。"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_chat_endpoint_new_session(client):
    """測試新會話的聊天端點。"""
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

## 常見實作模式

### 新增新代理

1. 建立代理檔案：`app/agents/new_agent.py`
2. 定義代理函數，回傳類型為 `Command[Literal[END]]`
3. 更新監督者分類以包含新代理類型
4. 在 `app/graph/builder.py` 中新增節點到圖
5. 更新路由邏輯
6. 新增測試

### 切換到正式環境資料庫

1. 實作 `PostgresSessionStore` 或 `RedisSessionStore`
2. 更新 `app/main.py` 中的相依性注入：
```python
def get_session_store() -> SessionStore:
    if settings.environment == "production":
        return PostgresSessionStore(settings.database_url)
    return InMemorySessionStore()
```

### 新增串流支援

1. 修改圖呼叫以使用 `astream`：
```python
async for chunk in app_state["graph"].astream(state, config):
    yield f"data: {json.dumps(chunk)}\n\n"
```

2. 更新端點以回傳 `StreamingResponse`

## 疑難排解

### 問題：監督者總是分類錯誤
- 檢查 LLM 溫度（應該較低，0.1-0.3）
- 驗證提示的清晰度
- 使用結構化輸出驗證進行測試

### 問題：RAG 代理找不到文件
- 驗證文件已載入：檢查啟動日誌
- 直接使用範例查詢測試檢索器
- 檢查嵌入模型初始化

### 問題：會話未持久化
- 驗證 TTL 設定
- 檢查 SessionStore 儲存操作
- 新增日誌以追蹤會話操作

## 後續步驟

1. 完成待處理的實作（標記為 ⏳）
2. 執行所有測試：`pytest tests/`
3. 使用不同對話場景手動測試
4. 部署到開發環境
5. 監控並迭代改進

## 其他資源

- [LangGraph 文件](https://langchain-ai.github.io/langgraph/)
- [FastAPI 文件](https://fastapi.tiangolo.com/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FAISS 文件](https://github.com/facebookresearch/faiss)
