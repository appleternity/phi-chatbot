# API Contracts: Multi-Chatbot Annotation Interface

**Feature**: 001-chatbot-annotation
**Date**: 2025-11-06

## Overview

This directory contains JSON Schema definitions for the chatbot annotation interface's data contracts. Since this is a frontend-only application with no backend API, the contracts focus on:

1. **LocalStorage Schema** - Data structure stored in browser localStorage
2. **Export Schema** - JSON file format exported via "下載資料" button

## Schema Files

### 1. `localstorage-schema.json`

Defines the `ComparisonSession` structure stored in browser localStorage.

**LocalStorage Keys**:
- `current_session_id` - Active session UUID
- `comparison_session_{sessionId}` - Complete session data

**Key Features**:
- Supports 2-4 simultaneous chatbot instances
- Tracks conversation history with timestamps
- Stores user preference selection
- Includes versioning for schema migrations

**Validation**:
```bash
# Validate against schema using ajv-cli
npx ajv-cli validate -s localstorage-schema.json -d session-data.json
```

---

### 2. `export-schema.json`

Defines the exported JSON file structure generated when user clicks "下載資料" (Download Data) button.

**Export Filename Format**: `chatbot-annotation-{timestamp}.json`

**Key Features**:
- Flattened chatbot data (no nested state)
- Export metadata (version, timestamps, message count)
- Nullable `selectedChatbotId` if no preference selected
- Complete conversation histories from all chatbots

**Validation**:
```bash
# Validate export files
npx ajv-cli validate -s export-schema.json -d chatbot-annotation-1730906400000.json
```

---

## Data Flow

```
User Interactions
      ↓
  LocalStorage
  (comparison_session_{sessionId})
      ↓
  Export Button Click
      ↓
  Transform to ExportedData
      ↓
  JSON File Download
  (chatbot-annotation-{timestamp}.json)
      ↓
  Manual File Sharing
      ↓
  External Analysis
```

---

## Schema Versioning

### Current Version: 1.0.0

**Version Format**: Semantic Versioning (MAJOR.MINOR.PATCH)

- **MAJOR**: Breaking changes (incompatible with previous versions)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Migration Strategy

When schema changes:

1. **Increment version** in `metadata.version` (localStorage) or `metadata.exportVersion` (export)
2. **Implement migration function** to transform old data to new format
3. **Detect version** on localStorage read and apply migrations automatically
4. **Backup original data** before migration (store in `_backup_{sessionId}` key)

**Example Migration Function**:
```typescript
function migrateSession(data: any): ComparisonSession {
  const version = data.metadata?.version || '0.0.0';

  if (version === '1.0.0') {
    return data; // Already latest
  }

  // Example: v0.9.x to v1.0.0 migration
  if (version.startsWith('0.9')) {
    return {
      ...data,
      metadata: {
        ...data.metadata,
        version: '1.0.0'
      },
      // Add any new required fields with defaults
      selection: data.selection || {
        selectedChatbotId: null,
        timestamp: new Date().toISOString()
      }
    };
  }

  throw new Error(`Unsupported version: ${version}`);
}
```

---

## TypeScript Integration

Generate TypeScript types from JSON schemas using `json-schema-to-typescript`:

```bash
# Install generator
npm install -D json-schema-to-typescript

# Generate TypeScript types
npx json2ts -i contracts/localstorage-schema.json -o src/types/session.generated.ts
npx json2ts -i contracts/export-schema.json -o src/types/export.generated.ts
```

**Usage in Code**:
```typescript
import { ComparisonSession } from './types/session.generated';
import { ExportedData } from './types/export.generated';

function loadSession(sessionId: string): ComparisonSession | null {
  const data = localStorage.getItem(`comparison_session_${sessionId}`);
  if (!data) return null;

  try {
    const parsed = JSON.parse(data);
    // Validate against schema if needed
    return parsed as ComparisonSession;
  } catch (err) {
    console.error('Failed to load session', err);
    return null;
  }
}

function exportData(session: ComparisonSession): ExportedData {
  return {
    sessionId: session.sessionId,
    exportTimestamp: new Date().toISOString(),
    selectedChatbotId: session.selection.selectedChatbotId,
    chatbots: session.chatbots.map(bot => ({
      chatId: bot.chatId,
      displayName: bot.displayName,
      messages: bot.messages,
      config: bot.config
    })),
    metadata: {
      exportVersion: '1.0.0',
      sessionCreatedAt: session.metadata.createdAt,
      sessionUpdatedAt: session.metadata.updatedAt,
      totalMessages: session.chatbots.reduce(
        (sum, bot) => sum + bot.messages.length,
        0
      )
    }
  };
}
```

---

## Validation in Production

### Runtime Validation

Use `ajv` (Another JSON Schema Validator) for runtime validation:

```bash
npm install ajv ajv-formats
```

**Implementation**:
```typescript
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import exportSchema from '../specs/001-chatbot-annotation/contracts/export-schema.json';

const ajv = new Ajv();
addFormats(ajv);

const validateExport = ajv.compile(exportSchema);

function isValidExport(data: unknown): data is ExportedData {
  const valid = validateExport(data);
  if (!valid) {
    console.error('Validation errors:', validateExport.errors);
  }
  return valid;
}

// Usage
const exportData = generateExportData();
if (isValidExport(exportData)) {
  downloadJSON(exportData);
} else {
  alert('Failed to generate valid export data');
}
```

### Testing

```typescript
import { describe, it, expect } from 'vitest';

describe('Export Data Validation', () => {
  it('validates correct export data', () => {
    const validData: ExportedData = {
      sessionId: '550e8400-e29b-41d4-a716-446655440000',
      exportTimestamp: '2025-11-06T13:00:00.000Z',
      selectedChatbotId: 'bot1',
      chatbots: [
        {
          chatId: 'bot1',
          displayName: 'GPT-4',
          messages: []
        }
      ],
      metadata: {
        exportVersion: '1.0.0',
        sessionCreatedAt: '2025-11-06T12:00:00.000Z',
        sessionUpdatedAt: '2025-11-06T12:30:00.000Z',
        totalMessages: 0
      }
    };

    expect(isValidExport(validData)).toBe(true);
  });

  it('rejects invalid sessionId format', () => {
    const invalidData = {
      sessionId: 'not-a-uuid',
      // ... rest of data
    };

    expect(isValidExport(invalidData)).toBe(false);
  });
});
```

---

## LocalStorage Quota Management

### Browser Limits

| Browser | LocalStorage Quota |
|---------|-------------------|
| Chrome | 10 MB |
| Firefox | 10 MB |
| Safari | 5 MB |
| Edge | 10 MB |

### Quota Monitoring

```typescript
function checkStorageQuota(): {
  used: number;
  available: number;
  percentage: number;
} {
  let total = 0;
  for (const key in localStorage) {
    if (localStorage.hasOwnProperty(key)) {
      total += localStorage[key].length + key.length;
    }
  }

  const usedBytes = total * 2; // UTF-16 encoding
  const availableBytes = 5 * 1024 * 1024; // 5MB (conservative estimate)

  return {
    used: usedBytes,
    available: availableBytes,
    percentage: (usedBytes / availableBytes) * 100
  };
}

// Warn user if storage is >75% full
const quota = checkStorageQuota();
if (quota.percentage > 75) {
  alert(`Storage is ${quota.percentage.toFixed(1)}% full. Please export data soon.`);
}
```

### Quota Error Handling

```typescript
function saveSession(session: ComparisonSession): boolean {
  try {
    const key = `comparison_session_${session.sessionId}`;
    const data = JSON.stringify(session);
    localStorage.setItem(key, data);
    return true;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'QuotaExceededError') {
      console.error('LocalStorage quota exceeded');

      // Fallback: Trim message history
      const trimmedSession = {
        ...session,
        chatbots: session.chatbots.map(bot => ({
          ...bot,
          messages: bot.messages.slice(-50) // Keep last 50 messages only
        }))
      };

      try {
        const key = `comparison_session_${session.sessionId}`;
        localStorage.setItem(key, JSON.stringify(trimmedSession));
        alert('Storage full: message history trimmed to last 50 messages per chatbot');
        return true;
      } catch {
        alert('Failed to save data: storage quota exceeded. Please export and clear data.');
        return false;
      }
    }

    throw err; // Re-throw other errors
  }
}
```

---

## Best Practices

### Data Integrity

✅ **Do**:
- Validate all data on read from localStorage
- Generate UUIDs for session and message IDs using `crypto.randomUUID()`
- Use ISO 8601 timestamps (`new Date().toISOString()`)
- Handle JSON parsing errors gracefully
- Backup data before schema migrations

❌ **Don't**:
- Store sensitive information (passwords, API keys) in localStorage
- Assume localStorage is always available (use fallback to in-memory state)
- Store binary data directly (use Base64 encoding if necessary)
- Rely on localStorage for critical data (encourage regular exports)

### Performance

✅ **Do**:
- Debounce localStorage writes (500ms recommended)
- Limit message history to 200 per chatbot
- Use shallow comparison for state updates
- Compress data if needed (LZ-string library)

❌ **Don't**:
- Write to localStorage on every keystroke
- Store redundant or computed data
- Perform synchronous operations during render

### Security

✅ **Do**:
- Sanitize user input before storing (prevent XSS)
- Validate data structure on read (prevent injection attacks)
- Use Content Security Policy headers
- Export data only when explicitly requested

❌ **Don't**:
- Store authentication tokens in localStorage
- Trust data from localStorage without validation
- Execute code from localStorage values
- Share localStorage between multiple origins

---

## Tools & Resources

### Validation Tools
- **ajv** - JSON Schema validator for JavaScript
- **ajv-cli** - Command-line JSON Schema validation
- **ajv-formats** - Additional format validators (date-time, uri, email)

### Development Tools
- **json-schema-to-typescript** - Generate TypeScript types from schemas
- **quicktype** - Generate types from JSON examples
- **JSON Schema Lint** - Online schema validator

### Testing
- **Vitest** - Fast unit testing for TypeScript
- **json-schema-faker** - Generate fake data from schemas for testing

### Documentation
- [JSON Schema Documentation](https://json-schema.org/)
- [MDN: Window.localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [MDN: Blob API](https://developer.mozilla.org/en-US/docs/Web/API/Blob)

---

## Future Enhancements

### Potential Schema Extensions (v2.0.0+)

1. **Message Reactions**: Add user reactions/ratings to individual messages
   ```typescript
   interface Message {
     // ... existing fields
     reactions?: {
       helpful: boolean;
       accurate: boolean;
       creative: boolean;
     };
   }
   ```

2. **Session Tags**: Allow categorizing sessions with tags
   ```typescript
   interface ComparisonSession {
     // ... existing fields
     tags?: string[];
   }
   ```

3. **Multi-Turn Comparisons**: Support comparing chatbot responses across multiple conversation turns
   ```typescript
   interface PreferenceSelection {
     // ... existing fields
     perMessagePreferences?: {
       messageId: string;
       selectedChatbotId: string;
     }[];
   }
   ```

4. **Offline Support**: IndexedDB fallback for larger datasets
5. **Cloud Sync**: Optional cloud backup via API (requires backend)

---

## Contact

For schema-related questions or proposals for schema changes, please open an issue or submit a pull request with:

1. **Proposed schema change** (JSON diff)
2. **Migration strategy** (backward compatibility plan)
3. **Rationale** (why the change is needed)
4. **Impact assessment** (affected components, breaking changes)
