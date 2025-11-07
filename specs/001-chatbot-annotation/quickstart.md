# Quickstart: Multi-Chatbot Annotation Interface

**Feature**: 001-chatbot-annotation
**Date**: 2025-11-06
**Estimated Setup Time**: 30 minutes

## Overview

This guide will help you set up and run the chatbot annotation interface locally in under 30 minutes. This is a React-based frontend-only application that allows users to compare multiple chatbots side-by-side and export preference data as JSON files.

## Prerequisites

### Required Software

- **Node.js**: 18.0.0 or higher ([Download](https://nodejs.org/))
- **npm**: 9.0.0 or higher (comes with Node.js)
- **Git**: For version control

**Check your versions**:
```bash
node --version  # Should be v18.0.0+
npm --version   # Should be 9.0.0+
```

### Recommended Tools

- **VS Code**: With ESLint and Tailwind CSS IntelliSense extensions
- **Chrome/Firefox DevTools**: For debugging and localStorage inspection

---

## Quick Setup (5 minutes)

### 1. Clone the Repository

```bash
# Clone the repo
git clone <repository-url>
cd langgraph-annotation

# Switch to the feature branch
git checkout 001-chatbot-annotation
```

### 2. Install Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install all dependencies
npm install
```

**Expected dependencies**:
- react@^18.2.0
- react-dom@^18.2.0
- react-intersection-observer@^9.5.3
- lodash@^4.17.21
- tailwindcss@^3.4.0
- vite@^5.0.0
- typescript@^5.0.0

### 3. Start Development Server

```bash
# Start Vite dev server
npm run dev
```

**Expected output**:
```
  VITE v5.0.0  ready in 300 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 4. Open in Browser

Navigate to **http://localhost:5173/**

You should see 3 smartphone-style chatbot instances side-by-side with Instagram-style UI.

---

## Project Structure

```
frontend/
├── src/
│   ├── components/           # React components
│   │   ├── SmartphoneChatbot/  # Core chatbot UI (P1)
│   │   ├── ComparisonLayout/   # Multi-instance container (P2)
│   │   └── ExportButton/       # Download data button (P2)
│   ├── services/             # Business logic
│   │   ├── chatbotService.ts   # API/mock integration
│   │   ├── storageService.ts   # LocalStorage operations
│   │   └── exportService.ts    # JSON export logic
│   ├── types/                # TypeScript definitions
│   │   ├── chatbot.ts          # Message, ChatbotInstance
│   │   ├── session.ts          # ComparisonSession
│   │   └── export.ts           # ExportedData
│   ├── hooks/                # Custom React hooks
│   │   ├── useChatbot.ts       # Chatbot state management
│   │   ├── useLocalStorage.ts  # LocalStorage wrapper
│   │   └── useExport.ts        # Export functionality
│   ├── utils/                # Helper functions
│   │   ├── validation.ts       # Data validation
│   │   └── timestamp.ts        # Date/time utilities
│   ├── App.tsx               # Main application
│   └── index.tsx             # React root
├── public/
│   └── index.html            # HTML template
├── specs/                    # Feature documentation
│   └── 001-chatbot-annotation/
│       ├── spec.md           # Feature specification
│       ├── plan.md           # Implementation plan
│       ├── research.md       # Technical research
│       ├── data-model.md     # Data structures
│       ├── contracts/        # JSON schemas
│       └── quickstart.md     # This file
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## Development Workflow

### Phase 1: Core SmartphoneChatbot Component (P1)

**Goal**: Build a single reusable chatbot UI component

**Steps**:

1. **Create Component Structure** (~30 min)
   ```bash
   mkdir -p src/components/SmartphoneChatbot
   touch src/components/SmartphoneChatbot/index.tsx
   touch src/components/SmartphoneChatbot/ChatHeader.tsx
   touch src/components/SmartphoneChatbot/MessageBubble.tsx
   touch src/components/SmartphoneChatbot/MessageList.tsx
   touch src/components/SmartphoneChatbot/MessageInput.tsx
   touch src/components/SmartphoneChatbot/TypingIndicator.tsx
   ```

2. **Implement Instagram-Style UI** (~2 hours)
   - Chat header with avatar (sticky positioned)
   - Message bubbles with gradients (`from-[#667eea] to-[#764ba2]`)
   - Rounded corners (18px border-radius)
   - Message input at bottom (fixed position)
   - Typing indicator animation

3. **Add State Management** (~1 hour)
   - `useState` for messages array
   - Auto-scroll with `react-intersection-observer`
   - Debounced localStorage writes

4. **Test Single Instance** (~30 min)
   - Send messages and verify responses
   - Check localStorage persistence
   - Test page refresh (data restoration)

**Verification**:
```bash
# Component should be testable independently
npm run dev
# Navigate to http://localhost:5173/
# You should see ONE chatbot instance working
```

---

### Phase 2: Multi-Instance Layout (P2)

**Goal**: Display 3 chatbot instances side-by-side

**Steps**:

1. **Create ComparisonLayout Component** (~30 min)
   ```bash
   mkdir -p src/components/ComparisonLayout
   touch src/components/ComparisonLayout/index.tsx
   ```

2. **Render Multiple Instances** (~30 min)
   ```tsx
   // ComparisonLayout/index.tsx
   <div className="flex gap-4 p-4">
     <SmartphoneChatbot chatId="bot1" displayName="GPT-4" />
     <SmartphoneChatbot chatId="bot2" displayName="Claude" />
     <SmartphoneChatbot chatId="bot3" displayName="Gemini" />
   </div>
   ```

3. **Add Preference Selection** (~1 hour)
   - Click handler on chatbot container
   - Visual highlight (green border or checkmark)
   - Store selection in parent state

4. **Test Multi-Instance** (~30 min)
   - Send different messages to each chatbot
   - Verify independent scroll positions
   - Test selection UI

**Verification**:
```bash
# All 3 chatbots should work independently
npm run dev
# Navigate to http://localhost:5173/
# You should see 3 chatbots side-by-side
```

---

### Phase 3: Data Export (P2)

**Goal**: Allow users to download annotation data as JSON

**Steps**:

1. **Create ExportButton Component** (~30 min)
   ```bash
   mkdir -p src/components/ExportButton
   touch src/components/ExportButton/index.tsx
   ```

2. **Implement Export Service** (~1 hour)
   ```bash
   touch src/services/exportService.ts
   ```

   - Aggregate data from all chatbots
   - Generate JSON with schema validation
   - Create blob and download link
   - Filename: `chatbot-annotation-{timestamp}.json`

3. **Position "下載資料" Button** (~15 min)
   - Fixed or absolute positioning in corner
   - Traditional Chinese text
   - Click triggers export

4. **Test Export** (~30 min)
   - Click button and verify file downloads
   - Validate JSON against schema
   - Check edge cases (no selection, empty conversations)

**Verification**:
```bash
# Export should generate valid JSON
npm run dev
# Navigate to http://localhost:5173/
# Interact with chatbots, select preference
# Click "下載資料" → file downloads
# Validate: npx ajv-cli validate -s specs/001-chatbot-annotation/contracts/export-schema.json -d chatbot-annotation-*.json
```

---

## Common Commands

### Development

```bash
# Start dev server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run type-check

# Linting
npm run lint

# Fix linting errors
npm run lint:fix
```

### Testing

```bash
# Run unit tests (if implemented)
npm test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

### LocalStorage Management

**View in Browser DevTools**:
1. Open Chrome DevTools (F12)
2. Go to **Application** tab
3. Expand **Local Storage** → `http://localhost:5173`
4. See keys: `current_session_id`, `comparison_session_{uuid}`

**Clear localStorage** (for testing):
```javascript
// In browser console
localStorage.clear();
location.reload();
```

---

## Troubleshooting

### Issue: Dev server won't start

**Error**: `Error: Cannot find module 'vite'`

**Solution**:
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

---

### Issue: TypeScript errors

**Error**: `Cannot find module '@/types/chatbot' or its corresponding type declarations`

**Solution**:
```bash
# Check tsconfig.json has path aliases configured
# Restart TypeScript server in VS Code
# Cmd+Shift+P → "TypeScript: Restart TS Server"
```

---

### Issue: Tailwind styles not applying

**Error**: Styles look unstyled, no gradients or colors

**Solution**:
```bash
# Verify tailwind.config.js exists
# Check postcss.config.js exists
# Restart dev server
npm run dev
```

---

### Issue: LocalStorage quota exceeded

**Error**: `QuotaExceededError: Failed to execute 'setItem' on 'Storage'`

**Solution**:
```javascript
// Clear old sessions
localStorage.clear();

// Or implement automatic trimming (see data-model.md)
```

---

### Issue: Export button not downloading file

**Error**: Nothing happens when clicking "下載資料"

**Solution**:
```javascript
// Check browser console for errors
// Verify Blob API support
console.log('Blob' in window); // Should be true

// Check if download attribute is supported
const a = document.createElement('a');
console.log('download' in a); // Should be true
```

---

## Development Tips

### Hot Reload Issues

If changes aren't reflecting:
```bash
# Kill dev server (Ctrl+C)
# Clear Vite cache
rm -rf node_modules/.vite
# Restart
npm run dev
```

### Debugging LocalStorage

```javascript
// In browser console
// View all keys
Object.keys(localStorage);

// View specific session
const sessionId = localStorage.getItem('current_session_id');
const session = JSON.parse(localStorage.getItem(`comparison_session_${sessionId}`));
console.log(session);

// Export current session to console
console.log(JSON.stringify(session, null, 2));
```

### Performance Profiling

```javascript
// Enable React DevTools Profiler
// In browser:
// 1. Install React DevTools extension
// 2. Open DevTools
// 3. Go to "Profiler" tab
// 4. Click record button
// 5. Interact with app
// 6. Stop recording
// 7. Analyze flamegraph
```

### Instagram Gradient Testing

```html
<!-- Test gradients in browser console -->
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); width: 200px; height: 100px; border-radius: 18px;"></div>
```

---

## Next Steps

### After Quickstart

1. **Read Full Documentation**:
   - [Feature Specification](./spec.md) - User stories and requirements
   - [Implementation Plan](./plan.md) - Technical architecture
   - [Data Model](./data-model.md) - TypeScript interfaces
   - [Research](./research.md) - Best practices and patterns

2. **Explore Contracts**:
   - [LocalStorage Schema](./contracts/localstorage-schema.json)
   - [Export Schema](./contracts/export-schema.json)
   - [Contracts README](./contracts/README.md)

3. **Start Development**:
   - Follow Phase 1 → Phase 2 → Phase 3 workflow
   - Implement SmartphoneChatbot component first (P1)
   - Add multi-instance layout (P2)
   - Implement export functionality (P2)

4. **Manual Testing Checklist**:
   - [ ] Single chatbot renders with Instagram UI
   - [ ] Messages send and display correctly
   - [ ] Typing indicator shows during response
   - [ ] LocalStorage persists data
   - [ ] Page refresh restores conversation
   - [ ] 3 chatbots render side-by-side
   - [ ] Each chatbot maintains independent state
   - [ ] Preference selection works (visual highlight)
   - [ ] "下載資料" button downloads valid JSON
   - [ ] JSON validates against schema

---

## Useful Resources

### Documentation
- [React 18 Docs](https://react.dev/)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Vite Docs](https://vitejs.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

### Libraries
- [react-intersection-observer](https://www.npmjs.com/package/react-intersection-observer)
- [lodash](https://lodash.com/docs/)
- [ajv](https://ajv.js.org/)

### Tools
- [React DevTools](https://react.dev/learn/react-developer-tools)
- [VS Code](https://code.visualstudio.com/)
- [JSON Schema Validator](https://www.jsonschemavalidator.net/)

### Learning
- [Instagram UI Tutorial](https://www.youtube.com/results?search_query=instagram+chat+ui+react)
- [LocalStorage Guide](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [Tailwind Gradients](https://tailwindcss.com/docs/gradient-color-stops)

---

## Getting Help

### Common Questions

**Q: How do I mock chatbot responses?**

A: Create a `chatbotService.ts` with a mock function:
```typescript
export async function sendMessage(chatId: string, message: string): Promise<string> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Return mock response
  return `Mock response from ${chatId} to: "${message}"`;
}
```

**Q: How do I add more chatbot instances?**

A: Add more `<SmartphoneChatbot>` components with unique `chatId`:
```tsx
<SmartphoneChatbot chatId="bot4" displayName="Llama" />
```

**Q: How do I customize the Instagram gradient?**

A: Edit Tailwind classes in MessageBubble.tsx:
```tsx
className="bg-gradient-to-r from-[#yourColor1] to-[#yourColor2]"
```

**Q: How do I test on mobile?**

A: Use browser DevTools device emulation or expose dev server:
```bash
npm run dev -- --host
# Access from mobile: http://<your-ip>:5173/
```

---

## Support

For questions or issues:

1. **Check documentation** in `specs/001-chatbot-annotation/`
2. **Review contracts** for data structure questions
3. **Inspect browser console** for errors
4. **Check localStorage** in DevTools → Application tab
5. **Open an issue** if problem persists

---

## Estimated Timeline

| Phase | Task | Time |
|-------|------|------|
| **Setup** | Install dependencies, start dev server | 30 min |
| **Phase 1** | Build SmartphoneChatbot component | 3-4 hours |
| **Phase 2** | Multi-instance layout + selection | 2-3 hours |
| **Phase 3** | Data export functionality | 2-3 hours |
| **Testing** | Manual smoke testing | 1 hour |
| **Total** | Complete MVP | **9-12 hours** |

**Note**: Times are estimates for an experienced React developer. Add 2-3 hours if new to React or Tailwind CSS.

---

## Success Criteria

You've successfully completed the quickstart when:

✅ Dev server runs without errors
✅ 3 chatbot instances render side-by-side
✅ Messages send and display with Instagram-style UI
✅ Independent conversations in each chatbot
✅ LocalStorage persists data across page refreshes
✅ Preference selection works (visual highlight)
✅ "下載資料" button exports valid JSON
✅ JSON validates against schema

**Congratulations! You're ready to start collecting annotation data! 🎉**
