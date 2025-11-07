import { useState, useCallback } from 'react';
import { Message } from '../types/chatbot';
import { generateMessageId, getCurrentTimestamp } from '../utils/timestamp';
import { sendMessage as sendMessageAPI } from '../services/chatbotService';

export function useChatbot(chatId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    // Add user message
    const userMessage: Message = {
      id: generateMessageId(),
      content,
      sender: 'user',
      timestamp: getCurrentTimestamp(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);
    setError(null);

    try {
      // Get bot response
      const response = await sendMessageAPI(chatId, content);

      const botMessage: Message = {
        id: generateMessageId(),
        content: response,
        sender: 'bot',
        timestamp: getCurrentTimestamp(),
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      console.error('Failed to send message:', err);
    } finally {
      setIsTyping(false);
    }
  }, [chatId]);

  return {
    messages,
    isTyping,
    error,
    sendMessage,
  };
}
