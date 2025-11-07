import React from 'react';
import { Message } from '../../types/chatbot';
import { formatTimestamp } from '../../utils/timestamp';

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble = React.memo<MessageBubbleProps>(({ message }) => {
  const isUser = message.sender === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[75%] rounded-[18px] px-4 py-2 ${
          isUser
            ? 'bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white'
            : 'bg-gray-200 text-gray-900'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
        <p className={`text-xs mt-1 ${isUser ? 'text-gray-100' : 'text-gray-500'}`}>
          {formatTimestamp(message.timestamp)}
        </p>
      </div>
    </div>
  );
});

MessageBubble.displayName = 'MessageBubble';
