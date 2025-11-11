# SSE 串流聊天 API 契約文件

**版本**: 0.1.0
**最後更新**: 2025-11-06
**規格參考**: specs/003-sse-streaming/

---

## 目錄

- [概述](#概述)
- [API 端點](#api-端點)
- [請求格式](#請求格式)
- [回應格式 SSE 事件](#回應格式-sse-事件)
- [前端實作模式](#前端實作模式)
- [錯誤處理](#錯誤處理)
- [完整範例](#完整範例)
- [效能指標](#效能指標)

---

## 概述

本 API 使用 **Server-Sent Events (SSE)** 技術提供即時串流聊天回應。客戶端透過 HTTP POST 請求發送訊息，伺服器透過持久化的 HTTP 連線以事件流（event stream）方式回傳處理進度與生成的文字 token。

### 核心特性

- ✅ **即時 Token 串流**: 逐字元回傳 LLM 生成內容（目標延遲 <100ms）
- ✅ **處理階段指示器**: 明確標示檢索（retrieval）、重排序（reranking）、生成（generation）階段
- ✅ **中斷支援**: 客戶端可主動取消串流（AbortController）
- ✅ **會話感知**: 透過 session_id 維持對話上下文
- ✅ **錯誤處理**: 結構化錯誤事件與逾時保護（30 秒）
- ✅ **CORS 支援**: 允許跨域前端應用存取

### 技術棧

**後端**:
- FastAPI 0.115+ (非同步框架)
- LangGraph 0.6.0 (多代理編排)
- asyncio.timeout (逾時控制)
- StreamingResponse (SSE 傳輸)

**前端**:
- fetch() + ReadableStream API (SSE 解析)
- React Hooks (狀態管理)
- AbortController (取消機制)

---

## API 端點

### POST /chat

建立 SSE 串流連線以進行即時聊天。

**基礎 URL**: `http://localhost:8000` (開發環境)

**完整端點**: `POST http://localhost:8000/chat`

**HTTP Headers**:
```http
Content-Type: application/json
```

**回應 Headers**:
```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

## 請求格式

### ChatStreamRequest

**JSON Schema**:

| 欄位 | 型別 | 必填 | 說明 | 限制 |
|------|------|------|------|------|
| `message` | string | ✅ | 使用者訊息/問題 | 長度: 1-5000 字元 |
| `session_id` | string | ✅ | 會話識別碼（UUID 格式） | 格式: `^[a-f0-9-]{36}$` |

**範例請求**:

```json
{
  "message": "What are the side effects of aripiprazole?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**TypeScript 型別定義**:

```typescript
interface ChatStreamRequest {
  message: string        // 1-5000 字元
  session_id: string     // UUID v4 格式
}
```

**驗證規則**:

1. **message**:
   - 不可為空字串
   - 最小長度: 1 字元
   - 最大長度: 5000 字元
   - 自動修剪前後空白（前端實作）

2. **session_id**:
   - 必須符合 UUID 格式（8-4-4-4-12 十六進位數字）
   - 範例: `550e8400-e29b-41d4-a716-446655440000`
   - 前端生成方式: `crypto.randomUUID()`

---

## 回應格式: SSE 事件

### 事件流格式

所有事件遵循 SSE 標準格式：

```
data: <JSON_PAYLOAD>\n\n
```

每個事件為一個 JSON 物件，以 `data:` 前綴開頭，雙換行符 `\n\n` 結尾。

### StreamEvent 基礎結構

所有事件共享相同的基礎結構：

```typescript
interface StreamEvent {
  type: EventType      // 事件類型（discriminator）
  content?: any        // 事件內容（依類型而異）
  timestamp: string    // ISO8601 時間戳記
}
```

**欄位說明**:

| 欄位 | 型別 | 說明 | 格式範例 |
|------|------|------|----------|
| `type` | string | 事件類型識別符 | `"token"`, `"retrieval_start"` |
| `content` | any | 事件內容（可為 string 或 dict） | 見下方各事件說明 |
| `timestamp` | string | UTC 時間戳記 | `"2025-11-06T10:30:45.123Z"` |

---

### 事件類型詳解

#### 1. 處理階段事件（Stage Events）

**用途**: 標示系統處理進度（檢索、重排序）

##### 1.1 retrieval_start - 檢索開始

```json
{
  "type": "retrieval_start",
  "content": {
    "stage": "retrieval",
    "status": "started"
  },
  "timestamp": "2025-11-06T10:30:40.000Z"
}
```

**觸發時機**: RAG 代理啟動，開始向量資料庫檢索

**前端處理**: 顯示「正在搜尋知識庫...」載入指示器

---

##### 1.2 retrieval_complete - 檢索完成

```json
{
  "type": "retrieval_complete",
  "content": {
    "stage": "retrieval",
    "status": "complete",
    "doc_count": 5
  },
  "timestamp": "2025-11-06T10:30:42.456Z"
}
```

**觸發時機**: 向量檢索完成，已取得候選文件

**content 欄位**:
- `doc_count` (可選): 檢索到的文件數量

**前端處理**: 更新進度指示器為「正在分析相關性...」

---

##### 1.3 reranking_start - 重排序開始

```json
{
  "type": "reranking_start",
  "content": {
    "stage": "reranking",
    "status": "started"
  },
  "timestamp": "2025-11-06T10:30:42.500Z"
}
```

**觸發時機**: Qwen3-Reranker 模型啟動，重新評估文件相關性

**前端處理**: 顯示「正在分析相關性...」

**注意**: 僅在 `RETRIEVAL_STRATEGY="rerank"` 或 `"advanced"` 時發生

---

##### 1.4 reranking_complete - 重排序完成

```json
{
  "type": "reranking_complete",
  "content": {
    "stage": "reranking",
    "status": "complete",
    "selected": 3
  },
  "timestamp": "2025-11-06T10:30:43.200Z"
}
```

**觸發時機**: 重排序完成，準備生成回應

**content 欄位**:
- `selected` (可選): 最終選用的文件數量

**前端處理**: 切換為「正在生成回應...」或直接顯示串流 token

---

#### 2. Token 事件（Token Events）

**用途**: 即時傳送 LLM 生成的文字片段

```json
{
  "type": "token",
  "content": "Aripiprazole",
  "timestamp": "2025-11-06T10:30:43.250Z"
}
```

**觸發頻率**: 每個 LLM token 生成時（約每 50-100ms 一次）

**content 型別**: `string` - 單一文字片段（可能是單字、標點符號、空格）

**前端處理**:
1. 將 token 追加至暫存陣列: `tokens.push(event.content)`
2. 即時渲染: `tokens.join('')`
3. 自動捲動至最新內容

**範例串流序列**:
```
token: "Aripiprazole"
token: " is"
token: " an"
token: " atypical"
token: " antipsychotic"
token: "."
```

**效能要求**:
- 首個 token 延遲: <1 秒（FR-001, SC-001）
- 後續 token 延遲: <100ms（FR-002, SC-002）

---

#### 3. 完成事件（Done Event）

**用途**: 標示串流成功完成

```json
{
  "type": "done",
  "content": {},
  "timestamp": "2025-11-06T10:30:45.500Z"
}
```

**觸發時機**: 所有 token 傳送完畢，LangGraph 執行結束

**content 型別**: 空物件 `{}`

**前端處理**:
1. 設定 `isStreaming = false`
2. 將累積的 tokens 儲存為完整訊息
3. 儲存至 localStorage（會話歷史）
4. 清除載入指示器

**保證**: 每次成功串流必定以 `done` 事件結束（除非發生錯誤或取消）

---

#### 4. 錯誤事件（Error Events）

**用途**: 回報後端處理錯誤

```json
{
  "type": "error",
  "content": {
    "message": "Failed to retrieve documents",
    "code": "RETRIEVAL_ERROR"
  },
  "timestamp": "2025-11-06T10:30:40.789Z"
}
```

**content 結構**:

| 欄位 | 型別 | 說明 | 範例 |
|------|------|------|------|
| `message` | string | 使用者可讀的錯誤訊息 | `"Request timed out after 30 seconds"` |
| `code` | string | 程式化錯誤代碼 | `"TIMEOUT_ERROR"` |

**錯誤代碼列表**:

| 代碼 | 說明 | 觸發條件 |
|------|------|----------|
| `RETRIEVAL_ERROR` | 向量檢索失敗 | PostgreSQL 連線錯誤、embedding 生成失敗 |
| `PROCESSING_ERROR` | LangGraph 執行錯誤 | 代理節點處理異常 |
| `TIMEOUT_ERROR` | 請求逾時 | 超過 30 秒未完成 |
| `INTERNAL_ERROR` | 未預期的後端錯誤 | 系統層級異常（不暴露內部細節） |

**前端處理**:
1. 設定 `isStreaming = false`
2. 顯示錯誤訊息: `error.content.message`
3. 可選：依據 `code` 提供不同 UI 回饋（例如逾時建議重試）

**安全性**: 內部錯誤（`INTERNAL_ERROR`）不暴露敏感資訊

---

#### 5. 取消事件（Cancelled Event）

**用途**: 確認客戶端取消請求

```json
{
  "type": "cancelled",
  "content": {},
  "timestamp": "2025-11-06T10:30:44.000Z"
}
```

**觸發時機**:
1. 使用者點擊「停止生成」按鈕
2. `AbortController.abort()` 被呼叫
3. 客戶端中斷連線（`request.is_disconnected()`）

**content 型別**: 空物件 `{}`

**前端處理**:
1. 設定 `isStreaming = false`
2. 保留已累積的 tokens（不清除）
3. 可選：顯示「生成已停止」提示

**後端行為**:
- 立即停止 LangGraph 執行
- 回傳 `cancelled` 事件後關閉連線
- 不儲存未完成的回應至資料庫

---

## 前端實作模式

### React Hook: useStreamingChat

**檔案位置**: `frontend/src/hooks/useStreamingChat.ts`

**核心實作技術**:

| 技術 | 用途 | 規格參考 |
|------|------|----------|
| `fetch()` API | HTTP POST 請求 | T017 |
| `ReadableStream` | 讀取 SSE 事件流 | T017 |
| `AbortController` | 取消串流 | T018, FR-018 |
| `TextDecoder` | 解碼 UTF-8 二進位資料 | T020 |
| 緩衝區管理 | 處理不完整的 SSE 區塊 | T020 |

---

### 使用方式

```typescript
import { useStreamingChat } from '../hooks/useStreamingChat'

function ChatComponent() {
  const {
    tokens,           // string[] - 累積的 token 陣列
    stage,            // string - 當前處理階段
    isStreaming,      // boolean - 是否正在串流
    error,            // string | null - 錯誤訊息
    streamMessage,    // (msg, sessionId) => Promise<void> - 發起串流
    stopStreaming,    // () => void - 停止串流
    resetState        // () => void - 重置狀態
  } = useStreamingChat()

  const handleSend = async () => {
    await streamMessage("Hello", "session-123")
  }

  const handleStop = () => {
    stopStreaming()
  }

  return (
    <div>
      {/* 即時顯示串流內容 */}
      {isStreaming && <p>{tokens.join('')}</p>}

      {/* 停止按鈕 */}
      {isStreaming && (
        <button onClick={handleStop}>停止生成</button>
      )}

      {/* 錯誤提示 */}
      {error && <p>錯誤: {error}</p>}
    </div>
  )
}
```

---

### 狀態管理

**StreamingState 結構**:

```typescript
interface StreamingState {
  tokens: string[]        // 累積的 token 陣列
  stage: string           // 當前處理階段
  isStreaming: boolean    // 串流狀態
  error: string | null    // 錯誤訊息
}
```

**狀態轉換**:

```
初始狀態
  ↓ streamMessage()
正在串流 (isStreaming=true)
  ↓
  ├─ Token 事件 → 累積至 tokens[]
  ├─ Stage 事件 → 更新 stage
  ├─ Done 事件 → isStreaming=false (成功)
  ├─ Error 事件 → isStreaming=false, error=訊息
  └─ Cancelled 事件 → isStreaming=false (使用者取消)
```

---

### SSE 解析邏輯

**parseSSEChunk() 實作重點**:

```typescript
const parseSSEChunk = (chunk: string): StreamEvent[] => {
  // 1. 累積緩衝區（處理不完整區塊）
  buffer += chunk

  // 2. 以 \n\n 分割事件
  const lines = buffer.split('\n\n')

  // 3. 解析完整事件（保留最後不完整片段）
  for (let i = 0; i < lines.length - 1; i++) {
    const line = lines[i].trim()

    // 4. 過濾空行與註解
    if (!line || line.startsWith(':')) continue

    // 5. 移除 "data: " 前綴並解析 JSON
    if (line.startsWith('data: ')) {
      const jsonStr = line.substring(6)
      const event = JSON.parse(jsonStr)
      events.push(event)
    }
  }

  // 6. 保留不完整區塊至下次處理
  buffer = lines[lines.length - 1]

  return events
}
```

**為何需要緩衝區？**

SSE 資料流可能在任意位置切割，例如：

```
接收區塊 1: "data: {\"type\":\"tok"
接收區塊 2: "en\",\"content\":\"Hi\"}\n\n"
```

緩衝區確保完整事件才進行解析。

---

### 取消機制實作

**AbortController 整合**:

```typescript
// 1. 建立 AbortController
const abortController = new AbortController()

// 2. 傳入 fetch signal
const response = await fetch('/chat', {
  method: 'POST',
  body: JSON.stringify(request),
  signal: abortController.signal  // 連結取消訊號
})

// 3. 使用者點擊停止
const handleStop = () => {
  abortController.abort()  // 觸發 AbortError
}

// 4. 錯誤處理
try {
  // ... 串流處理 ...
} catch (error) {
  if (error.name === 'AbortError') {
    console.log('使用者取消串流')
  }
}
```

**後端偵測斷線**:

```python
async for event in graph.astream_events(...):
    # 每個迭代檢查客戶端連線
    if await request.is_disconnected():
        yield create_cancelled_event().to_sse_format()
        break
```

---

## 錯誤處理

### 錯誤分類與處理策略

| 錯誤類型 | HTTP 狀態碼 | SSE 事件 | 前端處理 | 重試建議 |
|----------|-------------|----------|----------|----------|
| 請求驗證失敗 | 422 | - | 顯示表單錯誤 | ❌ 不重試（修正輸入） |
| 網路錯誤 | - | - | `catch (error)` | ✅ 自動重試（指數退避） |
| 後端處理錯誤 | 200 (串流中) | `error` 事件 | 顯示錯誤訊息 | ✅ 使用者手動重試 |
| 逾時 (30s) | 200 (串流中) | `error` (TIMEOUT_ERROR) | 提示重試 | ✅ 使用者手動重試 |
| 使用者取消 | 200 (串流中) | `cancelled` 事件 | 保留已生成內容 | ✅ 使用者可再次發送 |

---

### 詳細錯誤處理範例

#### 1. 請求驗證錯誤（422 Unprocessable Entity）

**觸發條件**:
- `message` 為空字串
- `session_id` 格式不符合 UUID

**回應範例**:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "message"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

**前端處理**:
```typescript
const response = await fetch('/chat', { ... })

if (response.status === 422) {
  const errors = await response.json()
  // 顯示表單驗證錯誤
  console.error('驗證失敗:', errors.detail)
  return
}
```

---

#### 2. 網路錯誤（無法連線）

**觸發條件**:
- 伺服器未啟動
- DNS 解析失敗
- CORS 錯誤

**前端處理**:
```typescript
try {
  await streamMessage(message, sessionId)
} catch (error) {
  if (error instanceof TypeError) {
    // 網路錯誤
    setError('無法連線至伺服器，請檢查網路連線')
  }
}
```

---

#### 3. 後端處理錯誤（SSE error 事件）

**後端錯誤傳播**:
```python
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    yield create_error_event(
        "An unexpected error occurred",
        "INTERNAL_ERROR"
    ).to_sse_format()
```

**前端處理**:
```typescript
if (isErrorEvent(event)) {
  setError(event.content.message)
  setIsStreaming(false)
  // 可選：依 code 顯示不同提示
  if (event.content.code === 'TIMEOUT_ERROR') {
    showRetryButton()
  }
}
```

---

#### 4. 逾時保護（30 秒）

**後端實作**:
```python
async with asyncio.timeout(30):  # FR-014
    async for event in graph.astream_events(...):
        # ... 處理事件 ...
```

**逾時錯誤事件**:
```json
{
  "type": "error",
  "content": {
    "message": "Request timed out after 30 seconds",
    "code": "TIMEOUT_ERROR"
  },
  "timestamp": "2025-11-06T10:31:10.000Z"
}
```

**前端處理**:
- 顯示「請求逾時，請稍後重試」
- 提供「重新發送」按鈕

---

## 完整範例

### 範例 1: 成功串流完整流程

**請求**:
```http
POST /chat HTTP/1.1
Content-Type: application/json

{
  "message": "What are the side effects of aripiprazole?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**回應事件序列**:

```
data: {"type":"retrieval_start","content":{"stage":"retrieval","status":"started"},"timestamp":"2025-11-06T10:30:40.000Z"}

data: {"type":"retrieval_complete","content":{"stage":"retrieval","status":"complete","doc_count":5},"timestamp":"2025-11-06T10:30:42.456Z"}

data: {"type":"reranking_start","content":{"stage":"reranking","status":"started"},"timestamp":"2025-11-06T10:30:42.500Z"}

data: {"type":"reranking_complete","content":{"stage":"reranking","status":"complete","selected":3},"timestamp":"2025-11-06T10:30:43.200Z"}

data: {"type":"token","content":"Aripiprazole","timestamp":"2025-11-06T10:30:43.250Z"}

data: {"type":"token","content":" is","timestamp":"2025-11-06T10:30:43.300Z"}

data: {"type":"token","content":" an","timestamp":"2025-11-06T10:30:43.350Z"}

data: {"type":"token","content":" atypical","timestamp":"2025-11-06T10:30:43.400Z"}

data: {"type":"token","content":" antipsychotic","timestamp":"2025-11-06T10:30:43.450Z"}

data: {"type":"token","content":".","timestamp":"2025-11-06T10:30:43.500Z"}

data: {"type":"done","content":{},"timestamp":"2025-11-06T10:30:45.500Z"}

```

**前端處理時間軸**:

| 時間點 | 事件 | UI 狀態 |
|--------|------|---------|
| T+0ms | 發送請求 | 顯示「正在發送...」 |
| T+100ms | `retrieval_start` | 顯示「正在搜尋知識庫...」 |
| T+2456ms | `retrieval_complete` | 顯示「已找到 5 篇相關文獻」 |
| T+2500ms | `reranking_start` | 顯示「正在分析相關性...」 |
| T+3200ms | `reranking_complete` | 顯示「正在生成回應...」 |
| T+3250ms | 首個 `token` | 開始顯示文字 "Aripiprazole" |
| T+3500ms | 最後 `token` | 完整文字 "Aripiprazole is an atypical antipsychotic." |
| T+5500ms | `done` | 儲存訊息，清除載入狀態 |

**總時長**: 5.5 秒
**首個 token 延遲**: 3.25 秒（符合 <1s 目標？需優化）

---

### 範例 2: 使用者中斷串流

**請求**:
```json
{
  "message": "Explain the mechanism of SSRI medications",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**事件序列（中斷前）**:
```
data: {"type":"retrieval_start","content":{"stage":"retrieval","status":"started"},"timestamp":"..."}

data: {"type":"token","content":"Selective","timestamp":"..."}

data: {"type":"token","content":" serotonin","timestamp":"..."}

data: {"type":"token","content":" reuptake","timestamp":"..."}
```

**使用者點擊「停止」按鈕 → 觸發 `abortController.abort()`**

**最後事件**:
```
data: {"type":"cancelled","content":{},"timestamp":"2025-11-06T10:30:44.000Z"}

```

**前端狀態**:
- `isStreaming = false`
- `tokens = ["Selective", " serotonin", " reuptake"]`
- 顯示「生成已停止」提示

**保留行為**: 已累積的 tokens 不會清除，使用者可查看部分生成內容。

---

### 範例 3: 後端錯誤處理

**請求**:
```json
{
  "message": "What is fluoxetine?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**假設場景**: PostgreSQL 資料庫連線失敗

**錯誤事件**:
```
data: {"type":"retrieval_start","content":{"stage":"retrieval","status":"started"},"timestamp":"..."}

data: {"type":"error","content":{"message":"Failed to retrieve documents","code":"RETRIEVAL_ERROR"},"timestamp":"2025-11-06T10:30:41.000Z"}

```

**前端處理**:
```typescript
if (isErrorEvent(event)) {
  setError("無法搜尋知識庫，請稍後重試")
  setIsStreaming(false)
  showRetryButton()
}
```

**UI 顯示**:
```
❌ 錯誤: 無法搜尋知識庫，請稍後重試
[重新發送] 按鈕
```

---

## 效能指標

### 功能性需求（Functional Requirements）

| 編號 | 需求 | 目標 | 實測表現 | 達成狀態 |
|------|------|------|----------|----------|
| FR-001 | 即時 Token 串流 | 逐 token 傳送 | ✅ 實作 | ✅ |
| FR-002 | Token 延遲 | <100ms | 待測試 | 🟡 |
| FR-004 | 處理階段指示器 | 檢索、重排序、生成 | ✅ 實作 | ✅ |
| FR-006 | SSE 傳輸機制 | text/event-stream | ✅ 實作 | ✅ |
| FR-010 | 錯誤處理 | 結構化錯誤事件 | ✅ 實作 | ✅ |
| FR-011 | 連線清理 | 自動關閉 | ✅ FastAPI 處理 | ✅ |
| FR-014 | 逾時保護 | 30 秒 | ✅ asyncio.timeout | ✅ |
| FR-018 | 客戶端取消 | AbortController | ✅ 實作 | ✅ |
| FR-019 | 斷線偵測 | is_disconnected() | ✅ 實作 | ✅ |

---

### 成功標準（Success Criteria）

| 編號 | 標準 | 目標 | 實測 | 達成 |
|------|------|------|------|------|
| SC-001 | 首個 Token 延遲 | <1 秒 | 待測試 | 🟡 |
| SC-002 | Token 間延遲 | <100ms | 待測試 | 🟡 |
| SC-006 | 並發會話支援 | 10+ | 待壓測 | 🟡 |

**圖例**:
- ✅ 已達成
- 🟡 待測試/優化
- ❌ 未達成

---

### 效能優化建議

#### 後端優化

1. **檢索階段**:
   - 使用 pgvector IVFFlat 索引（目前為暴力搜尋）
   - 預載入 embedding 模型（`PRELOAD_MODELS=True`）
   - 快取常見查詢的向量表示

2. **重排序階段**:
   - 批次處理重排序請求（batch_size > 1）
   - 使用 GPU 加速（MPS/CUDA）
   - 考慮跳過重排序（`RETRIEVAL_STRATEGY=simple`）

3. **生成階段**:
   - 使用更快的 LLM（Qwen3-Max → Qwen3-Turbo）
   - 啟用 vLLM 或 TGI 推理引擎
   - 調整溫度參數（temperature=0.0 最快）

#### 前端優化

1. **渲染優化**:
   - 使用 `React.memo()` 避免不必要的重渲染
   - 虛擬化長對話列表（react-window）
   - 防抖處理捲動事件

2. **網路優化**:
   - 啟用 HTTP/2 多工傳輸
   - 壓縮 JSON payload（gzip）
   - 使用 CDN 部署前端資源

---

## 附錄

### A. 相關規格文件

- **資料模型**: `specs/003-sse-streaming/data-model.md`
- **技術任務**: `specs/003-sse-streaming/tasks.md`
- **實作計畫**: `specs/003-sse-streaming/plan.md`

### B. 後端原始碼參考

- **主應用**: `app/main.py` (L170-205)
- **串流端點**: `app/api/streaming.py`
- **資料模型**: `app/models.py` (L32-293)
- **圖建構器**: `app/graph/builder.py`

### C. 前端原始碼參考

- **串流 Hook**: `frontend/src/hooks/useStreamingChat.ts`
- **型別定義**: `frontend/src/types/streaming.ts`
- **聊天容器**: `frontend/src/components/ChatContainer.tsx`
- **聊天輸入**: `frontend/src/components/ChatInput.tsx`

### D. 開發環境設定

**後端啟動**:
```bash
# 1. 啟動 PostgreSQL
docker-compose up -d

# 2. 建立資料庫 schema
python -m app.db.schema

# 3. 索引文件
python -m src.embeddings.cli index --input data/chunking_final

# 4. 啟動 FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端啟動**:
```bash
# 1. 安裝依賴
cd frontend && npm install

# 2. 設定 API URL（.env）
echo "VITE_API_URL=http://localhost:8000" > .env

# 3. 啟動開發伺服器
npm run dev
```

### E. 測試指令

**健康檢查**:
```bash
curl http://localhost:8000/health
```

**SSE 串流測試（curl）**:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is sertraline?",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }' \
  -N  # 禁用緩衝以即時顯示
```

**前端開發者工具測試**:
```javascript
// 開啟瀏覽器 console
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Hello',
    session_id: crypto.randomUUID()
  })
})

const reader = response.body.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  console.log(decoder.decode(value))
}
```

---

**文件版本**: v1.0
**維護者**: Medical Chatbot Team
**最後更新**: 2025-11-06
