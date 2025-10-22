# Medical Chatbot Frontend

Modern React + TypeScript frontend for the Medical Chatbot multi-agent system.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

The frontend will be available at **http://localhost:3000**

## 📦 Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **Axios** - HTTP client
- **Lucide React** - Beautiful icons

## 🛠️ Available Scripts

```bash
# Development server (port 3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── ChatContainer.tsx   # Main chat container
│   │   ├── ChatMessage.tsx     # Message bubble
│   │   ├── ChatInput.tsx       # Input field
│   │   ├── Header.tsx          # App header
│   │   └── WelcomeMessage.tsx  # Welcome screen
│   ├── services/            # API services
│   │   └── api.ts              # Backend API client
│   ├── utils/               # Utilities
│   │   └── session.ts          # Session management
│   ├── types/               # TypeScript types
│   │   └── index.ts
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── public/                  # Static assets
├── index.html               # HTML template
├── vite.config.ts           # Vite configuration
├── tailwind.config.js       # Tailwind configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies
```

## 🎨 Features

- ✅ **Beautiful UI** - Modern gradient design with Tailwind CSS
- ✅ **Real-time Chat** - Instant messaging with typing indicators
- ✅ **Session Management** - Persistent conversations with localStorage
- ✅ **Agent Display** - Shows which agent (Emotional Support / Medical Info) is responding
- ✅ **Responsive Design** - Works on desktop, tablet, and mobile
- ✅ **Type Safety** - Full TypeScript coverage
- ✅ **Error Handling** - Graceful error messages and retry logic

## 🔧 Configuration

### Backend API URL

Edit `.env` to configure the backend API URL:

```env
VITE_API_URL=http://localhost:8000
```

For production, set this to your deployed backend URL.

### Proxy Configuration

The Vite dev server is configured to proxy `/api` requests to the backend:

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}
```

## 🚢 Production Build

```bash
# Build optimized production bundle
npm run build

# Preview production build locally
npm run preview
```

The build output will be in the `dist/` directory.

### Deploy

You can deploy the `dist/` folder to any static hosting service:

- **Vercel**: `vercel deploy`
- **Netlify**: Drag and drop `dist/` folder
- **AWS S3 + CloudFront**: Upload to S3 bucket
- **Docker**: See `Dockerfile` example below

### Docker Example

Create `Dockerfile`:

```dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Build and run:

```bash
docker build -t medical-chatbot-frontend .
docker run -p 3000:80 medical-chatbot-frontend
```

## 🧪 Testing

Run the backend first:

```bash
# In backend directory
uvicorn app.main:app --reload --port 8000
```

Then test the frontend:

1. **Open browser**: http://localhost:3000
2. **Try emotional support**: "I'm feeling anxious"
3. **Try medical info**: "What is Sertraline?"
4. **Multi-turn conversation**: Keep chatting in the same session
5. **New session**: Click "New Session" button

## 🔍 Troubleshooting

### "Cannot connect to backend"

- Ensure backend is running on `http://localhost:8000`
- Check CORS is enabled in FastAPI
- Verify `.env` has correct `VITE_API_URL`

### "Module not found" errors

```bash
rm -rf node_modules package-lock.json
npm install
```

### Build errors

```bash
npm run lint
npm run build
```

## 📚 Documentation

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [TypeScript](https://www.typescriptlang.org/)

---

Built with ❤️ using React + TypeScript + Vite
