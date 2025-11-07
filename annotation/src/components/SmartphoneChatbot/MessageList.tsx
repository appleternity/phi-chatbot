import React, { useEffect, useRef } from 'react';
import { useInView } from 'react-intersection-observer';
import { Message } from '../../types/chatbot';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';

interface MessageListProps {
  messages: Message[];
  isTyping: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isTyping }) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { ref: anchorRef, inView } = useInView({
    threshold: 0,
    rootMargin: '100px',
  });

  useEffect(() => {
    // Only auto-scroll if user is already viewing the bottom
    if (inView && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isTyping, inView]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isTyping && <TypingIndicator />}
      <div ref={anchorRef} />
      <div ref={bottomRef} />
    </div>
  );
};
