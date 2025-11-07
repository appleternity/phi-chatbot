import React, { useState, useEffect } from 'react';
import { SmartphoneChatbot } from '../SmartphoneChatbot';
import { ExportButton } from '../ExportButton';
import { NewSessionButton } from '../NewSessionButton';
import { storageService } from '../../services/storageService';

interface ComparisonLayoutProps {
  sessionId: string;
}

export const ComparisonLayout: React.FC<ComparisonLayoutProps> = ({ sessionId: initialSessionId }) => {
  const [currentSessionId, setCurrentSessionId] = useState(initialSessionId);
  const [selectedChatbotId, setSelectedChatbotId] = useState<string | null>(null);

  // Load selection from localStorage
  useEffect(() => {
    const session = storageService.loadSession(currentSessionId);
    if (session?.selection.selectedChatbotId) {
      setSelectedChatbotId(session.selection.selectedChatbotId);
    }
  }, [currentSessionId]);

  // Save selection to localStorage
  useEffect(() => {
    const session = storageService.loadSession(currentSessionId);
    if (session) {
      session.selection = {
        selectedChatbotId,
        timestamp: new Date().toISOString(),
      };
      session.metadata.updatedAt = new Date().toISOString();
      storageService.saveSession(session);
    }
  }, [selectedChatbotId, currentSessionId]);

  const handleSelect = (chatId: string) => {
    setSelectedChatbotId(chatId === selectedChatbotId ? null : chatId);
  };

  const chatbots = [
    { chatId: 'bot1', displayName: 'GPT-4', avatar: undefined },
    { chatId: 'bot2', displayName: 'Claude', avatar: undefined },
    { chatId: 'bot3', displayName: 'Gemini', avatar: undefined },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold text-center mb-8 text-gray-900">
        Chatbot Annotation Interface
      </h1>

      {/* Export Button */}
      <ExportButton sessionId={currentSessionId} />

      <div className="flex gap-6 justify-center items-start overflow-x-auto pb-4">
        {chatbots.map((bot) => (
          <div
            key={bot.chatId}
            className={`relative transition-all ${
              selectedChatbotId === bot.chatId
                ? 'ring-4 ring-green-500 ring-offset-4 rounded-lg'
                : ''
            }`}
          >
            <SmartphoneChatbot
              chatId={bot.chatId}
              displayName={bot.displayName}
              avatar={bot.avatar}
              sessionId={currentSessionId}
            />

            {/* Selection Button */}
            <button
              onClick={() => handleSelect(bot.chatId)}
              className={`absolute -bottom-12 left-1/2 transform -translate-x-1/2 px-6 py-2 rounded-full font-medium transition-all ${
                selectedChatbotId === bot.chatId
                  ? 'bg-green-500 text-white hover:bg-green-600'
                  : 'bg-white text-gray-700 border-2 border-gray-300 hover:border-green-500 hover:text-green-600'
              }`}
            >
              {selectedChatbotId === bot.chatId ? (
                <>✓ Selected</>
              ) : (
                <>Select as Preferred</>
              )}
            </button>

            {/* Checkmark Badge */}
            {selectedChatbotId === bot.chatId && (
              <div className="absolute -top-3 -right-3 bg-green-500 text-white rounded-full w-10 h-10 flex items-center justify-center text-xl font-bold shadow-lg">
                ✓
              </div>
            )}
          </div>
        ))}
      </div>

      {/* New Session Button */}
      <NewSessionButton onNewSession={setCurrentSessionId} />
    </div>
  );
};
