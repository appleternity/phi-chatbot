/**
 * Message entity representing a single message in a conversation
 */
export interface Message {
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

/**
 * ChatbotInstance representing one chatbot being compared
 */
export interface ChatbotInstance {
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

export type ChatbotState = ChatbotInstance['state'];
export type MessageSender = Message['sender'];
