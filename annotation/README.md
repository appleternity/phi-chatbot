# Chatbot Annotation Interface

Multi-chatbot comparison annotation tool for collecting preference data.

## Features

- 🎨 Instagram-style chat UI with gradient messages
- 💬 3 independent chatbot instances (GPT-4, Claude, Gemini)
- ✅ Preference selection with visual indicators
- 📥 Data export to JSON (下載資料)
- 🔄 Session management (開始新對話)
- 💾 LocalStorage persistence
- 🌐 Traditional Chinese interface
- ⚠️ Storage quota monitoring
- 🛡️ Error boundary protection
- ♿ Full accessibility support (ARIA labels, keyboard navigation)

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

1. **Chat with bots**: Send messages to each of the 3 chatbots independently
2. **Select preference**: Click "Select as Preferred" on your preferred chatbot
3. **Export data**: Click "下載資料" to download annotation JSON
4. **New session**: Click "開始新對話" to reset and start over

### Build for Production

```bash
npm run build
npm run preview
```

## Project Structure

```
annotation/
├── src/
│   ├── components/       # React components
│   │   ├── SmartphoneChatbot/
│   │   ├── ComparisonLayout/
│   │   ├── ExportButton/
│   │   ├── NewSessionButton/
│   │   └── ErrorBoundary.tsx
│   ├── services/         # Business logic
│   │   └── storageService.ts
│   ├── hooks/            # Custom React hooks
│   │   ├── useExport.ts
│   │   └── useSession.ts
│   ├── types/            # TypeScript interfaces
│   │   ├── chatbot.ts
│   │   └── session.ts
│   └── utils/            # Helper functions
│       └── storageMonitor.ts
└── public/
```

## Technologies

- React 18
- TypeScript 5
- Vite 5
- Tailwind CSS 3
- LocalStorage API

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Key Features

### Storage Monitoring
- Automatic quota checking (75% threshold warning)
- User-friendly alerts when storage is full
- Export recommendations before quota exceeded

### Error Handling
- React Error Boundary for graceful error recovery
- Clear error messages with reload/reset options
- Component stack traces for debugging

### Accessibility
- ARIA labels on all interactive elements
- Keyboard navigation support
- Screen reader friendly
- Focus indicators on all controls

### Performance
- React.memo optimizations for message rendering
- Debounced localStorage writes (500ms)
- Efficient state management

## Development

### Code Quality

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Format code
npm run format
```

### Testing

```bash
# Run all tests
npm test

# Run smoke tests
# See SMOKE_TEST_CHECKLIST.md
```

## Data Export Format

Exported JSON structure:

```json
{
  "sessionId": "uuid-v4",
  "chatbots": [
    {
      "chatId": "bot1",
      "displayName": "GPT-4",
      "messages": [
        {
          "id": "msg-id",
          "role": "user|assistant",
          "content": "message text",
          "timestamp": "ISO-8601"
        }
      ]
    }
  ],
  "selection": {
    "selectedChatbotId": "bot1|bot2|bot3|null",
    "timestamp": "ISO-8601"
  },
  "metadata": {
    "createdAt": "ISO-8601",
    "updatedAt": "ISO-8601",
    "version": "1.0.0"
  }
}
```

## Troubleshooting

### Storage Quota Exceeded
1. Export your current data
2. Click "開始新對話" to clear old sessions
3. Import critical data if needed

### Application Errors
1. Try refreshing the page
2. Clear browser cache and localStorage
3. Check browser console for detailed errors

### Build Issues
```bash
# Clean install
rm -rf node_modules package-lock.json
npm install
npm run build
```

## License

MIT
