# Feature Specification: Multi-Chatbot Comparison Annotation Interface

**Feature Branch**: `001-chatbot-annotation`
**Created**: 2025-11-06
**Status**: Draft
**Input**: User description: "I need to build an annotation interface for comparing multiple chatbots simultaneously. The interface should: 1. Have a SmartphoneChatbot component that mimics Instagram's chat interface 2. Display multiple SmartphoneChatbot components side-by-side for comparison 3. Allow users to chat with each bot independently 4. Let users select which chatbot response they prefer 5. Use React for the frontend 6. Prioritize speed and simplicity over extensive testing 7. Have a phone-like aspect ratio and styling for each chatbot component. Target: Quick MVP for data collection, Instagram chat UI aesthetic, responsive smartphone-sized components that can be displayed in a grid or side-by-side layout."

## Clarifications

### Session 2025-11-06

- Q: What mechanism should the SmartphoneChatbot components use to generate bot responses? → A: Separate chat API will be provided (out of scope for frontend implementation)
- Q: How should the chatbot instances be configured when the application loads? → A: Hardcoded configuration with simple array structure [{"chatbot_name": "ABC"}, {"chatbot_name": "123"}]; chatbot_name passed as parameter to chat API
- Q: What is the chat API request/response contract format? → A: POST /chat with Request: {"user_id": string, "session_id": string|null, "message": string, "chatbot_name": string} → Response: {"session_id": string, "message": string, "agent": string, "metadata"?: object}. HTTP Status: 200 OK, 404 Not Found, 403 Forbidden, 500 Internal Server Error. Timeout: 120 seconds
- Q: How should the frontend generate and manage the user_id for chat API requests? → A: Generate once per browser session, persist in localStorage, reuse across multiple comparison sessions until localStorage cleared
- Q: Should the exported JSON file include backend-specific identifiers for analysis correlation? → A: Yes, include all identifiers (user_id, backend session_ids per chatbot, agent names in message metadata)
- Q: Where should the annotation interface be implemented relative to the existing frontend directory? → A: Create separate `annotation/` directory at repository root - this is a standalone data collection tool, not part of the main medical chatbot frontend

## User Scenarios & Testing

### User Story 1 - Chat with Individual Smartphone UI Instance (Priority: P1)

As a data annotator, I need to interact with a single chatbot through a smartphone-style chat interface, so I can have a natural conversation and evaluate the chatbot's behavior.

**Why this priority**: This is the foundational component of the annotation interface. The SmartphoneChatbot component must work independently before we can create multiple instances for comparison. This delivers immediate value as a reusable chat UI component.

**Independent Test**: Can be fully tested by rendering a single SmartphoneChatbot component, typing messages, receiving responses, and verifying Instagram-style UI elements display correctly. Delivers standalone chat interface that can be used individually or replicated.

**Acceptance Scenarios**:

1. **Given** a SmartphoneChatbot component is rendered, **When** I type "What is the capital of France?" and send the message, **Then** the chatbot receives the message and displays a response in the chat window
2. **Given** I have sent multiple messages to a chatbot, **When** I scroll through the chat history, **Then** I see the complete conversation history with timestamps in Instagram-style chat bubbles
3. **Given** the chatbot is processing my message, **When** I wait for a response, **Then** I see a typing indicator (like Instagram's animated dots) until the response arrives

---

### User Story 2 - Display Multiple Independent Chatbot Instances (Priority: P2)

As a data annotator, I need to see multiple SmartphoneChatbot instances side-by-side (each with different settings), so I can interact with each chatbot independently and compare their overall behavior.

**Why this priority**: Comparison requires multiple instances, but the individual SmartphoneChatbot component (P1) must work first. This story builds on P1 by replicating the component multiple times. Still critical for data collection workflow.

**Independent Test**: Can be fully tested by rendering 3 SmartphoneChatbot components in a side-by-side layout, verifying each maintains independent conversation state, and confirming layout accommodates all instances without overlap. Delivers multi-chatbot comparison capability.

**Acceptance Scenarios**:

1. **Given** the interface loads with 3 chatbot instances, **When** I view the layout, **Then** I see 3 smartphone-style containers side-by-side, each with distinct chatbot identifiers
2. **Given** I send a message in chatbot 1, **When** I switch to chatbot 2 and send a different message, **Then** each chatbot maintains its own independent conversation history without affecting the other
3. **Given** I have interacted with multiple chatbots, **When** I scroll within one chatbot's message area, **Then** only that chatbot's scroll position changes while others remain stationary

---

### User Story 3 - Select Overall Preferred Chatbot (Priority: P2)

As a data annotator, I need to select which chatbot I prefer overall after interacting with all of them, so the system can record my preference for training data.

**Why this priority**: Recording user preferences is the primary purpose of this annotation interface. However, selection only makes sense after users can interact with multiple chatbots (depends on P2). Critical for data collection objective.

**Independent Test**: Can be fully tested by interacting with multiple chatbot instances, clicking a "Select" button on one chatbot container, and verifying the selection is visually highlighted and recorded. Delivers core value of collecting comparative preference data.

**Acceptance Scenarios**:

1. **Given** I have interacted with 3 chatbot instances, **When** I click a "Select as Preferred" button on one chatbot's container, **Then** that chatbot instance is visually highlighted as selected (e.g., green border or checkmark)
2. **Given** I have already selected one chatbot as preferred, **When** I click to select a different chatbot, **Then** the previous selection is deselected and the new selection is highlighted
3. **Given** I have selected a preferred chatbot, **When** the system records my preference, **Then** it captures the complete conversation history from all chatbots along with my selection

---

### User Story 4 - Export Annotation Data (Priority: P2)

As a data annotator, I need to export my conversation histories and preference selection to a JSON file, so I can share the collected data with researchers for analysis.

**Why this priority**: Data export is essential for the data collection workflow. Without the ability to extract data from local storage, collected annotations cannot be analyzed. This is a key deliverable for the MVP.

**Independent Test**: Can be fully tested by interacting with chatbots, selecting a preference, clicking the "下載資料" (Download Data) button, and verifying a JSON file downloads with complete conversation histories and selection. Delivers data extraction capability.

**Acceptance Scenarios**:

1. **Given** I have interacted with multiple chatbots and selected a preferred one, **When** I click the "下載資料" button in the corner of the interface, **Then** a JSON file downloads containing my preference selection and all conversation histories
2. **Given** the JSON file has been downloaded, **When** I inspect its contents, **Then** I see structured data including session ID, user_id, selected chatbot identifier, timestamp, complete message histories from all chatbot instances with backend session_ids per chatbot and agent names in message metadata
3. **Given** I have not yet selected a preferred chatbot, **When** I click the "下載資料" button, **Then** the system still exports the JSON with conversation histories but marks preference as "not selected" or null

---

### User Story 5 - Navigate Between Multiple Comparison Sessions (Priority: P3)

As a data annotator, I may need to restart comparison sessions or clear data, so I can efficiently work through multiple annotation tasks.

**Why this priority**: Session management is helpful for productivity but not essential for MVP. Initial version can focus on single-session workflow with manual data export between sessions.

**Independent Test**: Can be fully tested by completing one comparison session, exporting data, then clicking a "New Comparison" or "Clear Data" button and verifying the interface resets with cleared local storage. Delivers workflow reset capability.

**Acceptance Scenarios**:

1. **Given** I have completed a comparison session and exported the data, **When** I click "Start New Comparison" or "Clear Data", **Then** all chatbot instances reset with cleared chat history and local storage is cleared
2. **Given** the interface supports configurable chatbot counts, **When** I select to compare 2, 3, or 4 chatbots, **Then** the layout adjusts to display the selected number of smartphone-style chatbot containers side-by-side

---

### Edge Cases

- What happens when a chatbot responds significantly slower than expected? System should display loading/typing indicator during response wait time without blocking user interaction with that chatbot's input (up to 120-second timeout)
- What happens when chat API times out (>120 seconds)? System should display timeout error message in that chatbot's interface and allow user to retry
- What happens when chat API returns 404 (session not found)? System should treat as new conversation, send with session_id=null, and display new response
- What happens when chat API returns 403 (session ownership error)? System should display error message and offer to start new session for that chatbot
- What happens when chat API returns 500 (server error)? System should display error message in that specific chatbot's interface without affecting other chatbot instances, allow retry
- What happens when a chatbot returns an error or fails to respond? System should display an error message in that specific chatbot's interface without affecting other chatbot instances
- What happens if screen width cannot accommodate all chatbot instances side-by-side? System should support horizontal scrolling or responsive layout adjustment to ensure all chatbots remain accessible
- What happens when messages contain very long text or special characters? System should handle text wrapping within chat bubbles and properly escape/sanitize displayed content
- What happens if a user clicks "下載資料" without selecting a preferred chatbot? System should export JSON with conversation histories and mark preference as null or "not selected"
- What happens if a user clicks "下載資料" multiple times? System should generate new JSON files with updated timestamps each time
- What happens when local storage reaches browser limits? System should handle storage quota errors gracefully and may prompt user to export and clear data
- What happens when different chatbot instances have significantly different conversation lengths? Each chatbot's scroll container should handle different content heights independently
- What happens if user refreshes the page? Data persisted in local storage should be restored, allowing users to continue their session

## Requirements

### Functional Requirements

- **FR-001**: System MUST render a single SmartphoneChatbot component with smartphone-style container (portrait aspect ratio, approximately 375-414px width, minimum 667px height)
- **FR-002**: System MUST implement Instagram-style chat interface including: right-aligned user messages with blue/purple styling, left-aligned bot messages with gray styling, rounded chat bubbles with proper padding, chat header with bot identifier, and message input field at bottom
- **FR-003**: System MUST allow users to send messages to a chatbot and receive responses within the chat interface
- **FR-004**: System MUST display conversation history with proper scrolling within the message area
- **FR-005**: System MUST show typing/loading indicators when chatbot is processing a message
- **FR-006**: System MUST handle chatbot response errors gracefully by displaying error messages in the chat interface
- **FR-007**: System MUST support rendering multiple independent SmartphoneChatbot instances simultaneously in a side-by-side layout (target: 3 instances, maximum: 4 instances)
- **FR-007a**: System MUST initialize chatbot instances from hardcoded configuration array with structure [{"chatbot_name": "ABC"}, {"chatbot_name": "123"}], passing chatbot_name as parameter to chat API
- **FR-007b**: System MUST generate unique user_id on first application load, persist in localStorage, and reuse across all comparison sessions until localStorage is cleared
- **FR-007c**: System MUST integrate with chat API using POST /chat endpoint with request payload {"user_id": string, "session_id": string|null, "message": string, "chatbot_name": string} and handle response {"session_id": string, "message": string, "agent": string, "metadata"?: object}
- **FR-007d**: System MUST handle chat API HTTP status codes: 200 (success), 404 (session not found), 403 (session ownership error), 500 (server error) with appropriate user feedback
- **FR-007e**: System MUST implement 120-second timeout for chat API requests and display timeout error if exceeded
- **FR-008**: System MUST maintain completely independent conversation state for each chatbot instance (separate message history, scroll position, response state, and session_id per chatbot)
- **FR-009**: System MUST allow users to interact with each chatbot instance independently without affecting other instances
- **FR-010**: System MUST allow users to select one preferred chatbot overall after interacting with multiple instances
- **FR-011**: System MUST provide visual feedback when a chatbot is selected as preferred (e.g., highlight border, checkmark, or selection indicator on the container)
- **FR-012**: System MUST allow users to change their overall preference selection before finalizing
- **FR-013**: System MUST persist all conversation data and preference selection in browser local storage
- **FR-014**: System MUST restore conversation state from local storage when page is refreshed or reopened
- **FR-015**: System MUST provide a "下載資料" (Download Data) button positioned in the corner of the interface
- **FR-016**: System MUST export annotation data as a JSON file when user clicks "下載資料" button
- **FR-017**: Exported JSON MUST include session identifier, user_id, selected chatbot identifier (or null if not selected), timestamp, complete conversation histories from all chatbot instances with backend session_ids per chatbot, and agent names in message metadata for analysis correlation
- **FR-018**: System MUST generate unique filenames for exported JSON files (e.g., including timestamp) to prevent overwrites
- **FR-019**: System MUST handle local storage quota errors gracefully and provide feedback to users
- **FR-020**: System MUST support horizontal scrolling or responsive layout adjustment when screen width cannot accommodate all chatbot instances side-by-side

### Key Entities

- **ChatbotInstance**: Represents one chatbot being compared. Attributes include chatbot_name (used for API calls and display), session_id (backend-generated UUID for conversation continuity), conversation history (messages sent and received), and current response state (idle/typing/responded/error). Configuration is hardcoded as simple array structure: [{"chatbot_name": "ABC"}, {"chatbot_name": "123"}]
- **Message**: Represents a single message in conversation. Attributes include message text content, sender (user or specific chatbot), timestamp, agent name (from API response), and display styling information
- **ComparisonSession**: Represents one annotation task stored in local storage. Attributes include session identifier, user_id (generated once per browser session and persisted), list of active chatbot instances (each with independent conversation history and backend session_id), user's overall preference selection (or null if not selected), and creation/update timestamps
- **PreferenceSelection**: Represents user's choice of preferred chatbot overall. Attributes include selected chatbot identifier (or null if not selected) and timestamp of selection
- **ExportedData**: Represents the JSON file structure for data export. Attributes include session identifier, user_id, selected chatbot identifier (or null), export timestamp, and complete conversation histories from all chatbot instances with all messages (including sender, timestamp, agent name, and metadata), backend session_ids per chatbot for analysis correlation

## Success Criteria

### Measurable Outcomes

- **SC-001**: Single SmartphoneChatbot component renders successfully with Instagram-style UI (rounded bubbles, appropriate colors, proper spacing, smartphone aspect ratio)
- **SC-002**: Users can send messages and receive responses within the SmartphoneChatbot component with response latency handled gracefully (typing indicators, no UI freezing)
- **SC-003**: Interface displays 3 independent SmartphoneChatbot instances simultaneously without layout breaking on standard desktop monitors (1920x1080 or larger)
- **SC-004**: Each chatbot instance maintains completely independent conversation state allowing users to have different conversations without cross-contamination
- **SC-005**: Users can scroll and interact with individual chatbot instances without affecting other instances (independent scroll positions, input fields, response states)
- **SC-006**: All conversation data and preference selections persist in local storage and survive page refreshes
- **SC-007**: Users can successfully export annotation data by clicking "下載資料" button, resulting in a valid JSON file download
- **SC-008**: Exported JSON files contain complete and accurate data (session ID, user_id, preference selection or null, timestamp, all conversation histories with backend session_ids per chatbot and agent names for analysis correlation)
- **SC-009**: Users can visually distinguish between different chatbot instances through clear labeling, separation, and distinct identifiers in the UI
- **SC-010**: Annotators can complete one full workflow (interact with chatbots, select preference, export data) with natural pacing and intuitive UI flow

## Assumptions

- **This is a standalone annotation interface** - Implementation goes in separate `annotation/` directory at repository root, completely independent from the existing `frontend/` directory which houses the main medical chatbot interface
- A separate chat API will be provided at POST /chat endpoint (implementation is out of scope for this frontend-focused feature; frontend will integrate with defined API contract)
- Chat API follows defined contract: Request {"user_id": string, "session_id": string|null, "message": string, "chatbot_name": string} → Response {"session_id": string, "message": string, "agent": string, "metadata"?: object}
- Frontend generates unique user_id once per browser session on first load, persists in localStorage, and reuses across all comparison sessions until localStorage is cleared
- Backend handles session_id generation (UUID) and session persistence; frontend stores session_id per chatbot for conversation continuity
- Chat API timeout is 120 seconds; frontend must handle timeout gracefully
- Chatbot instances are hardcoded in frontend configuration with simple array structure [{"chatbot_name": "ABC"}, {"chatbot_name": "123"}]; chatbot_name is the only parameter needed and is passed to chat API
- Primary deliverable is the single SmartphoneChatbot component; multi-instance layout is secondary but important for comparison workflow
- Users have independent conversations with each chatbot instance (not synchronized messages sent to all)
- Overall preference selection happens after users interact with all chatbot instances, not per-message
- No backend database or server-side storage is implemented - all data stored in browser local storage only
- Data collection workflow relies on users manually downloading JSON files and sending them back for analysis
- Exported JSON files will be collected and analyzed outside this system (no built-in data aggregation or analysis features)
- Users understand they need to export data before clearing browser data/cache (data loss is user responsibility)
- No user authentication or authorization is required for MVP (single-user or open access annotation tool)
- Interface targets desktop/laptop screens (mobile responsive design is not required for MVP)
- Standard modern web browsers (Chrome, Firefox, Safari, Edge - latest versions) are the target environment with standard local storage support (~5-10MB limit)
- No real-time collaboration features needed (single annotator working independently per session)
- Instagram-style design is for visual similarity only; no actual Instagram API integration or branding compliance is required
- Button text "下載資料" (Download Data) in Traditional Chinese is acceptable for the target user base

## Out of Scope

- User authentication and authorization system
- Backend database or server-side storage implementation (local storage only)
- Server-side data aggregation, analysis, or visualization
- Automated data upload or synchronization to remote servers
- Chat API implementation for bot responses (separate API will be provided; only frontend integration is in scope)
- Mobile/tablet responsive design (desktop-focused MVP)
- Accessibility features beyond basic HTML semantics
- Internationalization and localization (Traditional Chinese "下載資料" button is acceptable)
- Built-in analytics dashboard for viewing collected annotation data
- Batch annotation workflows or task queues
- Real-time collaboration between multiple annotators
- A/B testing framework for comparing different UI layouts
- Advanced filtering or search within conversation history
- Customizable themes or UI preferences beyond Instagram-style design
- Integration with external annotation platforms or tools
- Data backup or recovery mechanisms (user responsible for exporting data before clearing browser storage)
