import React from 'react';
import { ChatHeader } from './ChatHeader';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useChatbot } from '../../hooks/useChatbot';
import { useLocalStorage } from '../../hooks/useLocalStorage';

interface SmartphoneChatbotProps {
  chatId: string;
  displayName: string;
  avatar?: string;
  sessionId: string;
}

export const SmartphoneChatbot: React.FC<SmartphoneChatbotProps> = ({
  chatId,
  displayName,
  avatar,
  sessionId,
}) => {
  const { messages, isTyping, error, sendMessage } = useChatbot(chatId);
  useLocalStorage(chatId, messages, sessionId);

  return (
    <div className="flex flex-col max-w-[414px] min-h-[667px] bg-white rounded-lg shadow-lg overflow-hidden border border-gray-200">
      <ChatHeader displayName={displayName} avatar={avatar} />
      <MessageList messages={messages} isTyping={isTyping} />
      {error && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-200 text-red-600 text-sm">
          Error: {error}
        </div>
      )}
      <MessageInput onSendMessage={sendMessage} disabled={isTyping} />
    </div>
  );
};
