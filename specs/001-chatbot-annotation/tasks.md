# Tasks: Multi-Chatbot Comparison Annotation Interface

**Input**: Design documents from `/specs/001-chatbot-annotation/`
**Prerequisites**: plan.md (✓), spec.md (✓), research.md (✓), data-model.md (✓), contracts/ (✓)

**Tests**: Tests are NOT requested per spec ("prioritize speed and simplicity over extensive testing"). Manual smoke testing will be performed instead.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **IMPORTANT**: This is a **standalone annotation interface** - use `annotation/` directory, NOT `frontend/`
- **Web app structure**: `annotation/src/`, `annotation/tests/`
- **Spec docs**: `specs/001-chatbot-annotation/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure in standalone `annotation/` directory

- [X] T001 Create annotation project structure (annotation/src/, annotation/public/, annotation/tests/)
- [X] T002 Initialize React + TypeScript project with Vite (annotation/package.json, annotation/tsconfig.json, annotation/vite.config.ts)
- [X] T003 [P] Install core dependencies: react@^18.2.0, react-dom@^18.2.0, typescript@^5.0.0
- [X] T004 [P] Install UI dependencies: tailwindcss@^3.4.0, postcss@^8.4.32, autoprefixer@^10.4.16
- [X] T005 [P] Install utility dependencies: react-intersection-observer@^9.5.3, lodash@^4.17.21
- [X] T006 [P] Configure Tailwind CSS (annotation/tailwind.config.js, annotation/postcss.config.js)
- [X] T007 [P] Configure ESLint and Prettier for code quality
- [X] T008 Create base App component structure in annotation/src/App.tsx
- [X] T009 Create HTML template with viewport meta tags in annotation/index.html
- [X] T010 [P] Add Instagram gradient color palette to Tailwind config (from-[#667eea] to-[#764ba2])

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core type definitions, services, and utilities that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T011 [P] Create Message interface in annotation/src/types/chatbot.ts
- [X] T012 [P] Create ChatbotInstance interface in annotation/src/types/chatbot.ts
- [X] T013 [P] Create ComparisonSession interface in annotation/src/types/session.ts
- [X] T014 [P] Create PreferenceSelection interface in annotation/src/types/session.ts
- [X] T015 [P] Create ExportedData interface in annotation/src/types/export.ts
- [X] T016 [P] Implement timestamp utility functions in annotation/src/utils/timestamp.ts
- [X] T017 [P] Implement data validation helpers in annotation/src/utils/validation.ts (isValidMessage, isValidChatbotInstance, isValidComparisonSession)
- [X] T018 Implement localStorage service in annotation/src/services/storageService.ts (save, load, debounced writes with 500ms delay, quota error handling)
- [X] T019 Implement mock chatbot service in annotation/src/services/chatbotService.ts (sendMessage with simulated delay, mock responses)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Chat with Individual Smartphone UI Instance (Priority: P1) 🎯 MVP

**Goal**: Build a single reusable SmartphoneChatbot component with Instagram-style UI that maintains conversation state and persists to localStorage

**Independent Test**: Render one SmartphoneChatbot component, type messages, receive responses, verify Instagram-style UI elements display correctly, refresh page and verify data restoration from localStorage

### Implementation for User Story 1

- [X] T020 [P] [US1] Create ChatHeader component in annotation/src/components/SmartphoneChatbot/ChatHeader.tsx (avatar, display name, status indicator, sticky positioning)
- [X] T021 [P] [US1] Create MessageBubble component in annotation/src/components/SmartphoneChatbot/MessageBubble.tsx (Instagram gradient for user messages, gray for bot, rounded-[18px], React.memo optimization)
- [X] T022 [P] [US1] Create TypingIndicator component in annotation/src/components/SmartphoneChatbot/TypingIndicator.tsx (three-dot animation with 0.2s stagger)
- [X] T023 [P] [US1] Create MessageInput component in annotation/src/components/SmartphoneChatbot/MessageInput.tsx (text input, send button, fixed bottom positioning, Enter key handler)
- [X] T024 [US1] Create MessageList component in annotation/src/components/SmartphoneChatbot/MessageList.tsx (scrollable container, scroll anchor pattern with react-intersection-observer, depends on T021, T022)
- [X] T025 [US1] Implement useChatbot custom hook in annotation/src/hooks/useChatbot.ts (message state, send message handler, typing state, error handling)
- [X] T026 [US1] Implement useLocalStorage custom hook in annotation/src/hooks/useLocalStorage.ts (load from localStorage on mount, debounced save on message changes)
- [X] T027 [US1] Create main SmartphoneChatbot component in annotation/src/components/SmartphoneChatbot/index.tsx (compose all subcomponents, smartphone aspect ratio max-w-[414px] min-h-[667px], integrate hooks from T025-T026)
- [X] T028 [US1] Add component styles in annotation/src/components/SmartphoneChatbot/styles.css (Instagram gradients, rounded corners, spacing)
- [X] T029 [US1] Update App.tsx to render single SmartphoneChatbot instance for testing (chatId="bot1", displayName="Test Bot")

**Checkpoint**: At this point, User Story 1 should be fully functional - one working chatbot with Instagram UI, message persistence, and typing indicators

---

## Phase 4: User Story 2 - Display Multiple Independent Chatbot Instances (Priority: P2)

**Goal**: Display 3 SmartphoneChatbot instances side-by-side with independent conversation state

**Independent Test**: Render 3 chatbots in side-by-side layout, send different messages to each, verify each maintains independent conversation history and scroll position, verify layout accommodates all instances without overlap

### Implementation for User Story 2

- [x] T030 [US2] Create ComparisonLayout component in annotation/src/components/ComparisonLayout/index.tsx (flex container with gap-4, horizontal scroll if needed, render 3 SmartphoneChatbot instances with unique chatIds: "bot1", "bot2", "bot3")
- [x] T031 [US2] Add layout styles in annotation/src/components/ComparisonLayout/styles.css (responsive grid/flex layout, overflow-x handling)
- [x] T032 [US2] Update App.tsx to render ComparisonLayout instead of single chatbot
- [x] T033 [US2] Configure chatbot instances with different display names (GPT-4, Claude, Gemini) and avatars

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - 3 independent chatbots with separate conversations

---

## Phase 5: User Story 3 - Select Overall Preferred Chatbot (Priority: P2)

**Goal**: Allow users to select one preferred chatbot with visual feedback and store selection in session state

**Independent Test**: Interact with multiple chatbots, click selection button on one chatbot container, verify visual highlight (green border or checkmark), change selection and verify previous deselects

### Implementation for User Story 3

- [x] T034 [P] [US3] Add selection state management to ComparisonLayout component (selectedChatbotId state, handleSelect callback)
- [x] T035 [US3] Add visual selection indicator to SmartphoneChatbot component (green border when selected, checkmark icon, conditional styling based on isSelected prop)
- [x] T036 [US3] Add "Select as Preferred" button to SmartphoneChatbot component (positioned at bottom or in header, onClick triggers parent selection handler)
- [x] T037 [US3] Update storageService to persist selection state (save selectedChatbotId in ComparisonSession, load on mount)
- [x] T038 [US3] Add selection timestamp to PreferenceSelection (record when selection was made)

**Checkpoint**: All selection functionality works - users can pick preferred chatbot and see visual feedback

---

## Phase 6: User Story 4 - Export Annotation Data (Priority: P2)

**Goal**: Allow users to download complete annotation data as JSON file with all conversations and preference selection

**Independent Test**: Interact with chatbots, select preference, click "下載資料" button, verify JSON file downloads with correct schema, validate JSON structure

### Implementation for User Story 4

- [X] T039 [US4] Implement export service in annotation/src/services/exportService.ts (aggregate data from all chatbots, generate ExportedData structure, calculate totalMessages metadata)
- [X] T040 [US4] Implement JSON Schema validation using ajv in exportService (validate before export, handle validation errors)
- [X] T041 [US4] Implement file download functionality in exportService (create Blob, URL.createObjectURL, trigger download with filename chatbot-annotation-{timestamp}.json)
- [X] T042 [US4] Create useExport custom hook in annotation/src/hooks/useExport.ts (export handler, loading state, error handling)
- [X] T043 [US4] Create ExportButton component in annotation/src/components/ExportButton/index.tsx (Traditional Chinese text "下載資料", onClick triggers export, loading indicator)
- [X] T044 [US4] Add ExportButton styles in annotation/src/components/ExportButton/styles.css (fixed/absolute positioning in corner, z-index for visibility)
- [X] T045 [US4] Integrate ExportButton into ComparisonLayout component (position in top-right or bottom-right corner)
- [X] T046 [US4] Add error handling for export failures (show alert if validation fails, handle edge case where no selection made)

**Checkpoint**: Export functionality complete - users can download valid JSON files with all annotation data

---

## Phase 7: User Story 5 - Navigate Between Multiple Comparison Sessions (Priority: P3)

**Goal**: Allow users to reset sessions and clear data for new annotation tasks

**Independent Test**: Complete comparison session, export data, click "New Comparison" button, verify all chatbot instances reset with cleared history and localStorage cleared

### Implementation for User Story 5

- [X] T047 [P] [US5] Add session management functions to storageService (clearAllData, initializeNewSession)
- [X] T048 [US5] Create "New Comparison" or "Clear Data" button in ComparisonLayout (positioned near ExportButton, confirmation dialog before clearing)
- [X] T049 [US5] Implement reset handler that clears localStorage and reinitializes all chatbot states
- [X] T050 [US5] Add session ID generation using crypto.randomUUID() for new sessions
- [X] T051 [US5] Add confirmation dialog before clearing data (prevent accidental data loss, warn user to export first)

**Checkpoint**: Session management complete - users can reset and start new comparison sessions

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, final validation, and documentation

- [X] T052 [P] Add localStorage quota monitoring and warnings (warn at 75% full, implement trimming fallback)
- [X] T053 [P] Implement error boundaries for graceful error handling in React components
- [X] T054 [P] Add loading states and error messages throughout UI (network errors, localStorage failures)
- [X] T055 [P] Optimize performance with React.memo for MessageBubble components
- [X] T056 Add accessibility improvements (ARIA labels, keyboard navigation, focus management)
- [X] T057 [P] Add responsive layout adjustments for different screen sizes (handle narrow desktops)
- [X] T058 Update README.md with setup instructions and usage guide
- [X] T059 Run quickstart.md validation (verify all commands work, test on clean install)
- [X] T060 Perform manual smoke testing across Chrome, Firefox, Safari, Edge (follow checklist in quickstart.md)
- [X] T061 Update CLAUDE.md with React 18, Tailwind CSS, Vite technologies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (Phase 3) can start immediately after Foundational
  - User Story 2 (Phase 4) depends on User Story 1 completion (reuses SmartphoneChatbot)
  - User Story 3 (Phase 5) depends on User Story 2 completion (adds selection to multi-instance layout)
  - User Story 4 (Phase 6) depends on User Story 3 completion (exports include selection)
  - User Story 5 (Phase 7) depends on User Story 4 completion (reset after export workflow)
- **Polish (Phase 8)**: Depends on desired user stories being complete (minimum: US1-US4 for MVP)

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories - **MVP CORE**
- **User Story 2 (P2)**: Depends on US1 completion (replicates SmartphoneChatbot component)
- **User Story 3 (P2)**: Depends on US2 completion (adds selection to multi-instance layout)
- **User Story 4 (P2)**: Depends on US3 completion (exports selection data)
- **User Story 5 (P3)**: Depends on US4 completion (session reset after export workflow)

### Within Each User Story

- Setup: All [P] tasks can run in parallel
- Foundational: All [P] tasks can run in parallel
- User Story 1: T020-T023 (subcomponents) run in parallel → T024 depends on T021-T022 → T025-T026 (hooks) run in parallel → T027 composes all → T028-T029 finalize
- User Story 2: T030-T031 can run in parallel → T032-T033 integration
- User Story 3: T034-T036 implementation → T037-T038 persistence
- User Story 4: T039-T042 core logic → T043-T044 component → T045-T046 integration
- User Story 5: T047-T048 parallel → T049-T051 sequential

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003-T007)
- All Foundational tasks marked [P] can run in parallel (T011-T017)
- Within User Story 1: T020-T023 (4 subcomponents) in parallel, T025-T026 (2 hooks) in parallel
- Within User Story 4: T039-T042 (core logic) in parallel
- All Polish tasks marked [P] can run in parallel (T052-T055, T057)

---

## Parallel Example: User Story 1

```bash
# Launch all subcomponents together:
Task: T020 "Create ChatHeader component in annotation/src/components/SmartphoneChatbot/ChatHeader.tsx"
Task: T021 "Create MessageBubble component in annotation/src/components/SmartphoneChatbot/MessageBubble.tsx"
Task: T022 "Create TypingIndicator component in annotation/src/components/SmartphoneChatbot/TypingIndicator.tsx"
Task: T023 "Create MessageInput component in annotation/src/components/SmartphoneChatbot/MessageInput.tsx"

# Then launch both hooks together:
Task: T025 "Implement useChatbot custom hook in annotation/src/hooks/useChatbot.ts"
Task: T026 "Implement useLocalStorage custom hook in annotation/src/hooks/useLocalStorage.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1-2 Only)

1. Complete Phase 1: Setup (~30 minutes)
2. Complete Phase 2: Foundational (~2 hours)
3. Complete Phase 3: User Story 1 (~3-4 hours)
4. **STOP and VALIDATE**: Test single chatbot independently
5. Complete Phase 4: User Story 2 (~2-3 hours)
6. **STOP and VALIDATE**: Test 3 chatbots independently
7. MVP ready for basic annotation workflow

**Estimated MVP Time**: 8-10 hours

### Full Feature Delivery (User Stories 1-4)

1. Complete Setup + Foundational → Foundation ready (2.5 hours)
2. Add User Story 1 → Test independently → Core chatbot working (3-4 hours)
3. Add User Story 2 → Test independently → Multi-instance layout working (2-3 hours)
4. Add User Story 3 → Test independently → Selection feature working (2-3 hours)
5. Add User Story 4 → Test independently → Export functionality working (2-3 hours)
6. Add Polish tasks → Final validation → Production ready (2 hours)

**Estimated Full Feature Time**: 14-17 hours

### Incremental Delivery Milestones

- **Milestone 1 (MVP Core)**: US1 complete - Single working chatbot with Instagram UI (Hours 0-6)
- **Milestone 2 (Comparison MVP)**: US2 complete - 3 independent chatbots (Hours 6-10)
- **Milestone 3 (Data Collection MVP)**: US3-US4 complete - Selection + Export working (Hours 10-16)
- **Milestone 4 (Full Feature)**: US5 + Polish complete - Session management + production ready (Hours 16-20)

---

## Notes

- **Tests**: Manual smoke testing only per spec requirement ("prioritize speed and simplicity")
- **[P] tasks**: Different files, no dependencies - can run in parallel
- **[Story] label**: Maps task to specific user story for traceability
- **Each user story**: Independently testable at checkpoints
- **Commit strategy**: Commit after each task or logical group (e.g., all subcomponents)
- **LocalStorage**: 5-10MB limit - warn users at 75% capacity
- **Browser support**: Chrome, Firefox, Safari, Edge (latest versions, desktop only)
- **No backend**: All data in localStorage, manual JSON export workflow
- **Instagram UI**: Gradient colors from-[#667eea] to-[#764ba2], rounded-[18px] bubbles
- **Performance targets**: Component render <100ms, localStorage operations <50ms, export <500ms

---

## Manual Testing Checklist (Replace Automated Tests)

Per spec requirement for "speed over extensive testing", perform manual validation:

### User Story 1 Validation
- [ ] Single chatbot renders with Instagram-style UI
- [ ] Rounded chat bubbles display correctly (18px radius)
- [ ] User messages have blue-purple gradient
- [ ] Bot messages have gray background
- [ ] Messages send and responses appear
- [ ] Typing indicator shows during response wait
- [ ] Chat scrolls automatically when at bottom
- [ ] Chat doesn't auto-scroll when user scrolled up
- [ ] LocalStorage persists conversation
- [ ] Page refresh restores conversation history

### User Story 2 Validation
- [ ] 3 chatbots render side-by-side without overlap
- [ ] Each chatbot has unique identifier displayed
- [ ] Sending message in bot1 doesn't affect bot2/bot3
- [ ] Independent scroll positions maintained
- [ ] Layout handles horizontal scroll if window narrow
- [ ] All 3 chatbots persist independently in localStorage

### User Story 3 Validation
- [ ] "Select as Preferred" button visible on each chatbot
- [ ] Clicking selection adds visual highlight (green border/checkmark)
- [ ] Changing selection deselects previous chatbot
- [ ] Selection persists in localStorage across refresh
- [ ] Selection timestamp recorded correctly

### User Story 4 Validation
- [ ] "下載資料" button visible in corner of interface
- [ ] Button click triggers file download
- [ ] Downloaded file has format: chatbot-annotation-{timestamp}.json
- [ ] JSON file contains all conversation histories
- [ ] JSON includes selected chatbot ID (or null if not selected)
- [ ] JSON includes metadata: sessionId, timestamps, totalMessages
- [ ] JSON validates against contracts/export-schema.json schema
- [ ] Multiple clicks generate unique filenames (no overwrites)

### User Story 5 Validation
- [ ] "New Comparison" or "Clear Data" button visible
- [ ] Confirmation dialog appears before clearing
- [ ] Clearing removes all localStorage data
- [ ] All chatbot instances reset with empty history
- [ ] New session ID generated after reset
- [ ] Can start new annotation workflow after reset

### Browser Compatibility
- [ ] Test on Chrome (latest version)
- [ ] Test on Firefox (latest version)
- [ ] Test on Safari (latest version)
- [ ] Test on Edge (latest version)

### Edge Cases
- [ ] Long messages wrap correctly in bubbles
- [ ] Special characters display properly
- [ ] Very fast message sending doesn't break UI
- [ ] localStorage quota warning appears near limit
- [ ] Export works when no selection made (null value)
- [ ] Export works with empty conversations

---

## Success Criteria

**Project is complete when**:

✅ All tasks T001-T061 are checked off (or consciously deferred)
✅ Manual testing checklist passes all items
✅ quickstart.md validation succeeds
✅ Users can collect annotation data with workflow: chat → select → export
✅ Exported JSON files validate against schema
✅ All 4 target browsers work correctly

**MVP is ready when**:

✅ Tasks T001-T033 complete (Setup + Foundational + US1-US2)
✅ 3 chatbots render with Instagram UI
✅ Independent conversations maintained
✅ Manual testing passes for US1-US2

**Total Estimated Effort**: 14-17 hours for full feature (US1-US4 + Polish), 8-10 hours for MVP (US1-US2)
