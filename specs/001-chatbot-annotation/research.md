# Research: Multi-Chatbot Annotation Interface

**Feature**: 001-chatbot-annotation
**Date**: 2025-11-06
**Status**: Complete

## Overview

This document consolidates research findings for building an Instagram-style chat interface in React with multiple independent chatbot instances, local storage persistence, and JSON export functionality.

## Key Technical Decisions

### 1. Styling Framework: Tailwind CSS

**Decision**: Use Tailwind CSS for all styling

**Rationale**:
- **Instagram gradient support**: Built-in gradient utilities (`bg-gradient-to-r`, `from-[color]`, `to-[color]`) with custom color support
- **Performance**: Tree-shaking eliminates unused styles (~10KB final bundle)
- **Rapid development**: Utility-first approach speeds up UI iteration
- **Smartphone aspect ratio**: Easy responsive design with custom width values (`max-w-[414px]`)
- **Pre-built components**: Ecosystem libraries (Flowbite, daisyUI) provide chat UI accelerators

**Alternatives Considered**:
- **CSS Modules**: Good performance but requires more manual styling work; lacks gradient utilities
- **styled-components**: Runtime performance overhead (~15KB); unnecessary complexity for this use case
- **Emotion**: Better than styled-components but still adds bundle size; Tailwind is simpler

**Implementation**:
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Instagram Gradient Colors**:
- User messages: `bg-gradient-to-r from-[#667eea] to-[#764ba2]`
- Bot messages: `bg-gray-200`
- Rounded bubbles: `rounded-[18px]`

---

### 2. Component Architecture: Component-First with React.memo

**Decision**: Build reusable SmartphoneChatbot component with memoization

**Rationale**:
- **Aligns with P1 priority**: Single component must work independently before multi-instance layout
- **Performance**: `React.memo()` prevents unnecessary re-renders when sibling chatbots update
- **State isolation**: Each instance maintains independent conversation state via unique `chatId` prop
- **Reusability**: Same component used for 1 chatbot or 3 chatbots side-by-side

**Component Structure**:
```
SmartphoneChatbot/
├── index.tsx              # Main container with state management
├── ChatHeader.tsx         # Avatar, name, status (sticky positioned)
├── MessageBubble.tsx      # Individual message (memoized)
├── MessageList.tsx        # Scrollable container with auto-scroll
├── MessageInput.tsx       # Input field + send button (fixed bottom)
├── TypingIndicator.tsx    # Three-dot animation
└── styles.css             # Component-specific Tailwind classes
```

**State Management Pattern**:
- **Single chatbot**: `useState` is sufficient
- **Multiple chatbots (3-4)**: Still use `useState` per instance (simpler than global state)
- **Complex scenarios**: Consider `useReducer` if state logic becomes unwieldy

**Memoization Strategy**:
```tsx
const MessageBubble = React.memo(({ message }) => {
  // Component implementation
}, (prevProps, nextProps) => {
  return prevProps.message.id === nextProps.message.id &&
         prevProps.message.content === nextProps.message.content;
});
```

---

### 3. Scroll Behavior: Scroll Anchor Pattern

**Decision**: Use `react-intersection-observer` for intelligent auto-scroll

**Rationale**:
- **Respects user intent**: Only auto-scrolls if user is already at bottom of chat
- **Prevents disruption**: If user manually scrolls up to read history, new messages don't force scroll
- **Performance**: IntersectionObserver is native browser API (no polling)
- **Smooth UX**: `behavior: 'smooth'` provides natural scroll animation

**Implementation**:
```tsx
import { useInView } from 'react-intersection-observer';

const { ref: anchorRef, inView } = useInView();

useEffect(() => {
  if (inView) {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }
}, [messages, inView]);
```

**Alternatives Considered**:
- **Always auto-scroll**: Bad UX - forces scroll even when user reading history
- **Manual scroll button**: Extra UI element; less intuitive than automatic behavior
- **Virtualization (react-virtuoso)**: Overkill for <100 messages; adds complexity

---

### 4. Local Storage Strategy: Debounced Writes

**Decision**: Debounce localStorage writes with 500ms delay

**Rationale**:
- **Performance**: Writing on every keystroke causes UI lag (localStorage is synchronous)
- **Battery efficiency**: Reduces unnecessary disk writes on mobile devices
- **Data safety**: Still captures all data (delayed writes still persist before page close)
- **Browser limits**: localStorage quota is 5-10MB; debouncing reduces quota pressure

**Implementation**:
```tsx
import { debounce } from 'lodash';

const debouncedSave = useMemo(
  () => debounce((messages) => {
    try {
      localStorage.setItem(`chat_${chatId}`, JSON.stringify(messages));
    } catch (err) {
      if (err.name === 'QuotaExceededError') {
        // Fallback: trim to last 50 messages
        const trimmed = messages.slice(-50);
        localStorage.setItem(`chat_${chatId}`, JSON.stringify(trimmed));
      }
    }
  }, 500),
  [chatId]
);

useEffect(() => {
  debouncedSave(messages);
}, [messages, debouncedSave]);
```

**Quota Handling**:
- **Limit message history**: Keep only last 200 messages per chatbot in memory
- **Graceful degradation**: If quota exceeded, trim to 50 messages and warn user
- **Export reminder**: Show notification encouraging users to export data regularly

---

### 5. Typing Indicator: Throttled Events with Auto-Hide

**Decision**: Show typing indicator with 3-second auto-hide and 1-second throttle

**Rationale**:
- **Network efficiency**: Throttling to 1/second prevents excessive API calls
- **UX clarity**: Three-dot animation clearly indicates bot is "thinking"
- **Instagram parity**: Mimics familiar Instagram Direct messaging behavior
- **Memory safety**: Proper cleanup prevents memory leaks on unmount

**Implementation**:
```tsx
const timeoutRef = useRef(null);

const handleTyping = useCallback(() => {
  setIsTyping(true);
  clearTimeout(timeoutRef.current);
  timeoutRef.current = setTimeout(() => setIsTyping(false), 3000);
}, []);

// Cleanup on unmount
useEffect(() => {
  return () => clearTimeout(timeoutRef.current);
}, []);
```

**Animation**:
```css
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-10px); }
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
```

---

### 6. Multi-Instance State: Independent chatId Namespacing

**Decision**: Use unique `chatId` prop for each instance to namespace localStorage

**Rationale**:
- **Data isolation**: Prevents cross-contamination between chatbot conversations
- **Independent state**: Each component maintains own useState without global state
- **Simpler architecture**: No need for Redux/Zustand for 3-4 chatbot instances
- **localStorage keys**: `chat_${chatId}` prevents key collisions

**Implementation**:
```tsx
function App() {
  return (
    <div className="flex gap-4">
      <SmartphoneChatbot chatId="bot1" name="GPT-4" />
      <SmartphoneChatbot chatId="bot2" name="Claude" />
      <SmartphoneChatbot chatId="bot3" name="Gemini" />
    </div>
  );
}

// Inside SmartphoneChatbot component:
const [messages, setMessages] = useState(() =>
  JSON.parse(localStorage.getItem(`chat_${chatId}`)) || []
);
```

**Benefits**:
- Each chatbot loads its own conversation history on mount
- Auto-saves independently without affecting other chatbots
- Can easily add/remove chatbots without refactoring state management

---

### 7. JSON Export: Client-Side File Download

**Decision**: Use browser `Blob` + `URL.createObjectURL` for JSON export

**Rationale**:
- **No backend required**: Fully client-side solution (aligns with spec)
- **Universal browser support**: Works in all modern browsers
- **Unique filenames**: Timestamp prevents file overwrites
- **Complete data**: Exports all chatbot conversations + preference selection

**Implementation**:
```tsx
const handleExport = () => {
  const exportData = {
    sessionId: sessionId,
    timestamp: new Date().toISOString(),
    selectedChatbot: selectedChatId || null,
    chatbots: [
      {
        chatId: 'bot1',
        name: 'GPT-4',
        messages: JSON.parse(localStorage.getItem('chat_bot1')) || []
      },
      // ... other chatbots
    ]
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json'
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `chatbot-annotation-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(url); // Cleanup
};
```

**Filename Format**: `chatbot-annotation-{timestamp}.json`

**Export Data Structure** (see contracts/export-schema.json for full schema):
```json
{
  "sessionId": "uuid-v4",
  "timestamp": "2025-11-06T12:34:56.789Z",
  "selectedChatbot": "bot2",
  "chatbots": [
    {
      "chatId": "bot1",
      "name": "GPT-4",
      "messages": [...]
    }
  ]
}
```

---

### 8. Testing Approach: Manual Smoke Testing

**Decision**: Prioritize manual testing over automated test suite (per spec)

**Rationale**:
- **User requirement**: Spec explicitly states "prioritize speed and simplicity over extensive testing"
- **MVP focus**: Quick data collection tool, not production SaaS
- **Development speed**: Automated tests would add 2-3 days to timeline
- **Core validation**: Manual testing sufficient for verifying:
  - Instagram-style UI renders correctly
  - Messages send/receive in all chatbots independently
  - LocalStorage persists and restores data
  - JSON export generates valid files
  - Preference selection works

**Minimal Testing Checklist**:
- [ ] Render 3 chatbot instances side-by-side
- [ ] Send messages in each chatbot independently
- [ ] Verify independent scroll positions
- [ ] Refresh page and verify data restoration
- [ ] Select preferred chatbot (visual highlight)
- [ ] Click "下載資料" and verify JSON download
- [ ] Import JSON into validator to check format
- [ ] Test on Chrome, Firefox, Safari (desktop only)

**Future Enhancement**: Add Jest + React Testing Library if this becomes long-term production tool

---

## Performance Targets

### Measured Benchmarks

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Component render | <100ms | React DevTools Profiler |
| LocalStorage write | <50ms | Performance.now() timing |
| JSON export generation | <500ms | Time from click to download |
| Scroll smoothness | 60fps | Chrome DevTools Performance |
| Multi-instance render (3 chatbots) | <300ms | Page load to interactive |

### Optimization Strategies Applied

1. **React.memo on MessageBubble** → 30-50% render reduction
2. **Debounced localStorage (500ms)** → Eliminates UI lag
3. **Scroll anchor with IntersectionObserver** → Smooth UX
4. **Message history limit (200 messages)** → Prevents memory bloat
5. **Throttled typing events (1/sec)** → Reduces network overhead

---

## Technology Stack Summary

### Core Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-intersection-observer": "^9.5.3",
    "lodash": "^4.17.21"
  },
  "devDependencies": {
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

### Build Tool: Vite

**Rationale**:
- **Fastest dev server**: Instant HMR for rapid iteration
- **Optimized production builds**: Rollup-based bundler
- **TypeScript support**: Zero-config TypeScript compilation
- **Tailwind integration**: Simple PostCSS plugin setup

**Alternatives Considered**:
- **Create React App**: Slower dev server, deprecated
- **Next.js**: Overkill for SPA (no SSR needed)
- **Webpack**: More complex configuration

---

## Risk Mitigation

### Identified Risks and Solutions

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LocalStorage quota exceeded (5-10MB) | Data loss | Limit history to 200 messages; warn user; trim on error |
| Browser refresh loses unsaved messages | Data loss | Auto-save on every message change (debounced) |
| User forgets to export data | Data loss | Add reminder UI after 10 messages |
| Multiple tabs open same interface | Data conflict | Use `storage` event listener for sync (optional) |
| Long messages break layout | UI break | CSS word-wrap + max-width constraints |
| Slow chatbot API response | Poor UX | Show typing indicator indefinitely until response |

### Browser Compatibility

**Supported Browsers** (per spec):
- Chrome 90+ ✅
- Firefox 88+ ✅
- Safari 14+ ✅
- Edge 90+ ✅

**Required APIs**:
- localStorage ✅ (universal support)
- IntersectionObserver ✅ (96% global support)
- Blob + URL.createObjectURL ✅ (universal support)
- CSS gradients ✅ (universal support)

---

## Development Workflow

### Phase 1: Core Component (P1 Priority)

1. **Setup Vite + React + Tailwind** (~30 min)
2. **Build SmartphoneChatbot component** (~3 hours)
   - ChatHeader with avatar
   - MessageBubble with Instagram gradients
   - MessageList with scroll behavior
   - MessageInput with send functionality
   - TypingIndicator animation
3. **Implement localStorage persistence** (~1 hour)
4. **Manual smoke testing** (~30 min)

**Estimated Time**: 5 hours

### Phase 2: Multi-Instance Layout (P2 Priority)

1. **ComparisonLayout component** (~1 hour)
   - Render 3 SmartphoneChatbot instances
   - Handle responsive layout (horizontal scroll if needed)
2. **Preference selection** (~1 hour)
   - Click handler for selection
   - Visual highlight (green border)
   - Store selection in state
3. **Manual testing** (~30 min)

**Estimated Time**: 2.5 hours

### Phase 3: Data Export (P2 Priority)

1. **ExportButton component** (~1 hour)
   - "下載資料" button with Traditional Chinese text
   - Position in corner (absolute/fixed)
2. **Export service** (~1.5 hours)
   - Aggregate data from all chatbots
   - Generate JSON with proper schema
   - Handle edge cases (no selection, empty conversations)
   - Create download link with unique filename
3. **JSON schema validation** (~30 min)
4. **Manual testing** (~30 min)

**Estimated Time**: 3.5 hours

### Total Development Time: ~11 hours

---

## Open Questions Resolved

### Q1: State Management Library?

**Answer**: No external state library needed

**Reasoning**:
- 3-4 chatbot instances manageable with local component state
- Each component uses `useState` independently
- Shared state (preference selection) can live in parent component
- Adding Redux/Zustand would be premature optimization

### Q2: Message Virtualization?

**Answer**: Not needed for MVP

**Reasoning**:
- Typical conversation: 10-50 messages per chatbot
- Message history limited to 200 per chatbot
- Virtualization (react-virtuoso) adds complexity without benefit
- Can add later if users report performance issues

### Q3: Multi-Tab Synchronization?

**Answer**: Optional, defer to future enhancement

**Reasoning**:
- Primary use case: single tab annotation workflow
- Multi-tab sync adds complexity (BroadcastChannel or storage events)
- If implemented later, use `storage` event listener (simpler than BroadcastChannel)

### Q4: TypeScript vs JavaScript?

**Answer**: TypeScript recommended

**Reasoning**:
- Complex nested data structures (messages, sessions, export format)
- Type safety prevents bugs in localStorage serialization
- Better IDE autocomplete for developer experience
- Minimal setup overhead with Vite

### Q5: Chatbot API Integration?

**Answer**: Mock service for initial development

**Reasoning**:
- Spec assumes "chatbot backend APIs or mock response mechanisms already exist"
- Create `chatbotService.ts` with mock responses initially
- Easy to swap mock for real API later
- Mock allows independent frontend development

---

## Next Steps (Phase 1)

1. **Create data-model.md** - Document TypeScript interfaces for all entities
2. **Create contracts/** - Define localStorage schema and export JSON schema
3. **Create quickstart.md** - Developer setup guide
4. **Update CLAUDE.md** - Add React 18, Tailwind CSS, Vite to active technologies
5. **Begin implementation** - Start with SmartphoneChatbot component (P1)

---

## References

- **Instagram UI Research**: Official Instagram Direct messaging patterns
- **React Performance**: React 18 documentation on memoization and concurrent features
- **Tailwind CSS**: Official documentation for gradient utilities
- **LocalStorage Best Practices**: MDN Web Docs on storage limits and error handling
- **Browser Compatibility**: Can I Use data for IntersectionObserver and Blob APIs
