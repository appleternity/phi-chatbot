import { useState } from 'react';
import { BotProfile, ChatMessage } from '../types/chat';
import ChatWindow from '../components/ChatWindow';
import BotSelector from '../components/BotSelector';
import { fetchBotResponse } from '../services/chatService';

const BOTS: BotProfile[] = [
  { id: 'bot_1', name: 'Amy', avatarColor: 'bg-blue-500', description: 'Just here to chat and be supportive!', welcomeMessage: 'Hello! I am Amy. How can I assist you today?' },
  { id: 'bot_2', name: 'Bob', avatarColor: 'bg-green-500', description: "I'm parent's best friend!", welcomeMessage: "Hey there! I'm Bob. What's on your mind?" },
  { id: 'bot_3', name: 'Cathy', avatarColor: 'bg-indigo-500', description: "Specialized in children's mental health.", welcomeMessage: "Hello! I'm Cathy. What would you like to talk about today?" },
];

function createInitialHistories(): Record<string, ChatMessage[]> {
  const result: Record<string, ChatMessage[]> = {};
  BOTS.forEach(bot => {
    result[bot.id] = [{
      id: crypto.randomUUID(),
      sender: 'bot',
      text: bot.welcomeMessage,
      rating: null,
      comment: null,
    }];
  });
  return result;
}

export default function ChatPage() {
  const [activeBotId, setActiveBotId] = useState(BOTS[0].id);
  const [chatHistories, setChatHistories] = useState(createInitialHistories());
  const [isBotLoading, setIsBotLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [userId] = useState(() => crypto.randomUUID());

  const activeBot = BOTS.find(b => b.id === activeBotId)!;
  const activeHistory = chatHistories[activeBotId];

  const handleSendMessage = async (text: string) => {
    const newUserMessage: ChatMessage = { id: crypto.randomUUID(), sender: 'user', text };
    setChatHistories(prev => ({
      ...prev,
      [activeBotId]: [...prev[activeBotId], newUserMessage],
    }));

    setIsBotLoading(true);
    const botReply = await fetchBotResponse(text, activeBot.id, userId);
    const newBotMessage: ChatMessage = {
      id: crypto.randomUUID(),
      sender: 'bot',
      text: botReply,
      rating: null,
      comment: null,
    };

    setChatHistories(prev => ({
      ...prev,
      [activeBotId]: [...prev[activeBotId], newBotMessage],
    }));
    setIsBotLoading(false);
  };

  const handleRateMessage = (id: string, rating: 'up' | 'down') => {
    setChatHistories(prev => {
      const updated = prev[activeBotId].map(msg => ({
        ...msg,
        rating: msg.id === id ? (msg.rating === rating ? null : rating) : msg.rating,
      }));
      return { ...prev, [activeBotId]: updated };
    });
  };

  const handleSubmitComment = (id: string, comment: string) => {
    setChatHistories(prev => {
      const updated = prev[activeBotId].map(msg =>
        msg.id === id ? { ...msg, comment: comment.trim() || null } : msg
      );
      return { ...prev, [activeBotId]: updated };
    });
  };

  return (
    <div className="flex h-screen text-gray-800">
      <div className={`${isChatOpen ? 'hidden' : 'flex w-full'} md:flex md:w-80`}>
        <BotSelector bots={BOTS} activeBotId={activeBotId} onSelectBot={(id) => { setActiveBotId(id); setIsChatOpen(true); }} />
      </div>

      <div className={`${!isChatOpen ? 'hidden' : 'flex'} flex-1 flex-col md:flex`}>
        <ChatWindow
          bot={activeBot}
          history={activeHistory}
          onSendMessage={handleSendMessage}
          isLoading={isBotLoading}
          onReturn={() => setIsChatOpen(false)}
          onRateMessage={handleRateMessage}
          onSubmitComment={handleSubmitComment}
        />
      </div>
    </div>
  );
}
