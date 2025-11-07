import React from 'react';
import { ChatHeader } from '../components/SmartphoneChatbot/ChatHeader';
import { MessageList } from '../components/SmartphoneChatbot/MessageList';
import { MessageInput } from '../components/SmartphoneChatbot/MessageInput';
import { useChatbot } from '../hooks/useChatbot';
import { useLocalStorage } from '../hooks/useLocalStorage';

interface SingleChatPageProps {
  sessionId: string;
}

export const SingleChatPage: React.FC<SingleChatPageProps> = ({ sessionId }) => {
  const chatId = 'main-chat';
  const displayName = 'AI Assistant';
  const avatar = undefined;

  const { messages, isTyping, error, sendMessage } = useChatbot(chatId);
  useLocalStorage(chatId, messages, sessionId);

  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-50 p-0 sm:p-4">
      {/* Container with responsive width and height */}
      <div className="flex flex-col w-full sm:max-w-[600px] h-screen sm:h-[667px] bg-white sm:rounded-lg sm:shadow-lg overflow-hidden sm:border sm:border-gray-200">
        <ChatHeader displayName={displayName} avatar={avatar} />
        <MessageList messages={messages} isTyping={isTyping} />
        {error && (
          <div className="px-4 py-2 bg-red-50 border-t border-red-200 text-red-600 text-sm">
            Error: {error}
          </div>
        )}
        <MessageInput onSendMessage={sendMessage} disabled={isTyping} />
      </div>
    </div>
  );
};
