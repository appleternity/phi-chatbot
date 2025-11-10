# API 合約文件

## 概述

本文件定義了醫療聊天機器人應用程式的後端 API 與前端實作之間的合約規範。

**版本**: 0.2.0
**最後更新**: 2025-11-06

## 重大變更 (v0.2.0)

- ✅ 新增 `user_id` 必填欄位（使用者識別）
- ✅ `session_id` 改為選填（`null` = 建立新對話）
- ✅ 後端負責生成 UUID 作為 session_id
- ✅ 後端驗證 session 擁有權（403 錯誤）
- ✅ 前端自動生成並儲存 user_id

---

## API 端點

### 1. POST `/chat` - 聊天訊息端點

主要的對話端點，處理使用者訊息並返回 AI 助理的回應。

#### 請求 (Request)

**HTTP Method**: `POST`
**Content-Type**: `application/json`
**Timeout**: 120 秒（2 分鐘）

##### 請求格式 (Request Schema)

```typescript
interface ChatRequest {
  user_id: string              // 使用者識別碼（必填）
  session_id: string | null    // 對話 session 識別碼（選填，null = 建立新對話）
  message: string              // 使用者訊息內容（至少 1 個字元）
}
```

**Python (Pydantic) 定義**:
```python
class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Session ID (None = create new)")
    message: str = Field(..., min_length=1, description="User message")
```

##### 請求範例

**新對話（第一則訊息）**:
```json
{
  "user_id": "user_1730901234_abc123",
  "session_id": null,
  "message": "阿立哌唑的作用機制是什麼？"
}
```

**繼續現有對話**:
```json
{
  "user_id": "user_1730901234_abc123",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "副作用有哪些？"
}
```

#### 回應 (Response)

**HTTP Status**:
- `200 OK`: 請求成功
- `404 Not Found`: Session 不存在或已過期
- `403 Forbidden`: Session 屬於不同的 user_id
- `500 Internal Server Error`: 伺服器錯誤

**Content-Type**: `application/json`

##### 回應格式 (Response Schema)

```typescript
interface ChatResponse {
  session_id: string           // Session 識別碼（後端生成或現有）
  message: string              // AI 助理的回應內容
  agent: string                // 處理此訊息的 agent 名稱
  metadata?: Record<string, any>  // 額外的元數據（選填）
}
```

**Python (Pydantic) 定義**:
```python
class ChatResponse(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Agent response")
    agent: str = Field(..., description="Agent that handled the message")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")
```

**重要**: 後端 **永遠** 返回 `session_id`，無論是新建立或現有的對話。

##### 成功回應範例

**新對話回應（後端生成 UUID）**:
```json
{
  "session_id": "7f8c9a3b-1e2d-4c5b-8a9f-0123456789ab",
  "message": "阿立哌唑（Aripiprazole）是一種第二代抗精神病藥物...",
  "agent": "rag",
  "metadata": {
    "retrieved_documents": 5,
    "processing_time_ms": 1850
  }
}
```

**現有對話回應（返回相同 session_id）**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "常見副作用包括：頭痛、噁心、焦慮...",
  "agent": "rag",
  "metadata": {
    "retrieved_documents": 3
  }
}
```

##### 錯誤回應範例

**404 - Session 不存在**:
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found or expired"
}
```

**403 - Session 擁有權驗證失敗**:
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 does not belong to user user_1730901234_abc123"
}
```

**500 - 伺服器錯誤**:
```json
{
  "detail": "Error processing request: Database connection timeout"
}
```

#### 處理流程

1. **Session 建立或載入**:
   - 若 `session_id` 為 `null`: 使用 UUID4 生成新 session_id，建立 SessionData
   - 若 `session_id` 已提供: 載入現有 session，驗證 user_id 擁有權
   - 驗證失敗: 返回 404（不存在）或 403（擁有權錯誤）

2. **狀態構建**: 使用 session 資料建立 graph state

3. **Graph 調用**: 將訊息傳遞給 LangGraph，路由到適當的 agent

4. **回應生成**: Agent 生成回應（包含 RAG 檢索或直接對話）

5. **Session 更新**: 儲存 agent 分配與元數據到 session store

6. **返回結果**: 回傳 AI 助理的訊息與 session_id（新或現有）

---

### 2. GET `/health` - 健康檢查端點

用於檢查 API 服務的健康狀態和版本資訊。

#### 請求 (Request)

**HTTP Method**: `GET`
**Content-Type**: `application/json`

無請求參數。

#### 回應 (Response)

**HTTP Status**: `200 OK`
**Content-Type**: `application/json`

##### 回應格式 (Response Schema)

```typescript
interface HealthResponse {
  status: string    // 健康狀態（通常為 "healthy"）
  version: string   // API 版本號
}
```

**Python (Pydantic) 定義**:
```python
class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
```

##### 回應範例

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## 前端實作

### 技術棧

- **HTTP Client**: Axios
- **語言**: TypeScript
- **框架**: React

### API 客戶端配置

**檔案位置**: `frontend/src/services/api.ts`

```typescript
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 120 秒 - 為 RAG 操作預留較長時間
})
```

#### 配置說明

| 配置項 | 值 | 說明 |
|--------|-----|------|
| `baseURL` | `VITE_API_URL` 環境變數或 `http://localhost:8000` | API 基礎 URL |
| `timeout` | 120000 毫秒（2 分鐘） | 請求超時時間（RAG 檢索可能需要較長時間） |
| `Content-Type` | `application/json` | 固定為 JSON 格式 |

### API 函數

#### 1. `sendMessage()` - 發送聊天訊息

```typescript
async function sendMessage(
  userId: string,
  message: string,
  sessionId: string | null
): Promise<ChatResponse>
```

**參數**:
- `userId`: 使用者識別碼（必填）
- `message`: 使用者訊息內容（必填）
- `sessionId`: Session 識別碼（選填，`null` = 新對話）

**返回值**: Promise\<ChatResponse\>

**範例**:
```typescript
// 新對話（第一則訊息）
const response1 = await sendMessage(
  'user_1730901234_abc123',
  '阿立哌唑的作用機制是什麼？',
  null  // null 表示新對話
)
console.log(response1.session_id) // 後端生成的 UUID
console.log(response1.message)    // AI 助理的回應

// 繼續對話（後續訊息）
const response2 = await sendMessage(
  'user_1730901234_abc123',
  '副作用有哪些？',
  response1.session_id  // 使用後端返回的 session_id
)
console.log(response2.session_id) // 相同的 session_id
```

#### 2. `checkHealth()` - 檢查 API 健康狀態

```typescript
async function checkHealth(): Promise<{
  status: string;
  version: string
}>
```

**參數**: 無

**返回值**: Promise<{ status: string; version: string }>

**範例**:
```typescript
const health = await checkHealth()
console.log(health.status)  // "healthy"
console.log(health.version) // "0.1.0"
```

### 前端訊息模型

**檔案位置**: `frontend/src/types/index.ts`

```typescript
export interface Message {
  role: 'user' | 'assistant' | 'error'  // 訊息角色
  content: string                        // 訊息內容
  agent?: string                         // Agent 名稱（選填）
  timestamp: number                      // 時間戳記（毫秒）
}
```

#### 訊息角色說明

| 角色 | 說明 | 使用場景 |
|------|------|----------|
| `user` | 使用者訊息 | 使用者輸入的問題或陳述 |
| `assistant` | AI 助理訊息 | 從後端 API 獲得的回應 |
| `error` | 錯誤訊息 | API 調用失敗或其他錯誤情況 |

### 對話容器實作

**檔案位置**: `frontend/src/components/ChatContainer.tsx`

#### 核心處理流程

```typescript
const handleSendMessage = async (content: string) => {
  // 1. 驗證輸入
  if (!content.trim() || isLoading) return

  // 2. 添加使用者訊息到 UI
  const userMessage: Message = {
    role: 'user',
    content,
    timestamp: Date.now(),
  }
  setMessages((prev) => [...prev, userMessage])
  setIsLoading(true)

  try {
    // 3. 調用 API
    const response = await sendMessage(sessionId, content)

    // 4. 添加助理回應到 UI
    const assistantMessage: Message = {
      role: 'assistant',
      content: response.message,
      agent: response.agent,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, assistantMessage])
  } catch (error) {
    // 5. 錯誤處理
    const errorMessage: Message = {
      role: 'error',
      content: `無法獲取回應：${error instanceof Error ? error.message : '未知錯誤'}`,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, errorMessage])
  } finally {
    setIsLoading(false)
  }
}
```

#### 本地儲存

對話歷史會自動儲存到瀏覽器的 `localStorage`：

- **儲存鍵值**: `chat_history`
- **格式**: JSON 序列化的 `Message[]` 陣列
- **時機**: 每次 `messages` 狀態更新時

#### 匯出/匯入功能

**匯出格式**:
```json
{
  "format": "medical-chatbot-v1",
  "exportDate": "2025-11-06T12:34:56.789Z",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "messageCount": 10,
  "messages": [
    {
      "role": "user",
      "content": "問題內容",
      "timestamp": 1699876543210
    },
    {
      "role": "assistant",
      "content": "回應內容",
      "agent": "rag",
      "timestamp": 1699876545123
    }
  ]
}
```

---

## 後端實作細節

### Session 管理

**檔案位置**: `app/core/session_store.py`

#### Session 資料結構

```python
@dataclass
class SessionData:
    session_id: str
    user_id: str  # 新增：使用者識別碼
    assigned_agent: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

#### 儲存策略

- **實作**: `InMemorySessionStore`（記憶體內儲存）
- **TTL**: 可配置（預設從 `settings.session_ttl_seconds`）
- **清理**: 自動清理過期 session
- **使用者索引**: `_user_index: Dict[str, set[str]]` - user_id → session_ids 映射
- **查詢方法**: `get_user_sessions(user_id)` - 取得使用者所有 session（依更新時間降序）

### RAG Agent 檢索流程

**檔案位置**: `app/agents/rag_agent.py`

#### 處理步驟

1. **提取查詢**: 從最後一則使用者訊息提取查詢字串
2. **格式化歷史**: 將對話歷史格式化為可讀字串
3. **檢索文件**: 使用完整對話上下文進行語義搜尋
   - **Simple 策略**: 僅使用最後一則訊息
   - **Rerank 策略**: 僅使用最後一則訊息（重排提供語義豐富性）
   - **Advanced 策略**: 使用最後 5 則訊息（LLM 查詢擴展）
4. **格式化文件**: 將檢索到的文件格式化為 Markdown
5. **生成回應**: 使用 LLM 合成答案

#### 文件格式化

```markdown
# Retrieved Information

## Source 1: 文件名稱 > 章節標題 > 小節標題

### Content:
文件內容...

---

## Source 2: ...
```

---

## CORS 配置

**檔案位置**: `app/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 生產環境應限制特定 origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

⚠️ **安全性注意事項**:
- 目前允許所有來源（`"*"`）僅適用於開發環境
- 生產環境應設定特定的允許來源清單

---

## 錯誤處理

### 後端錯誤回應

所有端點在發生錯誤時返回標準格式：

```json
{
  "detail": "錯誤訊息描述"
}
```

**HTTP Status Codes**:
- `200 OK`: 請求成功
- `404 Not Found`: Session 不存在或已過期
- `403 Forbidden`: Session 屬於不同的 user_id（擁有權驗證失敗）
- `500 Internal Server Error`: 伺服器內部錯誤

### 前端錯誤處理

1. **網路錯誤**: Axios 自動處理 timeout 和網路錯誤
2. **404 錯誤**: Session 過期或無效，前端應清除 session_id 並以 `null` 重試
3. **403 錯誤**: 使用者擁有權驗證失敗，不應發生（前端邏輯錯誤）
4. **API 錯誤**: 捕獲異常並顯示錯誤訊息給使用者
5. **本地儲存錯誤**: Try-catch 包裹 localStorage 操作

### 錯誤處理流程

**404 處理範例** (Session 過期):
```typescript
try {
  const response = await sendMessage(userId, message, sessionId)
  // 處理成功回應
} catch (error) {
  if (axios.isAxiosError(error) && error.response?.status === 404) {
    // Session 已過期，清除並建立新 session
    clearSession()
    const response = await sendMessage(userId, message, null)
    setSessionId(response.session_id)
  } else {
    // 其他錯誤處理
  }
}
```

---

## 效能考量

### 超時設定

| 層級 | 超時時間 | 原因 |
|------|---------|------|
| 前端 Axios | 120 秒 | RAG 檢索可能需要較長時間 |
| 後端 Uvicorn | 120 秒（keep-alive） | 支援長時間 RAG 操作 |

### 預期效能指標

- **語義搜尋**: <100ms（pgvector 相似度搜尋）
- **重排**: <2s（20 個候選文件，Qwen3-Reranker-0.6B）
- **總搜尋延遲**: <2.1s（Top-5 結果）
- **LLM 生成**: 取決於模型和提示長度

---

## 版本歷史

### v0.1.0 (當前版本)

**功能**:
- 基本聊天對話功能
- Session 管理
- RAG 文件檢索
- 健康檢查端點
- 對話歷史匯出/匯入

**已知限制**:
- Session 僅儲存於記憶體（重啟後遺失）
- CORS 配置為開發環境設定
- 無身份驗證機制

---

## 未來改進計畫

1. **持久化 Session**: 使用 Redis 或資料庫儲存 session
2. **WebSocket 支援**: 實現串流式回應
3. **速率限制**: 防止濫用
4. **身份驗證**: 加入使用者認證機制（目前 user_id 由前端生成）
5. **詳細錯誤碼**: 定義更細緻的錯誤分類
6. **Session 列表 API**: `GET /users/{user_id}/sessions` - 取得使用者所有對話

---

## 從 v0.1.0 遷移至 v0.2.0

### 破壞性變更

1. **API 合約變更**:
   - ❌ 舊版: `ChatRequest { session_id: string, message: string }`
   - ✅ 新版: `ChatRequest { user_id: string, session_id: string | null, message: string }`

2. **Session 建立流程**:
   - ❌ 舊版: 前端生成 `session_{timestamp}_{random}` 格式的 session_id
   - ✅ 新版: 後端生成 UUID4 格式的 session_id

3. **前端函數簽名**:
   - ❌ 舊版: `sendMessage(sessionId: string, message: string)`
   - ✅ 新版: `sendMessage(userId: string, message: string, sessionId: string | null)`

### 不需遷移的部分

- ✅ SessionData 其他欄位（assigned_agent, metadata, created_at, updated_at）
- ✅ Graph state 和 agent 邏輯
- ✅ LangGraph checkpointing（仍使用 thread_id=session_id）
- ✅ RAG 檢索流程

### 遷移步驟

1. **後端更新**:
   - 更新 `app/models.py`, `app/core/session_store.py`, `app/main.py`
   - 重啟後所有舊 session 失效（in-memory 儲存）

2. **前端更新**:
   - 更新 `types`, `session.ts`, `api.ts`, `App.tsx`, `ChatContainer.tsx`
   - 使用者首次載入頁面會自動生成 user_id

3. **測試**:
   - 新使用者第一則訊息 → 後端生成 session_id → 後續使用該 session_id
   - 頁面重新整理 → user_id 和 session_id 從 localStorage 復原 → 對話繼續

### 新功能

- ✅ 使用者識別（user_id）
- ✅ Session 擁有權驗證（403 錯誤）
- ✅ 後端控制 session 生命週期（UUID 生成）
- ✅ 使用者 session 查詢功能（`get_user_sessions()` 方法）

---

## 附錄：完整型別定義

### TypeScript (前端)

```typescript
// Request/Response Types
export interface ChatRequest {
  user_id: string
  session_id: string | null
  message: string
}

export interface ChatResponse {
  session_id: string
  message: string
  agent: string
  metadata?: Record<string, any>
}

// UI Types
export interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
  agent?: string
  timestamp: number
}
```

### Python (後端)

```python
from typing import Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Session ID (None = create new)")
    message: str = Field(..., min_length=1, description="User message")

class ChatResponse(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Agent response")
    agent: str = Field(..., description="Agent that handled the message")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.2.0"

# Session Data
@dataclass
class SessionData:
    session_id: str
    user_id: str
    assigned_agent: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

---

## 參考資源

- **後端主檔案**: `app/main.py`
- **API 模型定義**: `app/models.py`
- **前端 API 客戶端**: `frontend/src/services/api.ts`
- **前端型別定義**: `frontend/src/types/index.ts`
- **對話容器**: `frontend/src/components/ChatContainer.tsx`
- **RAG Agent**: `app/agents/rag_agent.py`
