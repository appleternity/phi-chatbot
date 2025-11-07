import { debounce } from 'lodash';
import { ComparisonSession } from '../types/session';
import { checkStorageQuota, showQuotaWarning } from '../utils/storageMonitor';

const STORAGE_KEY_PREFIX = 'comparison_session_';
const CURRENT_SESSION_KEY = 'current_session_id';

/**
 * LocalStorage service for persisting comparison session data
 */
export const storageService = {
  /**
   * Save session to localStorage with debounced writes
   * Debounced to 500ms to prevent excessive localStorage operations
   */
  saveSession: debounce((session: ComparisonSession) => {
    try {
      // Check quota before saving and show warning if needed
      const quota = checkStorageQuota();
      if (quota.warningNeeded) {
        showQuotaWarning();
      }

      const key = `${STORAGE_KEY_PREFIX}${session.sessionId}`;
      localStorage.setItem(key, JSON.stringify(session));
      localStorage.setItem(CURRENT_SESSION_KEY, session.sessionId);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'QuotaExceededError') {
        console.error('LocalStorage quota exceeded');
        alert(
          '❌ 儲存空間已滿！\n\n' +
          '請匯出資料並清除舊對話。'
        );
      } else {
        console.error('Failed to save session:', error);
      }
      throw error;
    }
  }, 500),

  /**
   * Load session from localStorage by session ID
   * @param sessionId - UUID of the session to load
   * @returns ComparisonSession or null if not found
   */
  loadSession(sessionId: string): ComparisonSession | null {
    try {
      const key = `${STORAGE_KEY_PREFIX}${sessionId}`;
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Failed to load session:', error);
      return null;
    }
  },

  /**
   * Get the current session ID from localStorage
   * @returns Current session ID or null if none exists
   */
  getCurrentSessionId(): string | null {
    return localStorage.getItem(CURRENT_SESSION_KEY);
  },

  /**
   * Clear all data from localStorage
   * Used for "New Comparison" workflow
   */
  clearAllData(): void {
    localStorage.clear();
  },

  /**
   * Initialize a new session with empty chatbot instances
   * @returns New session ID (UUID v4)
   */
  initializeNewSession(): string {
    const newSessionId = crypto.randomUUID();
    const session: ComparisonSession = {
      sessionId: newSessionId,
      chatbots: [
        {
          chatId: 'bot1',
          displayName: 'GPT-4',
          messages: [],
          state: 'idle',
        },
        {
          chatId: 'bot2',
          displayName: 'Claude',
          messages: [],
          state: 'idle',
        },
        {
          chatId: 'bot3',
          displayName: 'Gemini',
          messages: [],
          state: 'idle',
        },
      ],
      selection: {
        selectedChatbotId: null,
        timestamp: new Date().toISOString(),
      },
      metadata: {
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        version: '1.0.0',
      },
    };

    this.saveSession(session);
    return newSessionId;
  },
};
