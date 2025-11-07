import { Message, ChatbotInstance } from '../types/chatbot';
import { ComparisonSession } from '../types/session';

/**
 * Type guard for Message validation
 */
export function isValidMessage(msg: unknown): msg is Message {
  if (typeof msg !== 'object' || msg === null) return false;
  const m = msg as Message;

  return (
    typeof m.id === 'string' &&
    typeof m.content === 'string' &&
    m.content.length > 0 &&
    (m.sender === 'user' || m.sender === 'bot') &&
    typeof m.timestamp === 'string' &&
    !isNaN(Date.parse(m.timestamp))
  );
}

/**
 * Type guard for ChatbotInstance validation
 */
export function isValidChatbotInstance(bot: unknown): bot is ChatbotInstance {
  if (typeof bot !== 'object' || bot === null) return false;
  const b = bot as ChatbotInstance;

  return (
    typeof b.chatId === 'string' &&
    typeof b.displayName === 'string' &&
    b.displayName.length > 0 &&
    Array.isArray(b.messages) &&
    b.messages.every(isValidMessage) &&
    ['idle', 'typing', 'responded', 'error'].includes(b.state)
  );
}

/**
 * Type guard for ComparisonSession validation
 */
export function isValidComparisonSession(session: unknown): session is ComparisonSession {
  if (typeof session !== 'object' || session === null) return false;
  const s = session as ComparisonSession;

  return (
    typeof s.sessionId === 'string' &&
    Array.isArray(s.chatbots) &&
    s.chatbots.length >= 2 &&
    s.chatbots.length <= 4 &&
    s.chatbots.every(isValidChatbotInstance)
  );
}
