# Implementation Plan: Multi-Chatbot Comparison Annotation Interface

**Branch**: `001-chatbot-annotation` | **Date**: 2025-11-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-chatbot-annotation/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a React-based annotation interface for collecting comparative chatbot preference data. The interface displays multiple smartphone-styled chat components (Instagram aesthetic) side-by-side, allowing annotators to interact with different chatbots independently, select their preferred response, and export conversation data as JSON for analysis. Focus on speed, simplicity, and MVP delivery over extensive testing.

## Technical Context

**Language/Version**: JavaScript/TypeScript (ES2020+), React 18+
**Primary Dependencies**: React 18, React Router (optional), CSS-in-JS or Tailwind CSS for styling
**Storage**: Browser LocalStorage API (5-10MB limit for conversation history and session data)
**Testing**: NEEDS CLARIFICATION (MVP prioritizes speed over extensive testing per user requirement)
**Target Platform**: Modern desktop browsers (Chrome, Firefox, Safari, Edge - latest versions)
**Project Type**: web (frontend-only, single-page application)
**Performance Goals**: <100ms UI response time, smooth scrolling within chat containers, responsive input handling
**Constraints**: localStorage ~5-10MB limit, 120-second timeout for chat API calls, desktop-focused (no mobile responsive design required)
**Scale/Scope**: Single annotator per session, 3-4 simultaneous chatbot instances, typical conversation length 10-50 messages per chatbot

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: No project-specific constitution exists yet. Using general best practices as baseline.

### Initial Assessment (Pre-Research)

**✅ Simplicity Gate**:
- Single-purpose feature (chatbot comparison interface)
- Minimal external dependencies (React + localStorage)
- No complex architectural patterns needed for MVP

**⚠️ Testing Gate**:
- User explicitly prioritizes speed over extensive testing
- **Justification**: MVP for rapid data collection, testing can be added post-validation
- **Risk Mitigation**: Manual testing of core workflows, browser dev tools for debugging

**✅ Technology Appropriateness**:
- React 18 appropriate for interactive UI components
- localStorage suitable for client-side data persistence without backend
- Modern browsers provide consistent API support

**✅ Scope Control**:
- Clear boundaries: frontend-only, no authentication, no backend
- Well-defined MVP with P1/P2/P3 priorities
- Out-of-scope items explicitly documented

### Post-Design Re-Assessment (After Phase 1)

**✅ Architecture Simplicity**:
- Component-based React architecture with clear separation of concerns
- No unnecessary abstraction layers (direct localStorage, no state management library)
- Straightforward data flow: Component state → localStorage → JSON export

**✅ Technology Choices**:
- React 18: Appropriate for interactive UI (memoization, hooks for state)
- Tailwind CSS: Rapid UI development confirmed in research (Instagram gradients, responsive utilities)
- Vite: Fast dev server for rapid iteration (confirmed in research)
- TypeScript: Beneficial for complex data structures (export schema, message types)

**✅ Implementation Feasibility**:
- All design artifacts completed (data-model.md, contracts/, quickstart.md, research.md)
- Clear component structure with reusable elements
- Well-defined localStorage schema and export format
- Manageable scope: ~11 hours estimated development time

**⚠️ Testing Strategy** (unchanged):
- Still justified for MVP speed requirement
- Manual testing checklist provided in research.md
- Risk mitigated with browser dev tools and smoke testing

**Verdict**: Constitution gates passed. Ready for implementation (Phase 2: /speckit.tasks).

## Project Structure

### Documentation (this feature)

```text
specs/001-chatbot-annotation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── chat-api.yaml    # Chat API OpenAPI contract
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

**IMPORTANT**: This annotation interface is a **standalone application** separate from the existing `frontend/` directory (which contains the main medical chatbot interface).

```text
annotation/                            # Standalone annotation interface (NEW)
├── src/
│   ├── components/
│   │   ├── SmartphoneChatbot.jsx     # Core reusable chat component (P1)
│   │   ├── ChatMessage.jsx            # Individual message bubble
│   │   ├── ChatInput.jsx              # Message input field
│   │   ├── TypingIndicator.jsx        # Loading animation
│   │   ├── ChatbotGrid.jsx            # Multi-instance layout (P2)
│   │   └── ExportButton.jsx           # Data export functionality (P2)
│   ├── services/
│   │   ├── chatApi.js                 # Chat API integration
│   │   ├── localStorage.js            # LocalStorage management
│   │   └── userIdManager.js           # user_id generation and persistence
│   ├── hooks/
│   │   ├── useChatbot.js              # Chatbot state management
│   │   └── useLocalStorage.js         # localStorage hook
│   ├── utils/
│   │   ├── exportData.js              # JSON export logic
│   │   └── constants.js               # Config (chatbot instances array)
│   ├── App.jsx                        # Main application
│   └── index.js                       # Entry point
├── public/
│   └── index.html
└── package.json
```

**Structure Decision**: Standalone frontend application in separate `annotation/` directory, completely independent from the existing `frontend/` directory. This is a purpose-built data collection tool, not part of the main medical chatbot interface. Uses standard React component hierarchy with separation of concerns: presentational components, service layer for API/storage, custom hooks for state management, and utility functions for data operations. No backend directory needed as chat API is external.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Minimal testing | MVP speed requirement from user | User explicitly prioritized speed and data collection over test coverage; testing can be added after MVP validation |

**No other violations identified** - Project uses standard React patterns with minimal abstraction and clear separation of concerns.
