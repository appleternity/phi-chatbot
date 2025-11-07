import { ChatbotInstance } from './chatbot';

/**
 * PreferenceSelection representing user's choice of preferred chatbot
 */
export interface PreferenceSelection {
  /** ID of the selected chatbot (or null if not selected) */
  selectedChatbotId: string | null;

  /** When the selection was made (ISO 8601 timestamp) */
  timestamp: string;

  /** Optional notes or reasoning (future enhancement) */
  notes?: string;
}

/**
 * ComparisonSession representing one complete annotation task stored in localStorage
 */
export interface ComparisonSession {
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
