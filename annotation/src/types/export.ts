import { Message } from './chatbot';

/**
 * ExportedData representing the JSON file structure for data export
 */
export interface ExportedData {
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
    config?: Record<string, unknown>;
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
