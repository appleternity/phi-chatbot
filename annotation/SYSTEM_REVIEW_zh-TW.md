# 標註系統 - 完整技術審查報告

**審查日期**: 2025-11-16
**分支**: `001-chatbot-annotation`
**審查者**: Claude Code

---

## 執行摘要

標註系統是一個**全端多機器人聊天應用程式**,具備串流聊天功能、使用者身份驗證和回饋收集系統。系統由三個主要元件組成:

1. **後端**: FastAPI 伺服器搭配 PostgreSQL 資料庫
2. **前端**: React + TypeScript 單頁應用程式
3. **基礎設施**: Docker Compose 編排

### 系統目的

提供平台讓使用者與多個聊天機器人人格互動(透過 OpenRouter API 配置),並透過評分和評論提供回饋。系統將所有對話和回饋持久化儲存在 PostgreSQL 資料庫中。

---

## 架構概覽

### 高階架構

```
┌─────────────────┐     HTTP/WebSocket      ┌──────────────────┐
│                 │ ◄────────────────────── │                  │
│  React 前端     │                         │  FastAPI 後端    │
│  (埠號 5173/80) │ ─────────────────────► │   (埠號 8000)    │
│                 │     JWT 認證 + 串流      │                  │
└─────────────────┘                         └────────┬─────────┘
                                                     │
                                                     │ SQL
                                                     ▼
                                            ┌─────────────────┐
                                            │   PostgreSQL    │
                                            │   (埠號 5432)   │
                                            └─────────────────┘
                                                     ▲
                                                     │
                                            ┌────────┴─────────┐
                                            │  OpenRouter API  │
                                            │  (LLM 提供商)    │
                                            └──────────────────┘
```

### 技術堆疊

| 層級 | 技術 | 版本 | 用途 |
|-------|-----------|---------|---------|
| **前端** | React | 19.2.0 | UI 框架 |
| | TypeScript | 5.9.3 | 型別安全 |
| | Vite | 7.2.2 | 建置工具 |
| | Tailwind CSS | 3.4.18 | 樣式設計 |
| | React Router | 7.9.6 | 客戶端路由 |
| **後端** | FastAPI | 0.121.2+ | API 框架 |
| | SQLAlchemy | 2.0.44 | ORM |
| | Uvicorn | 0.38.0+ | ASGI 伺服器 |
| | psycopg2 | 2.9.0+ | PostgreSQL 驅動程式 |
| | python-jose | 3.5.0 | JWT 身份驗證 |
| | httpx | 0.28.1+ | 非同步 HTTP 客戶端 |
| **資料庫** | PostgreSQL | 15 | 主要資料儲存 |
| **部署** | Docker Compose | 3.9 | 容器編排 |
| | Nginx | Alpine | 前端網頁伺服器 |

---

## 後端程式碼審查

### 目錄結構

```
annotation_backend/
├── main.py                 # FastAPI 應用程式進入點
├── requirements.txt        # Python 依賴套件
├── Dockerfile             # 後端容器定義
├── .dockerignore          # Docker 建置排除檔案
├── routes/                # API 端點處理器
│   ├── auth.py           # 註冊與登入
│   ├── chat.py           # 聊天串流與回饋
│   └── bot.py            # 機器人配置
├── schemas/               # Pydantic 模型
│   ├── message.py        # 聊天訊息模式
│   └── user.py           # 使用者模式
├── db/                    # 資料庫層
│   ├── base.py           # SQLAlchemy 設定
│   ├── models.py         # ORM 模型 (User, Message)
│   └── crud.py           # 資料庫操作
├── core/                  # 核心工具
│   ├── config.py         # 環境配置
│   └── security.py       # 密碼雜湊與 JWT
├── data/                  # 靜態配置
│   └── bots.json         # 機器人設定檔
└── prompts.py            # 機器人系統提示詞
```

---

### 核心程式碼分析

#### 1. main.py - 應用程式進入點

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth, bot, chat

app = FastAPI(title="Chatbot Backend Service")

# CORS 配置
origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 資料庫表格自動建立 (開發環境)
from db.base import Base, engine
from db import models

@app.on_event("startup")
def on_startup():
    print("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)

# 路由註冊
app.include_router(auth.router)
app.include_router(bot.router)
app.include_router(chat.router)
```

**程式碼特點:**
✅ 使用 FastAPI 事件鉤子自動建立資料表
✅ CORS 配置明確指定允許來源
⚠️ `allow_credentials=True` 搭配萬用來源存在安全風險
⚠️ 生產環境應使用資料庫遷移工具而非自動建表

---

#### 2. routes/chat.py - 串流聊天核心邏輯

**關鍵功能: 句子邊界檢測與串流**

```python
ENDINGS = ["|", "\n\n", "\n"]  # 句子結束符號

async def event_generator():
    buffer = ""
    sentence_buffer = ""

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", settings.OPENROUTER_URL,
                                headers=headers, json=payload) as response:
            async for chunk in response.aiter_text():
                # 檢查取消事件
                if cancel_event.is_set():
                    print(f"Stream cancelled by server for user {user_id}")
                    break

                # 檢查客戶端斷線
                if await request.is_disconnected():
                    print(f"Client disconnected for user {user_id}")
                    cancel_event.set()
                    break

                buffer += chunk

                # 解析 SSE 格式
                while True:
                    line_end = buffer.find("\n")
                    if line_end == -1:
                        break

                    line = buffer[:line_end].strip()
                    buffer = buffer[line_end + 1:]

                    if not line or not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data == "[DONE]":
                        # 發送剩餘句子
                        trimmed = sentence_buffer.strip()
                        if trimmed:
                            msg_id = _save_message(trimmed, user_id, user_data.bot_id, db)
                            yield json.dumps({"response": trimmed, "message_id": msg_id}) + "\n"
                        raise StopAsyncIteration

                    # 解析 JSON 並累積句子
                    data_obj = json.loads(data)
                    delta = data_obj["choices"][0]["delta"]
                    content = delta.get("content", "")

                    if content:
                        sentence_buffer += content
                        split_indices = []

                        # 找出所有句子邊界
                        for end in ENDINGS:
                            idx = sentence_buffer.find(end)
                            while idx != -1:
                                split_indices.append(idx + len(end))
                                idx = sentence_buffer.find(end, idx + len(end))

                        # 發送最早的完整句子
                        if split_indices:
                            split_pos = min(split_indices)
                            sentence = sentence_buffer[:split_pos].strip()
                            if sentence and sentence not in ENDINGS:
                                msg_id = _save_message(sentence, user_id, user_data.bot_id, db)
                                yield json.dumps({"response": sentence, "message_id": msg_id}) + "\n"
                            sentence_buffer = sentence_buffer[split_pos:].lstrip()
```

**程式碼分析:**

✅ **優點:**
- 雙層緩衝機制: `buffer` (原始資料) + `sentence_buffer` (累積文字)
- 支援多種句子結束符號
- 客戶端取消機制完善 (`AbortController` + `cancel_event`)
- 錯誤處理妥善 (try-except-finally)

⚠️ **改進建議:**
1. **句子邊界過於簡單**: `|` 符號可能誤切分技術內容
2. **未處理 JSON 解析錯誤**: 惡意/損壞資料可能導致崩潰
3. **資料庫寫入頻繁**: 每句話一次 commit,高負載下效能問題
4. **未記錄完整回應**: 若使用者中斷,部分內容遺失

**建議優化:**
```python
# 改進 1: 更智能的句子分割
ENDINGS = ["。", "！", "？", ".", "!", "?", "\n\n"]

# 改進 2: 批次提交
messages_to_commit = []
if sentence and sentence not in ENDINGS:
    msg = _create_message(sentence, user_id, user_data.bot_id)
    messages_to_commit.append(msg)

    # 每 5 句提交一次
    if len(messages_to_commit) >= 5:
        db.add_all(messages_to_commit)
        db.commit()
        messages_to_commit.clear()
```

---

#### 3. routes/auth.py - 使用者認證

**註冊流程程式碼:**

```python
@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(username=req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists.")

    # 建立新使用者
    new_user = User(username=req.username, password_hash=hash_password(req.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 為所有機器人建立歡迎訊息
    with open(settings.BOT_INFO_PATH, "r", encoding="utf-8") as f:
        bots = json.load(f)

    for bot in bots:
        welcome_message = Message(
            id=str(uuid4()),
            user_id=new_user.id,
            bot_id=bot["id"],
            sender="bot",
            text=bot["welcome_message"],
        )
        db.add(welcome_message)

    db.commit()
    return {"user_id": new_user.id, "username": new_user.username}
```

**程式碼分析:**

✅ **安全性:**
- 使用 Argon2 雜湊演算法 (`hash_password`)
- 檢查使用者名稱重複
- 密碼不以明文儲存

⚠️ **潛在問題:**
1. **無輸入驗證**: 使用者名稱可包含特殊字元
2. **無密碼強度要求**: 允許弱密碼
3. **歡迎訊息建立低效**: 每個機器人一次資料庫插入
4. **註冊端點暴露**: 任何人都能註冊

**建議改進:**
```python
# 加入 Pydantic 驗證
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, regex="^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)

# 批次建立歡迎訊息
welcome_messages = [
    Message(id=str(uuid4()), user_id=new_user.id, bot_id=bot["id"],
            sender="bot", text=bot["welcome_message"])
    for bot in bots
]
db.add_all(welcome_messages)
db.commit()
```

---

#### 4. db/models.py - 資料庫模型

```python
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    bot_id = Column(String, index=True)
    sender = Column(String)  # 'user' | 'bot'
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    rating = Column(String, nullable=True)  # 'up' | 'down' | NULL
    comment = Column(Text, nullable=True)
    user = relationship("User", back_populates="messages")
```

**程式碼分析:**

✅ **優點:**
- 使用 UUID 作為主鍵 (避免序列可預測性)
- 外鍵關係定義清楚
- `bot_id` 有索引 (查詢效能)
- 使用 `Text` 型別儲存長訊息

⚠️ **改進建議:**
1. **缺少複合索引**: `(user_id, bot_id, created_at)` 可加速歷史查詢
2. **sender 欄位未約束**: 應使用 Enum 限制值
3. **rating 欄位未約束**: 應使用 Enum 或 CHECK 約束
4. **時間戳使用 utcnow**: 應考慮時區支援

**建議改進:**
```python
from sqlalchemy import Enum as SQLEnum
import enum

class SenderType(enum.Enum):
    USER = "user"
    BOT = "bot"

class RatingType(enum.Enum):
    UP = "up"
    DOWN = "down"

class Message(Base):
    __tablename__ = "messages"
    # ... 其他欄位 ...
    sender = Column(SQLEnum(SenderType), nullable=False)
    rating = Column(SQLEnum(RatingType), nullable=True)

    __table_args__ = (
        Index('idx_user_bot_time', 'user_id', 'bot_id', 'created_at'),
    )
```

---

#### 5. core/security.py - 安全機制

```python
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
```

**程式碼分析:**

✅ **安全最佳實踐:**
- 使用 Argon2 (2015年密碼雜湊競賽冠軍)
- JWT 有過期時間
- 分離雜湊和驗證邏輯

⚠️ **建議改進:**
1. **JWT 無刷新機制**: 30 分鐘後強制重新登入
2. **無令牌撤銷**: 無法讓舊令牌失效
3. **密鑰管理**: 從環境變數讀取,無輪替機制

---

## 前端程式碼審查

### 目錄結構

```
annotation_frontend/
├── src/
│   ├── main.tsx              # React 進入點
│   ├── App.tsx               # 路由配置
│   ├── pages/
│   │   ├── LoginPage.tsx     # 登入頁面
│   │   └── ChatPage.tsx      # 主聊天介面
│   ├── components/
│   │   ├── BotSelector.tsx   # 機器人選擇側邊欄
│   │   └── ChatWindow.tsx    # 聊天視窗 UI
│   ├── services/
│   │   ├── authService.ts    # 登入/登出邏輯
│   │   ├── botService.ts     # 獲取機器人列表
│   │   └── chatService.ts    # 聊天 API 呼叫
│   └── types/
│       └── chat.ts           # TypeScript 型別定義
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

---

### 核心程式碼分析

#### 1. App.tsx - 路由與認證邏輯

```typescript
import { jwtDecode } from "jwt-decode";

interface DecodedToken {
  sub: string;
  exp: number;
}

function isTokenValid(token: string | null): boolean {
  if (!token) return false;
  try {
    const decoded = jwtDecode<DecodedToken>(token);
    if (!decoded.exp) return false;
    return decoded.exp * 1000 > Date.now(); // 檢查過期時間
  } catch {
    return false;
  }
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = () => {
      const token = getToken();
      if (isTokenValid(token)) {
        setIsAuthenticated(true);
      } else {
        logout();
        setIsAuthenticated(false);
      }
      setIsLoading(false);
    };

    checkAuth();

    // 監聽跨分頁登入事件
    window.addEventListener("storage", checkAuth);
    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={isAuthenticated ? "/chat" : "/login"} />} />
        <Route path="/login" element={isAuthenticated ? <Navigate to="/chat" /> : <LoginPage />} />
        <Route path="/chat" element={isAuthenticated ? <ChatPage /> : <Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**程式碼分析:**

✅ **優點:**
- 客戶端 JWT 驗證
- 跨分頁同步登入狀態 (`storage` 事件)
- 受保護路由重導向

⚠️ **改進建議:**
1. **令牌更新邏輯缺失**: 接近過期時應自動刷新
2. **無錯誤邊界**: 解碼失敗可能導致白屏
3. **載入狀態過於簡單**: 可加入骨架屏

---

#### 2. ChatPage.tsx - 聊天頁面核心邏輯

**串流處理程式碼:**

```typescript
const handleSendMessage = async (text: string) => {
  if (!activeBotId) return;

  const newUserMessage: ChatMessage = {
    id: crypto.randomUUID(),
    sender: "user",
    text,
  };

  setChatHistories(prev => ({
    ...prev,
    [activeBotId]: [...(prev[activeBotId] || []), newUserMessage],
  }));

  setIsBotLoading(true);
  controllerRef.current = new AbortController();
  let isFirstChunk = true;

  try {
    await fetchBotStreamResponse(
      text,
      activeBotId,
      async (chunk, messageId) => {
        const trimmed = chunk.trim();
        if (!trimmed) return;

        // 第一句後延遲 3 秒顯示下一句
        if (!isFirstChunk) {
          await new Promise(res => setTimeout(res, 3000));
        } else {
          isFirstChunk = false;
        }

        const newBubble: ChatMessage = {
          id: messageId,
          sender: "bot",
          text: trimmed,
          rating: null,
          comment: null,
        };

        setChatHistories(prev => ({
          ...prev,
          [activeBotId]: [...(prev[activeBotId] || []), newBubble],
        }));
      },
      controllerRef
    );
  } catch (err) {
    console.error("Streaming error:", err);
  } finally {
    setIsBotLoading(false);
    controllerRef.current = null;
  }
};
```

**程式碼分析:**

✅ **優點:**
- 樂觀更新 (立即顯示使用者訊息)
- 支援取消串流 (`AbortController`)
- 錯誤處理完善

⚠️ **問題:**
1. **硬編碼延遲**: 3 秒延遲寫死在程式碼中
2. **無錯誤提示**: 串流失敗無使用者回饋
3. **狀態更新效能**: 每句話都觸發整個歷史重新渲染

**建議優化:**
```typescript
// 1. 可配置延遲
const CHUNK_DELAY = parseInt(import.meta.env.VITE_CHUNK_DELAY || '3000');

// 2. 錯誤提示
catch (err) {
  console.error("Streaming error:", err);
  // 加入錯誤訊息到聊天視窗
  setChatHistories(prev => ({
    ...prev,
    [activeBotId]: [...(prev[activeBotId] || []), {
      id: crypto.randomUUID(),
      sender: "bot",
      text: "抱歉,發生錯誤,請稍後再試。",
      isError: true
    }],
  }));
}

// 3. 使用 useReducer 優化狀態更新
const chatReducer = (state, action) => {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return {
        ...state,
        [action.botId]: [...(state[action.botId] || []), action.message]
      };
    // ...其他動作
  }
};
```

---

#### 3. ChatWindow.tsx - 聊天視窗元件

**自動捲動邏輯:**

```typescript
const [isNearBottom, setIsNearBottom] = useState(true);

const handleScroll = () => {
  if (messagesContainerRef.current) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
    setIsNearBottom(distanceFromBottom < 100); // 100px 閾值
  }
};

useEffect(() => {
  // 只在接近底部時自動捲動
  if (isNearBottom) {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }
}, [history, isNearBottom]);
```

**程式碼分析:**

✅ **優秀設計:**
- 尊重使用者捲動行為
- 100px 閾值合理
- 平滑捲動效果

⚠️ **可優化:**
1. **每次 scroll 都觸發狀態更新**: 可使用節流
2. **無虛擬化**: 長對話會有效能問題

**建議優化:**
```typescript
import { useMemo, useCallback } from 'react';
import throttle from 'lodash/throttle';

const handleScroll = useCallback(
  throttle(() => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
      setIsNearBottom(distanceFromBottom < 100);
    }
  }, 200), // 每 200ms 最多執行一次
  []
);
```

---

#### 4. services/chatService.ts - API 串流處理

```typescript
export async function fetchBotStreamResponse(
  message: string,
  botId: string,
  onChunk: (chunk: string, messageId: string) => Promise<void>,
  controllerRef: React.MutableRefObject<AbortController | null>
): Promise<void> {
  const token = getToken();
  if (!token) throw new Error('未認證');

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, bot_id: botId }),
    signal: controllerRef.current?.signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('無法讀取串流');

  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n').filter(Boolean);

      for (const line of lines) {
        if (line === '[STREAM_END]') return;

        try {
          const parsed = JSON.parse(line);
          await onChunk(parsed.response, parsed.message_id);
        } catch (e) {
          console.warn('解析失敗:', line);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

**程式碼分析:**

✅ **優點:**
- 正確使用 Streams API
- `releaseLock()` 資源清理
- 解析錯誤不中斷串流

⚠️ **改進建議:**
1. **未處理部分 JSON**: 換行切分可能切斷 JSON
2. **錯誤處理不完整**: 網路斷線無重試

**建議優化:**
```typescript
// 處理跨 chunk 的 JSON
let buffer = '';

for (const line of lines) {
  buffer += line;

  try {
    const parsed = JSON.parse(buffer);
    await onChunk(parsed.response, parsed.message_id);
    buffer = ''; // 清空緩衝
  } catch (e) {
    // JSON 不完整,繼續累積
    if (buffer.length > 10000) {
      // 防止記憶體洩漏
      console.error('緩衝區過大,重置');
      buffer = '';
    }
  }
}
```

---

## Docker 設定審查

### docker-compose.annotation.yml

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:15
    restart: always
    container_name: annotation-postgres
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_HOST: ${POSTGRES_HOST}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./annotation_backend
    container_name: annotation-backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres

  frontend:
    build: ./annotation_frontend
    container_name: annotation-frontend
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

**配置分析:**

✅ **優點:**
- 清晰的服務分離
- 持久化資料卷
- 依賴關係定義

⚠️ **問題:**

1. **缺少健康檢查**
```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
    interval: 10s
    timeout: 5s
    retries: 5

backend:
  depends_on:
    postgres:
      condition: service_healthy  # 等待資料庫就緒
```

2. **PostgreSQL 埠號暴露**
- 生產環境不應暴露 5432
- 建議只在內部網路通訊

3. **無資源限制**
```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
      reservations:
        cpus: '0.5'
        memory: 512M
```

4. **網路未明確定義**
```yaml
networks:
  annotation-network:
    driver: bridge

services:
  postgres:
    networks:
      - annotation-network
```

---

### annotation_backend/Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install -r requirements.txt

# 複製後端程式碼
COPY . .

# 執行 FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dockerfile 分析:**

⚠️ **重大問題:**

1. **無多階段建置**: 包含不必要的建置工具
2. **以 root 執行**: 安全風險
3. **未優化快取層**: 依賴變更導致全部重建
4. **無健康檢查**: Docker 無法判斷服務狀態

**建議改進:**

```dockerfile
# 多階段建置
FROM python:3.12-slim AS builder

WORKDIR /app

# 只複製依賴檔案
COPY requirements.txt .

# 安裝到獨立目錄
RUN pip install --no-cache-dir --user -r requirements.txt

# 生產階段
FROM python:3.12-slim

# 建立非 root 使用者
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 從建置階段複製已安裝的套件
COPY --from=builder /root/.local /home/appuser/.local

# 複製應用程式碼
COPY --chown=appuser:appuser . .

# 切換到非 root 使用者
USER appuser

# 設定 PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# 健康檢查
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/bots')"

# 執行應用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### annotation_frontend/Dockerfile

```dockerfile
# 階段 1: 建置前端
FROM node:20 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build   # 建立 dist/

# 階段 2: 使用 nginx 提供服務
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Dockerfile 分析:**

✅ **優點:**
- 多階段建置 (減少映像大小)
- 使用 Alpine (輕量化)
- 只複製建置產物

⚠️ **建議改進:**

1. **快取優化**: 分離依賴安裝與程式碼複製
```dockerfile
FROM node:20 AS builder
WORKDIR /app

# 先複製 package.json (快取層)
COPY package*.json ./
RUN npm ci --only=production  # 使用 ci 更快且穩定

# 再複製原始碼
COPY . .
RUN npm run build
```

2. **Nginx 設定優化**
```nginx
server {
    listen 80;

    # 壓縮
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # 快取靜態資源
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA 路由
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

3. **安全標頭**
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

---

## 環境配置

### .env.example

```bash
# OpenRouter 配置
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_URL=https://openrouter.ai/api/v1/chat/completions
DEFAULT_MODEL=qwen/qwen3-max

# PostgreSQL 配置
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=chatdb
POSTGRES_HOST=postgres  # Docker 服務名稱
POSTGRES_PORT=5432

# JWT 配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# 機器人配置
BOT_INFO_PATH=data/bots.json
```

**配置分析:**

⚠️ **安全問題:**

1. **預設密碼太弱**: `postgres` 應強制更改
2. **JWT 密鑰未強調**: 應提示生成強密鑰
3. **無生產環境區分**: 應加入 `ENVIRONMENT` 變數

**建議改進:**

```bash
# 生成強密碼的指令
# PostgreSQL 密碼: openssl rand -base64 32
POSTGRES_PASSWORD=請執行上述指令生成

# JWT 密鑰: openssl rand -hex 64
JWT_SECRET_KEY=請執行上述指令生成

# 環境標記
ENVIRONMENT=development  # development | production

# 日誌層級
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR

# CORS 來源 (生產環境)
ALLOWED_ORIGINS=https://yourdomain.com
```

---

## 部署指南

### 本地開發環境

```bash
# 1. 複製環境變數範本
cp .env.example .env

# 2. 編輯 .env 檔案,填入 API 金鑰
nano .env

# 3. 啟動所有服務
docker-compose -f docker-compose.annotation.yml up -d

# 4. 查看日誌
docker-compose -f docker-compose.annotation.yml logs -f backend

# 5. 驗證服務
curl http://localhost:8000/bots  # 後端 API
curl http://localhost:5173       # 前端頁面

# 6. 停止服務
docker-compose -f docker-compose.annotation.yml down

# 7. 停止並刪除資料 (⚠️ 危險)
docker-compose -f docker-compose.annotation.yml down -v
```

### 生產環境部署

**⚠️ 生產環境檢查清單:**

- [ ] 修改所有預設密碼
- [ ] 設定強 JWT 密鑰
- [ ] 配置 HTTPS (Nginx 反向代理 + Let's Encrypt)
- [ ] 限制 PostgreSQL 埠號 (移除 `ports` 映射)
- [ ] 加入資源限制 (`deploy.resources`)
- [ ] 設定健康檢查
- [ ] 配置日誌收集 (ELK stack / Loki)
- [ ] 設定監控告警 (Prometheus + Grafana)
- [ ] 啟用速率限制
- [ ] 關閉註冊端點或加入邀請機制
- [ ] 配置資料庫備份

---

## 安全性審查

### 高風險問題

1. **❌ HTTP 明文傳輸**
   - JWT 令牌暴露
   - 密碼傳輸無加密
   - **修復**: 配置 HTTPS

2. **❌ CORS 配置過於寬鬆**
   ```python
   # 問題程式碼
   allow_credentials=True
   allow_methods=["*"]
   allow_headers=["*"]
   ```
   - **修復**: 明確指定允許的方法和標頭

3. **❌ 無速率限制**
   - 暴力破解攻擊
   - API 濫用
   - **修復**: 使用 `slowapi`
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address

   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter

   @router.post("/login")
   @limiter.limit("5/minute")
   async def login(...):
       ...
   ```

4. **❌ 註冊端點暴露**
   - 任何人都能建立帳號
   - **修復**: 加入邀請碼系統或關閉端點

### 中風險問題

5. **⚠️ 無輸入長度驗證**
   - 超長訊息可能導致效能問題
   - **修復**: 加入 Pydantic 驗證
   ```python
   class UserMessage(BaseModel):
       message: str = Field(..., max_length=2000)
       bot_id: str
   ```

6. **⚠️ 無 SQL 注入防護測試**
   - 雖使用 ORM,但應測試
   - **修復**: 加入安全性測試

7. **⚠️ Docker 容器以 root 執行**
   - 容器逃逸風險
   - **修復**: 使用非 root 使用者

---

## 效能優化建議

### 後端優化

1. **資料庫連線池配置**
```python
from sqlalchemy import create_engine

engine = create_engine(
    settings.CHAT_DB_URL,
    pool_size=20,           # 連線池大小
    max_overflow=10,        # 最大溢出連線
    pool_pre_ping=True,     # 檢查連線有效性
    pool_recycle=3600,      # 1小時回收連線
)
```

2. **訊息批次提交**
```python
# 目前: 每句話一次 commit
msg_id = _save_message(sentence, user_id, bot_id, db)

# 優化: 累積 5 句再提交
message_buffer = []
if len(message_buffer) >= 5:
    db.add_all(message_buffer)
    db.commit()
```

3. **查詢優化**
```python
# 加入索引
from sqlalchemy import Index

Index('idx_user_bot_time', Message.user_id, Message.bot_id, Message.created_at)

# 使用 select_in_loading 避免 N+1 查詢
from sqlalchemy.orm import selectinload

messages = db.query(Message).options(
    selectinload(Message.user)
).filter_by(user_id=user_id).all()
```

### 前端優化

1. **虛擬化長列表**
```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

const virtualizer = useVirtualizer({
  count: history.length,
  getScrollElement: () => messagesContainerRef.current,
  estimateSize: () => 80,  // 預估訊息高度
});
```

2. **React.memo 避免重複渲染**
```typescript
export const ChatMessage = React.memo<ChatMessageProps>(
  ({ message, onRate, onComment }) => {
    return (/* ... */);
  },
  (prev, next) => prev.message.id === next.message.id && prev.message.rating === next.message.rating
);
```

3. **程式碼分割**
```typescript
import { lazy, Suspense } from 'react';

const ChatPage = lazy(() => import('./pages/ChatPage'));

<Suspense fallback={<LoadingSpinner />}>
  <ChatPage />
</Suspense>
```

---

## 測試建議

### 後端測試

```python
# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_register_success():
    response = client.post("/register", json={
        "username": "testuser",
        "password": "SecurePass123"
    })
    assert response.status_code == 200
    assert "user_id" in response.json()

def test_login_wrong_password():
    response = client.post("/login", json={
        "username": "testuser",
        "password": "WrongPassword"
    })
    assert response.status_code == 401

def test_chat_without_auth():
    response = client.post("/chat/stream", json={
        "message": "Hello",
        "bot_id": "bot_1"
    })
    assert response.status_code == 403  # Unauthorized
```

### 前端測試

```typescript
// tests/ChatWindow.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import ChatWindow from '../components/ChatWindow';

test('發送訊息後清空輸入框', () => {
  const mockSend = vi.fn();
  render(<ChatWindow onSendMessage={mockSend} history={[]} />);

  const input = screen.getByPlaceholderText('輸入訊息...');
  const sendButton = screen.getByRole('button', { name: /發送/i });

  fireEvent.change(input, { target: { value: 'Hello' } });
  fireEvent.click(sendButton);

  expect(mockSend).toHaveBeenCalledWith('Hello');
  expect(input).toHaveValue('');
});

test('評分按鈕切換狀態', () => {
  const mockRate = vi.fn();
  const message = { id: '1', text: 'Hello', sender: 'bot' };

  render(<ChatMessage message={message} onRate={mockRate} />);

  const thumbsUp = screen.getByLabelText('thumbs up');
  fireEvent.click(thumbsUp);

  expect(mockRate).toHaveBeenCalledWith('1', 'up');
});
```

---

## 已知問題與限制

### 高優先級

1. **❌ 串流延遲硬編碼 (3 秒)**
   - 位置: `ChatPage.tsx:98`
   - 影響: 無法調整使用者體驗
   - 修復: 移至環境變數

2. **❌ 無訊息刪除功能**
   - 影響: 錯誤訊息永久存在
   - 修復: 加入 DELETE 端點

3. **❌ 無對話清除功能**
   - 影響: 測試需要刪除資料庫
   - 修復: 加入「清除聊天」按鈕

4. **❌ PostgreSQL 埠號暴露**
   - 安全風險
   - 修復: 移除 Docker Compose 埠號映射

### 中優先級

5. **⚠️ 歡迎訊息重複建立**
   - 位置: `routes/auth.py:27-38`
   - 影響: 每個新使用者 3+ 訊息
   - 修復: 延遲載入首次互動時才建立

6. **⚠️ 無分頁**
   - `/history` 端點返回所有訊息
   - 影響: 長期使用者查詢緩慢
   - 修復: 加入 limit/offset 參數

7. **⚠️ CORS 配置不一致**
   - 允許 `localhost:3000` 但前端用 `5173`
   - 修復: 更新 CORS 設定

8. **⚠️ 無錯誤邊界**
   - 前端崩潰導致白屏
   - 修復: 加入 React Error Boundary

---

## 總結

### 優勢 ✅

1. **架構清晰**: 前後端分離,職責明確
2. **串流實作完善**: 句子邊界檢測,取消機制
3. **型別安全**: TypeScript + Pydantic
4. **容器化**: Docker Compose 簡化部署
5. **響應式設計**: 手機/桌面皆可使用

### 需改進 ⚠️

1. **安全性強化**: HTTPS, 速率限制, 輸入驗證
2. **效能優化**: 資料庫索引, 批次提交, 前端虛擬化
3. **測試覆蓋**: 單元測試, 整合測試, E2E 測試
4. **監控告警**: 日誌收集, 效能指標
5. **生產就緒**: 健康檢查, 資源限制, 非 root 使用者

### 部署建議

| 環境 | 狀態 | 建議 |
|------|------|------|
| **開發** | ✅ 可用 | 直接使用 docker-compose |
| **測試** | ⚠️ 需改進 | 加入健康檢查, 資源限制 |
| **生產** | ❌ 不建議 | 必須完成安全性強化 |

---

## 附錄

### 檔案清單

**後端 (21 個檔案):**
- Python 原始碼: 12 個
- 配置檔案: 4 個
- 文件: 0 個
- 測試: 0 個

**前端 (47 個檔案):**
- TypeScript/React: 15 個
- 配置檔案: 8 個
- 靜態資源: 2 個
- 測試: 0 個

**總程式碼行數 (估計):**
- 後端: ~1,500 行
- 前端: ~2,000 行
- 總計: ~3,500 行

### 外部依賴

**NPM 套件 (22 個):**
- 生產依賴: 5 個
- 開發依賴: 17 個

**Python 套件 (10 個):**
- 生產依賴: 10 個
- 開發依賴: 0 個

---

**審查報告結束**
