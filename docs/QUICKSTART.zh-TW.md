# 快速入門指南

## 5 分鐘設定

### 1. 安裝依賴套件

```bash
cd langgraph/
pip install -r requirements.txt
# 或使用 Poetry: poetry install
```

### 2. 配置環境

```bash
cp .env.example .env
```

編輯 `.env` 並新增您的 OpenRouter API 金鑰：
```
OPENAI_API_KEY=your-key-here
```

### 3. 啟動伺服器

```bash
uvicorn app.main:app --reload --port 8000
```

您應該會看到：
```
🚀 初始化醫療聊天機器人應用程式...
✅ 會話儲存已初始化
📚 載入醫療文件中...
✅ 已載入 5 份醫療文件至檢索器
✅ 醫療聊天機器人圖已編譯
🎉 應用程式啟動完成！
```

### 4. 開始測試！

**選項 A：網頁瀏覽器**
- 開啟 http://localhost:8000/docs
- 在 `/chat` 端點上點擊「Try it out」
- 使用此請求：
```json
{
  "session_id": "test-1",
  "message": "Sertraline 是什麼？"
}
```

**選項 B：命令列**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-1","message":"Sertraline 是什麼？"}'
```

**選項 C：Python 腳本**
```bash
python example_usage.py
```

## 測試內容

### 1. 醫療資訊（路由至 RAG 代理）
```json
{
  "session_id": "test-medical-1",
  "message": "Sertraline 是用來治療什麼的？"
}
```

### 2. 情緒支援（路由至情緒代理）
```json
{
  "session_id": "test-emotional-1",
  "message": "我今天感到焦慮"
}
```

### 3. 多輪對話
使用相同的 `session_id` 傳送多個訊息 - 代理指派會持續存在！

## 執行測試

```bash
# 所有測試
pytest

# 包含覆蓋率
pytest --cov=app

# 特定測試
pytest tests/unit/test_session_store.py -v
```

## 疑難排解

### 「找不到模組」錯誤
```bash
pip install -r requirements.txt
```

### 測試時「連線被拒」
確保伺服器正在執行：
```bash
uvicorn app.main:app --reload --port 8000
```

### LLM 錯誤
檢查您的 `.env` 檔案是否有正確的 `OPENAI_API_KEY`

## 下一步

- 📖 閱讀 [ARCHITECTURE.md](ARCHITECTURE.md) 了解系統設計
- 📖 閱讀 [ARCHITECTURE.zh-TW.md](ARCHITECTURE.zh-TW.md) 了解系統設計（繁體中文）
- 🛠️ 查看 [IMPLEMENTATION.md](IMPLEMENTATION.md) 進行自訂
- 🛠️ 查看 [IMPLEMENTATION.zh-TW.md](IMPLEMENTATION.zh-TW.md) 進行自訂（繁體中文）
- 📋 查看 [README.md](README.md) 取得完整文件
- 📋 查看 [README.zh-TW.md](README.zh-TW.md) 取得完整文件（繁體中文）

## 快速架構概覽

```
使用者訊息
    ↓
FastAPI /chat 端點
    ↓
會話檢查（首次訊息或回訪？）
    ↓
    ├─ 首次訊息 → 監督者分類意圖
    │                   ↓
    │   ┌──────────────┴──────────────┐
    │   ↓                              ↓
    │   情緒支援                    RAG 代理
    │   （同理心、傾聽）            （搜尋醫療文件）
    │
    └─ 後續訊息 → 直接路由至已指派的代理

所有回應都使用 session_id 儲存
```

## 檔案結構
```
langgraph/
├── app/               # 應用程式程式碼
│   ├── main.py       # FastAPI 應用程式（從這裡開始）
│   ├── agents/       # 監督者、情緒、RAG 代理
│   ├── graph/        # LangGraph 狀態與建構器
│   └── core/         # 會話儲存、檢索器
├── tests/            # 單元與整合測試
├── data/             # 心理健康藥物（5 份範例文件）
├── .env              # 您的配置（從 .env.example 建立）
└── README.md         # 完整文件
```

## 範例輸出

**情緒支援：**
```
使用者：「我感到焦慮」
代理：「我聽到您的感受了，感到焦慮是完全可以理解的。
      您願意談談是什麼讓您有這樣的感覺嗎？
      我在這裡傾聽。」
```

**醫療資訊：**
```
使用者：「Sertraline 是什麼？」
代理：「Sertraline（Zoloft）是一種 SSRI，用於治療憂鬱症、
      焦慮症、OCD、PTSD 和恐慌症。典型劑量：每日 50-200mg。
      ⚕️ 免責聲明：這僅為教育資訊...」
```

---

**一切就緒！** 🚀 啟動伺服器並試試這些範例。
