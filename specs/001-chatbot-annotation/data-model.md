# Data Model: Multi-Chatbot Annotation Interface

**Feature**: 001-chatbot-annotation
**Date**: 2025-11-06
**Language**: TypeScript

## Overview

This document defines the data structures for the chatbot annotation interface. All types are TypeScript interfaces representing data stored in browser localStorage and exported as JSON files.

## Core Entities

### Message

Represents a single message in a conversation between user and chatbot.

```typescript
interface Message {
  /** Unique identifier for the message (timestamp-based) */
  id: string;

  /** Message content (text) */
  content: string;

  /** Who sent the message */
  sender: 'user' | 'bot';

  /** When the message was sent (ISO 8601 timestamp) */
  timestamp: string;

  /** Display metadata (optional, for UI purposes) */
  displayStyle?: {
    /** Background color for custom message styling */
    backgroundColor?: string;
    /** Text color override */
    textColor?: string;
  };
}
```

**Validation Rules**:
- `id` must be unique within a conversation
- `content` must not be empty string
- `timestamp` must be valid ISO 8601 format
- `sender` must be either 'user' or 'bot'

**Example**:
```json
{
  "id": "1730906096789",
  "content": "What is the capital of France?",
  "sender": "user",
  "timestamp": "2025-11-06T12:34:56.789Z"
}
```

---

### ChatbotInstance

Represents one chatbot being compared, including its configuration and conversation history.

```typescript
interface ChatbotInstance {
  /** Unique identifier for this chatbot instance */
  chatId: string;

  /** Display name shown in UI */
  displayName: string;

  /** Avatar/icon URL (optional) */
  avatar?: string;

  /** Complete conversation history with this chatbot */
  messages: Message[];

  /** Current response state */
  state: 'idle' | 'typing' | 'responded' | 'error';

  /** Configuration settings that differentiate this instance */
  config?: {
    /** Model name or identifier */
    model?: string;
    /** Temperature or other parameters */
    parameters?: Record<string, unknown>;
    /** API endpoint if applicable */
    apiEndpoint?: string;
  };

  /** Last error message if state === 'error' */
  errorMessage?: string;
}
```

**Validation Rules**:
- `chatId` must be unique across all instances in a session
- `displayName` must not be empty
- `messages` array maintains chronological order (oldest first)
- `state` transitions: idle → typing → responded/error → idle

**Example**:
```json
{
  "chatId": "bot1",
  "displayName": "GPT-4",
  "avatar": "https://example.com/gpt4-avatar.png",
  "messages": [
    {
      "id": "1730906096789",
      "content": "What is the capital of France?",
      "sender": "user",
      "timestamp": "2025-11-06T12:34:56.789Z"
    },
    {
      "id": "1730906098123",
      "content": "The capital of France is Paris.",
      "sender": "bot",
      "timestamp": "2025-11-06T12:34:58.123Z"
    }
  ],
  "state": "idle",
  "config": {
    "model": "gpt-4-turbo",
    "parameters": {
      "temperature": 0.7
    }
  }
}
```

---

### PreferenceSelection

Represents user's choice of preferred chatbot overall.

```typescript
interface PreferenceSelection {
  /** ID of the selected chatbot (or null if not selected) */
  selectedChatbotId: string | null;

  /** When the selection was made (ISO 8601 timestamp) */
  timestamp: string;

  /** Optional notes or reasoning (future enhancement) */
  notes?: string;
}
```

**Validation Rules**:
- `selectedChatbotId` must match a valid `chatId` from the session's chatbot instances (or be null)
- `timestamp` must be valid ISO 8601 format
- Selection can be changed multiple times before export

**Example**:
```json
{
  "selectedChatbotId": "bot2",
  "timestamp": "2025-11-06T12:45:30.456Z"
}
```

---

### ComparisonSession

Represents one complete annotation task stored in localStorage.

```typescript
interface ComparisonSession {
  /** Unique session identifier (UUID v4) */
  sessionId: string;

  /** All chatbot instances in this comparison */
  chatbots: ChatbotInstance[];

  /** User's overall preference selection */
  selection: PreferenceSelection;

  /** Session metadata */
  metadata: {
    /** When the session was created */
    createdAt: string;
    /** Last update timestamp */
    updatedAt: string;
    /** Session version (for schema migrations) */
    version: string;
  };
}
```

**Validation Rules**:
- `sessionId` must be unique (generated with UUID v4)
- `chatbots` array must contain 2-4 elements
- Each `chatId` in `chatbots` must be unique
- `metadata.version` follows semver format (e.g., "1.0.0")

**LocalStorage Key**: `comparison_session_{sessionId}`

**Example**:
```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "chatbots": [
    {
      "chatId": "bot1",
      "displayName": "GPT-4",
      "messages": [...],
      "state": "idle"
    },
    {
      "chatId": "bot2",
      "displayName": "Claude",
      "messages": [...],
      "state": "idle"
    },
    {
      "chatId": "bot3",
      "displayName": "Gemini",
      "messages": [...],
      "state": "idle"
    }
  ],
  "selection": {
    "selectedChatbotId": "bot2",
    "timestamp": "2025-11-06T12:45:30.456Z"
  },
  "metadata": {
    "createdAt": "2025-11-06T12:30:00.000Z",
    "updatedAt": "2025-11-06T12:45:30.456Z",
    "version": "1.0.0"
  }
}
```

---

### ExportedData

Represents the JSON file structure for data export via "下載資料" button.

```typescript
interface ExportedData {
  /** Session identifier (matches ComparisonSession.sessionId) */
  sessionId: string;

  /** When the data was exported */
  exportTimestamp: string;

  /** Selected chatbot ID (or null if no selection made) */
  selectedChatbotId: string | null;

  /** Complete chatbot data including all conversations */
  chatbots: {
    chatId: string;
    displayName: string;
    messages: Message[];
    config?: ChatbotInstance['config'];
  }[];

  /** Export metadata */
  metadata: {
    /** Export format version (for compatibility) */
    exportVersion: string;
    /** Session creation time */
    sessionCreatedAt: string;
    /** Session last updated time */
    sessionUpdatedAt: string;
    /** Total number of messages across all chatbots */
    totalMessages: number;
  };
}
```

**Validation Rules**:
- `exportTimestamp` must be in ISO 8601 format
- `selectedChatbotId` must match one of the `chatId` values in `chatbots` array (or be null)
- `exportVersion` follows semver (e.g., "1.0.0")
- `totalMessages` must equal sum of all message array lengths

**Filename Format**: `chatbot-annotation-{timestamp}.json`
- Example: `chatbot-annotation-1730906400000.json`

**Example**:
```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "exportTimestamp": "2025-11-06T13:00:00.000Z",
  "selectedChatbotId": "bot2",
  "chatbots": [
    {
      "chatId": "bot1",
      "displayName": "GPT-4",
      "messages": [
        {
          "id": "1730906096789",
          "content": "What is the capital of France?",
          "sender": "user",
          "timestamp": "2025-11-06T12:34:56.789Z"
        },
        {
          "id": "1730906098123",
          "content": "The capital of France is Paris.",
          "sender": "bot",
          "timestamp": "2025-11-06T12:34:58.123Z"
        }
      ],
      "config": {
        "model": "gpt-4-turbo"
      }
    },
    {
      "chatId": "bot2",
      "displayName": "Claude",
      "messages": [...]
    },
    {
      "chatId": "bot3",
      "displayName": "Gemini",
      "messages": [...]
    }
  ],
  "metadata": {
    "exportVersion": "1.0.0",
    "sessionCreatedAt": "2025-11-06T12:30:00.000Z",
    "sessionUpdatedAt": "2025-11-06T12:45:30.456Z",
    "totalMessages": 12
  }
}
```

---

## State Transitions

### ChatbotInstance State Machine

```
       ┌──────┐
       │ idle │ ◄─────────┐
       └──┬───┘           │
          │               │
    (user sends message)  │
          │               │
          ▼               │
      ┌────────┐         │
      │ typing │         │
      └───┬────┘         │
          │              │
    (response received)  │
          │              │
          ▼              │
    ┌───────────┐        │
    │ responded ├────────┘
    └───────────┘
          │
    (or error occurs)
          │
          ▼
      ┌───────┐
      │ error │
      └───┬───┘
          │
    (user retries)
          │
          └─────────► idle
```

**State Descriptions**:
- **idle**: Waiting for user input
- **typing**: Processing user message, showing typing indicator
- **responded**: Message received, ready for next input
- **error**: Failed to get response, showing error message

---

## Data Relationships

### Entity Relationship Diagram

```
ComparisonSession (localStorage root)
    │
    ├── sessionId (UUID v4)
    ├── metadata (timestamps, version)
    ├── selection (PreferenceSelection)
    │       └── selectedChatbotId (foreign key to ChatbotInstance)
    │
    └── chatbots[] (array of ChatbotInstance)
            ├── chatId (unique identifier)
            ├── displayName
            ├── messages[] (array of Message)
            │       ├── id
            │       ├── content
            │       ├── sender
            │       └── timestamp
            ├── state (enum)
            └── config (optional settings)

ExportedData (JSON export)
    │
    ├── sessionId (matches ComparisonSession)
    ├── exportTimestamp
    ├── selectedChatbotId (nullable)
    ├── chatbots[] (flattened from ComparisonSession)
    └── metadata (export version, timestamps)
```

---

## LocalStorage Schema

### Storage Keys

| Key | Value Type | Description |
|-----|------------|-------------|
| `current_session_id` | string (UUID) | Active session identifier |
| `comparison_session_{sessionId}` | ComparisonSession (JSON string) | Complete session data |
| `chat_{chatId}` | Message[] (JSON string) | Individual chatbot conversation (legacy/backup) |

### Storage Operations

**Initialize New Session**:
```typescript
const sessionId = crypto.randomUUID();
const session: ComparisonSession = {
  sessionId,
  chatbots: [
    { chatId: 'bot1', displayName: 'GPT-4', messages: [], state: 'idle' },
    { chatId: 'bot2', displayName: 'Claude', messages: [], state: 'idle' },
    { chatId: 'bot3', displayName: 'Gemini', messages: [], state: 'idle' }
  ],
  selection: { selectedChatbotId: null, timestamp: new Date().toISOString() },
  metadata: {
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    version: '1.0.0'
  }
};

localStorage.setItem('current_session_id', sessionId);
localStorage.setItem(`comparison_session_${sessionId}`, JSON.stringify(session));
```

**Load Existing Session**:
```typescript
const sessionId = localStorage.getItem('current_session_id');
if (sessionId) {
  const sessionData = localStorage.getItem(`comparison_session_${sessionId}`);
  const session: ComparisonSession = JSON.parse(sessionData);
  // Restore chatbot states
}
```

**Update Message History**:
```typescript
const session = getCurrentSession();
const chatbot = session.chatbots.find(c => c.chatId === chatId);
chatbot.messages.push(newMessage);
session.metadata.updatedAt = new Date().toISOString();
saveSession(session);
```

---

## Data Validation

### Runtime Validation Helpers

```typescript
/**
 * Validates Message structure
 */
function isValidMessage(msg: unknown): msg is Message {
  if (typeof msg !== 'object' || msg === null) return false;
  const m = msg as Message;

  return (
    typeof m.id === 'string' &&
    typeof m.content === 'string' && m.content.length > 0 &&
    (m.sender === 'user' || m.sender === 'bot') &&
    typeof m.timestamp === 'string' && !isNaN(Date.parse(m.timestamp))
  );
}

/**
 * Validates ChatbotInstance structure
 */
function isValidChatbotInstance(bot: unknown): bot is ChatbotInstance {
  if (typeof bot !== 'object' || bot === null) return false;
  const b = bot as ChatbotInstance;

  return (
    typeof b.chatId === 'string' &&
    typeof b.displayName === 'string' && b.displayName.length > 0 &&
    Array.isArray(b.messages) &&
    b.messages.every(isValidMessage) &&
    ['idle', 'typing', 'responded', 'error'].includes(b.state)
  );
}

/**
 * Validates ComparisonSession structure
 */
function isValidComparisonSession(session: unknown): session is ComparisonSession {
  if (typeof session !== 'object' || session === null) return false;
  const s = session as ComparisonSession;

  return (
    typeof s.sessionId === 'string' &&
    Array.isArray(s.chatbots) &&
    s.chatbots.length >= 2 &&
    s.chatbots.length <= 4 &&
    s.chatbots.every(isValidChatbotInstance) &&
    typeof s.selection === 'object' &&
    (s.selection.selectedChatbotId === null ||
     s.chatbots.some(b => b.chatId === s.selection.selectedChatbotId))
  );
}
```

---

## Schema Versioning

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-06 | Initial schema definition |

### Migration Strategy

When schema changes are needed:

1. **Increment version** in `metadata.version` or `exportVersion`
2. **Write migration function** to transform old data to new format
3. **Detect version** on load and apply migrations
4. **Preserve original** data before migration (backup in `_backup` key)

**Example Migration**:
```typescript
function migrateSession(session: any): ComparisonSession {
  const version = session.metadata?.version || '0.0.0';

  if (version === '1.0.0') {
    return session; // Already latest version
  }

  // Example: v0.x to v1.0.0 migration
  if (version.startsWith('0.')) {
    return {
      ...session,
      metadata: {
        ...session.metadata,
        version: '1.0.0'
      },
      // Add any new required fields
    };
  }

  throw new Error(`Unsupported session version: ${version}`);
}
```

---

## Type Definitions File

All types should be defined in `/frontend/src/types/` directory:

```
types/
├── chatbot.ts       # Message, ChatbotInstance types
├── session.ts       # ComparisonSession, PreferenceSelection types
└── export.ts        # ExportedData type
```

**Example chatbot.ts**:
```typescript
export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot';
  timestamp: string;
  displayStyle?: {
    backgroundColor?: string;
    textColor?: string;
  };
}

export interface ChatbotInstance {
  chatId: string;
  displayName: string;
  avatar?: string;
  messages: Message[];
  state: 'idle' | 'typing' | 'responded' | 'error';
  config?: {
    model?: string;
    parameters?: Record<string, unknown>;
    apiEndpoint?: string;
  };
  errorMessage?: string;
}

export type ChatbotState = ChatbotInstance['state'];
export type MessageSender = Message['sender'];
```

---

## Best Practices

### Type Safety
- ✅ Use TypeScript strict mode
- ✅ Avoid `any` type; use `unknown` with type guards
- ✅ Define all fields explicitly (no index signatures)
- ✅ Use `Readonly<T>` for immutable data

### Data Integrity
- ✅ Validate data on localStorage read
- ✅ Generate UUIDs for session and message IDs
- ✅ Use ISO 8601 timestamps consistently
- ✅ Handle localStorage quota exceeded errors

### Performance
- ✅ Limit message history to 200 per chatbot
- ✅ Debounce localStorage writes (500ms)
- ✅ Use shallow comparison for state updates
- ✅ Memoize expensive computations (message sorting, filtering)

### Error Handling
- ✅ Try-catch around all localStorage operations
- ✅ Fallback to in-memory state if localStorage fails
- ✅ Log errors with context (chatId, sessionId)
- ✅ Show user-friendly error messages
