# Chatbot Annotation Interface

A simple multi-bot chat interface where users can talk with different chatbots and give thumbs-up, thumbs-down, or comment feedback on each response.

## Quick Start

### Prerequisites
- Node.js 18+
- npm 9+

### Installation

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
```

Open http://localhost:5173

### Usage

1. **Chat with bots**: Send messages to each of the chatbots independently
2. **Give feedback**: Provide feedback to each chatbot response
3. **Log in/out**

### Build for Production

```bash
npm run build
npm run preview
```

## Project Structure

```
annotation_frontend/
├── src/
|   ├── assets/           # static files (images, fonts, icons, global CSS)
|   │   └── styles.css
│   ├── components/
│   │   ├── BotSelector.tsx
│   │   └── ChatWindow.tsx
│   ├── config/           # export url for convenient import
│   │   └── index.ts
│   ├── pages/            # page-level components (routed)
│   │   ├── ChatPage.tsx
│   │   └── LoginPage.tsx
│   ├── services/         # API calls, external services
│   │   ├── authService.ts
│   │   ├── botService.ts
│   │   └── chatService.ts
│   ├── types/            # TypeScript interfaces
│   │   └── chat.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css         # global entry style
└── public/
    └── logo.svg 
```

## Technologies

- React 19
- TypeScript 5 + SWC
- Vite 7
- Tailwind CSS 3