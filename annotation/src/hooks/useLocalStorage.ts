import { useEffect } from 'react';
import { Message } from '../types/chatbot';
import { storageService } from '../services/storageService';

export function useLocalStorage(
  chatId: string,
  messages: Message[],
  sessionId: string
) {
  useEffect(() => {
    // Load from localStorage on mount
    const session = storageService.loadSession(sessionId);
    if (session) {
      const chatbot = session.chatbots.find(c => c.chatId === chatId);
      if (chatbot) {
        // Messages are already loaded in parent component
        return;
      }
    }
  }, [chatId, sessionId]);

  useEffect(() => {
    // Save to localStorage when messages change (debounced in storageService)
    const session = storageService.loadSession(sessionId);
    if (session) {
      const chatbotIndex = session.chatbots.findIndex(c => c.chatId === chatId);
      if (chatbotIndex !== -1) {
        session.chatbots[chatbotIndex].messages = messages;
        session.metadata.updatedAt = new Date().toISOString();
        storageService.saveSession(session);
      }
    }
  }, [messages, chatId, sessionId]);
}
