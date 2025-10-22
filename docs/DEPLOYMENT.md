# Deployment Guide

Complete deployment guide for the Medical Chatbot system with separate frontend and backend services.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Production                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  React Frontend  │ ──────► │  FastAPI Backend │          │
│  │  (Port 3000)     │  HTTP   │  (Port 8000)     │          │
│  │  Vite/Nginx      │         │  Uvicorn/Docker  │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 📦 What to Deploy

### Backend Service
- Location: `/app` directory
- Technology: FastAPI + LangGraph
- Port: 8000
- Dependencies: Python 3.11+, see `requirements.txt`

### Frontend Service
- Location: `/frontend` directory
- Technology: React + TypeScript + Vite
- Port: 3000 (dev) / 80 (production)
- Dependencies: Node.js 18+, see `frontend/package.json`

## 🚀 Quick Start (Development)

### 1. Start Backend

```bash
# Terminal 1 - Backend
cd langgraph/

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000

### 2. Start Frontend

```bash
# Terminal 2 - Frontend
cd langgraph/frontend/

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults to localhost:8000)

# Run frontend
npm run dev
```

Frontend will be available at: http://localhost:3000

### 3. Test the System

Open http://localhost:3000 in your browser and start chatting!

## 🐳 Docker Deployment

### Backend Docker

Create `Dockerfile` in root directory:

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY data/ ./data/

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
# Build backend image
docker build -t medical-chatbot-backend .

# Run backend container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key-here \
  -e MODEL_NAME=qwen/qwen3-max \
  medical-chatbot-backend
```

### Frontend Docker

Create `frontend/Dockerfile`:

```dockerfile
# Frontend Dockerfile - Multi-stage build
FROM node:18-alpine as build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

Create `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Enable gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Main app
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Build and run:

```bash
# Build frontend image
cd frontend
docker build -t medical-chatbot-frontend .

# Run frontend container
docker run -p 3000:80 medical-chatbot-frontend
```

### Docker Compose

Create `docker-compose.yml` in root:

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

Run with Docker Compose:

```bash
# Create .env file with your API keys
cat > .env << EOF
OPENAI_API_KEY=your-key-here
MODEL_NAME=qwen/qwen3-max
EOF

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## ☁️ Cloud Deployment

### AWS Deployment

#### Backend on AWS ECS/Fargate

1. **Build and push Docker image to ECR**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Create repository
aws ecr create-repository --repository-name medical-chatbot-backend

# Build and tag image
docker build -t medical-chatbot-backend .
docker tag medical-chatbot-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/medical-chatbot-backend:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/medical-chatbot-backend:latest
```

2. **Create ECS Task Definition**

```json
{
  "family": "medical-chatbot-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/medical-chatbot-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:openai-api-key"
        }
      ]
    }
  ]
}
```

3. **Deploy ECS Service with ALB**

#### Frontend on AWS S3 + CloudFront

```bash
# Build frontend
cd frontend
npm run build

# Upload to S3
aws s3 sync dist/ s3://medical-chatbot-frontend --delete

# Create CloudFront distribution (via AWS Console or CLI)
# Configure origin: S3 bucket
# Configure behaviors: SPA routing (404 -> /index.html)
```

#### Environment Variables via AWS Secrets Manager

```bash
# Store API key
aws secretsmanager create-secret \
  --name openai-api-key \
  --secret-string "your-api-key-here"

# Reference in ECS task definition (see above)
```

### Vercel Deployment (Frontend)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy frontend
cd frontend
vercel deploy --prod
```

Configure environment variables in Vercel dashboard:
- `VITE_API_URL` = Your backend URL

### Railway/Render Deployment (Backend)

**Railway:**

```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
railway login
railway init
railway up
```

**Render:**

1. Connect GitHub repository
2. Create new Web Service
3. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

## 🔒 Production Configuration

### Backend (.env)

```bash
# LLM Configuration
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-xxx
MODEL_NAME=qwen/qwen3-max

# Application
LOG_LEVEL=INFO
SESSION_TTL_SECONDS=3600
ENVIRONMENT=production

# Embedding
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Optional: Production database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379
```

### Frontend (.env.production)

```bash
VITE_API_URL=https://api.yourdomain.com
```

### CORS Configuration

Update `app/main.py` for production:

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

## 📊 Monitoring & Logging

### Application Logs

Backend logs to stdout in JSON format for easy parsing:

```python
import logging
import json

logging.basicConfig(
    format='%(message)s',
    level=logging.INFO
)
```

### Health Checks

Backend provides `/health` endpoint:

```bash
curl http://localhost:8000/health
```

Configure health checks in your orchestrator:
- **ECS**: healthCheck in task definition
- **Kubernetes**: livenessProbe and readinessProbe
- **Docker Compose**: healthcheck directive

### Metrics to Monitor

- Response latency (p50, p95, p99)
- Error rate
- Session creation rate
- Agent assignment distribution
- LLM token usage
- Memory usage
- CPU usage

## 🔐 Security Checklist

- [ ] API keys stored in secrets manager (not in code)
- [ ] HTTPS enabled (TLS certificates)
- [ ] CORS configured for production domains only
- [ ] Rate limiting enabled
- [ ] Input validation (handled by Pydantic)
- [ ] Security headers configured
- [ ] Container scanning enabled
- [ ] Dependency scanning enabled
- [ ] Log sensitive data filtering

## 🚨 Troubleshooting

### Frontend can't connect to backend

**CORS Error:**
- Update backend CORS allowed origins
- Check frontend `VITE_API_URL` is correct

**Network Error:**
- Verify backend is running
- Check firewall/security group rules
- Verify DNS/routing configuration

### Backend startup fails

**Import errors:**
```bash
pip install -r requirements.txt
```

**Missing environment variables:**
```bash
# Check .env file
cat .env

# Verify variables are loaded
python -c "from app.config import settings; print(settings.openai_api_key)"
```

### High latency

- Enable caching for LLM responses
- Use Redis for session storage
- Enable connection pooling
- Scale horizontally (multiple backend instances)

## 📈 Scaling

### Horizontal Scaling

**Backend:**
- Deploy multiple instances behind load balancer
- Use external session store (Redis/PostgreSQL)
- Consider serverless (AWS Lambda + API Gateway)

**Frontend:**
- CDN distribution (CloudFront, Cloudflare)
- Geographic distribution
- Edge caching

### Vertical Scaling

- Increase CPU/memory for backend containers
- Use larger instance types
- Optimize LLM batch processing

## 🔄 CI/CD Pipeline

Example GitHub Actions workflow:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build and push Docker image
        run: |
          docker build -t backend .
          # Push to registry

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build frontend
        run: |
          cd frontend
          npm ci
          npm run build
      - name: Deploy to S3
        run: aws s3 sync frontend/dist/ s3://bucket-name
```

---

## 📚 Next Steps

1. Choose deployment platform
2. Set up CI/CD pipeline
3. Configure monitoring
4. Set up alerts
5. Document runbooks

For questions, see main [README.md](README.md) or [ARCHITECTURE.md](ARCHITECTURE.md).
