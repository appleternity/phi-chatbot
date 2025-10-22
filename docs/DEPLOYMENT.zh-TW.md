# 部署指南

醫療聊天機器人系統的完整部署指南，前後端分離架構。

## 🏗️ 架構概覽

```
┌─────────────────────────────────────────────────────────────┐
│                         生產環境                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  React 前端      │ ──────► │  FastAPI 後端    │          │
│  │  (Port 3000)     │  HTTP   │  (Port 8000)     │          │
│  │  Vite/Nginx      │         │  Uvicorn/Docker  │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 📦 部署內容

### 後端服務
- 位置：`/app` 目錄
- 技術：FastAPI + LangGraph
- 埠號：8000
- 依賴：Python 3.11+，參見 `requirements.txt`

### 前端服務
- 位置：`/frontend` 目錄
- 技術：React + TypeScript + Vite
- 埠號：3000（開發）/ 80（生產）
- 依賴：Node.js 18+，參見 `frontend/package.json`

## 🚀 快速開始（開發環境）

### 1. 啟動後端

```bash
# 終端機 1 - 後端
cd langgraph/

# 安裝依賴
pip install -r requirements.txt

# 配置環境
cp .env.example .env
# 編輯 .env 填入您的 API 金鑰

# 執行後端
uvicorn app.main:app --reload --port 8000
```

後端將可在以下位址存取：http://localhost:8000

### 2. 啟動前端

```bash
# 終端機 2 - 前端
cd langgraph/frontend/

# 安裝依賴
npm install

# 配置環境
cp .env.example .env
# 如需要可編輯 .env（預設為 localhost:8000）

# 執行前端
npm run dev
```

前端將可在以下位址存取：http://localhost:3000

### 3. 測試系統

在瀏覽器中開啟 http://localhost:3000 並開始對話！

## 🐳 Docker 部署

### 後端 Docker

在根目錄建立 `Dockerfile`：

```dockerfile
# 後端 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式
COPY app/ ./app/
COPY data/ ./data/

# 暴露埠號
EXPOSE 8000

# 執行應用程式
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

建置並執行：

```bash
# 建置後端映像
docker build -t medical-chatbot-backend .

# 執行後端容器
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key-here \
  -e MODEL_NAME=qwen/qwen3-max \
  medical-chatbot-backend
```

### 前端 Docker

建立 `frontend/Dockerfile`：

```dockerfile
# 前端 Dockerfile - 多階段建置
FROM node:18-alpine as build

WORKDIR /app

# 安裝依賴
COPY package*.json ./
RUN npm ci

# 建置應用程式
COPY . .
RUN npm run build

# 生產階段
FROM nginx:alpine

# 複製建置檔案
COPY --from=build /app/dist /usr/share/nginx/html

# 複製 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

建置並執行：

```bash
# 建置前端映像
cd frontend
docker build -t medical-chatbot-frontend .

# 執行前端容器
docker run -p 3000:80 medical-chatbot-frontend
```

### Docker Compose

在根目錄建立 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_BASE=${OPENAI_API_BASE:-https://openrouter.ai/api/v1}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MODEL_NAME=${MODEL_NAME:-qwen/qwen3-max}
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000
    restart: unless-stopped

networks:
  default:
    name: medical-chatbot-network
```

使用 Docker Compose 執行：

```bash
# 建立包含 API 金鑰的 .env 檔案
cat > .env << EOF
OPENAI_API_KEY=your-key-here
MODEL_NAME=qwen/qwen3-max
EOF

# 啟動所有服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止所有服務
docker-compose down
```

存取：
- 前端：http://localhost:3000
- 後端 API：http://localhost:8000
- API 文件：http://localhost:8000/docs

## ☁️ 雲端部署

### AWS 部署

#### 後端部署至 AWS ECS/Fargate

1. **建置並推送 Docker 映像至 ECR**

```bash
# 登入 ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 建立儲存庫
aws ecr create-repository --repository-name medical-chatbot-backend

# 建置並標記映像
docker build -t medical-chatbot-backend .
docker tag medical-chatbot-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/medical-chatbot-backend:latest

# 推送映像
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/medical-chatbot-backend:latest
```

#### 前端部署至 AWS S3 + CloudFront

```bash
# 建置前端
cd frontend
npm run build

# 上傳至 S3
aws s3 sync dist/ s3://medical-chatbot-frontend --delete

# 建立 CloudFront 分發（透過 AWS Console 或 CLI）
# 配置來源：S3 儲存貯體
# 配置行為：SPA 路由（404 -> /index.html）
```

### Vercel 部署（前端）

```bash
# 安裝 Vercel CLI
npm i -g vercel

# 部署前端
cd frontend
vercel deploy --prod
```

在 Vercel 儀表板中配置環境變數：
- `VITE_API_URL` = 您的後端 URL

## 🔒 生產環境配置

### 後端（.env）

```bash
# LLM 配置
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-xxx
MODEL_NAME=qwen/qwen3-max

# 應用程式
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
ENVIRONMENT=production

# 嵌入模型
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# 選用：生產環境資料庫
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379
```

### 前端（.env.production）

```bash
VITE_API_URL=https://api.yourdomain.com
```

### CORS 配置

更新 `app/main.py` 用於生產環境：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## 📊 監控與日誌

### 應用程式日誌

後端以 JSON 格式輸出至 stdout，方便解析。

### 健康檢查

後端提供 `/health` 端點：

```bash
curl http://localhost:8000/health
```

### 監控指標

- 回應延遲（p50、p95、p99）
- 錯誤率
- 會話建立率
- 代理指派分布
- LLM token 使用量
- 記憶體使用量
- CPU 使用量

## 🔐 安全檢查清單

- [ ] API 金鑰儲存在 secrets manager（非程式碼中）
- [ ] 啟用 HTTPS（TLS 憑證）
- [ ] CORS 僅配置為生產網域
- [ ] 啟用速率限制
- [ ] 輸入驗證（由 Pydantic 處理）
- [ ] 配置安全標頭
- [ ] 啟用容器掃描
- [ ] 啟用依賴掃描
- [ ] 過濾敏感日誌資料

## 🚨 疑難排解

### 前端無法連接後端

**CORS 錯誤：**
- 更新後端 CORS 允許的來源
- 檢查前端 `VITE_API_URL` 是否正確

**網路錯誤：**
- 驗證後端正在執行
- 檢查防火牆/安全群組規則
- 驗證 DNS/路由配置

### 後端啟動失敗

**匯入錯誤：**
```bash
pip install -r requirements.txt
```

**缺少環境變數：**
```bash
# 檢查 .env 檔案
cat .env

# 驗證變數已載入
python -c "from app.config import settings; print(settings.openai_api_key)"
```

## 📈 擴展

### 水平擴展

**後端：**
- 在負載平衡器後部署多個實例
- 使用外部會話儲存（Redis/PostgreSQL）
- 考慮無伺服器架構（AWS Lambda + API Gateway）

**前端：**
- CDN 分發（CloudFront、Cloudflare）
- 地理分布
- 邊緣快取

---

## 📚 下一步

1. 選擇部署平台
2. 設定 CI/CD 管線
3. 配置監控
4. 設定告警
5. 編寫運維手冊

如有疑問，請參閱 [README.md](README.md) 或 [ARCHITECTURE.md](ARCHITECTURE.md)。
