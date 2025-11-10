import { useEffect, useState } from "react";
import { BotProfile, ChatMessage } from '../types/chat';
import ChatWindow from '../components/ChatWindow';
import BotSelector from '../components/BotSelector';
import { fetchBotResponse, sendFeedback, getChatHistory } from '../services/chatService';
import { getToken } from "../services/authService";


const BOTS: BotProfile[] = [
  { id: 'bot_1', name: '欣宁', avatarColor: 'bg-blue-500', description: '专业咨询版', 
    welcomeMessage: '您好，我是欣宁 🙂\n我可以陪您一起探讨孩子的情绪变化、沟通方式，或您自己在育儿中的压力。\n请放心表达，我会尽力以温和、专业的方式倾听和回应。' },
  { id: 'bot_2', name: '小安', avatarColor: 'bg-green-500', description: '温暖陪伴版', 
    welcomeMessage: '你好呀～我是小安😊\n有时候孩子的情绪、学习、沟通真的挺让人头疼的。\n你可以跟我聊聊最近让你最烦心或最担心的事，我们一起来想办法！'},
  { id: 'bot_3', name: '亲子心桥', avatarColor: 'bg-indigo-500', description: "科学育儿，用“心”沟通，帮您和孩子走得更近。", 
    welcomeMessage: '您好，很高兴能和您聊聊。作为家长，关心孩子的情绪和成长真的非常不容易。\n\n您可以把我当作一个安全、不带评判的“树洞”，和我聊聊您的困惑和担忧。我也会尽力为您提供一些科学的心理健康科普、实用的沟通技巧和初步的应对建议。\n\n您今天想从哪里开始聊起呢？' },
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

  useEffect(() => {
  const token = getToken();
  if (!token) return;

  // Load chat history for this user
  getChatHistory()
    .then((messages) => {
      if (!messages || messages.length === 0) {
        console.log("No previous history for this user.");
        // setChatHistories(createInitialHistories()); // or leave as empty
        return;
      }
      const historiesByBot: Record<string, ChatMessage[]> = {};
      messages.forEach((msg: any) => {
        if (!historiesByBot[msg.bot_id]) historiesByBot[msg.bot_id] = [];
        historiesByBot[msg.bot_id].push({
          id: msg.id,
          sender: msg.sender,
          text: msg.text,
          rating: msg.rating,
          comment: msg.comment,
        });
      });
      setChatHistories((prev) => ({ ...prev, ...historiesByBot }));
    })
    .catch((err) => console.error("Failed to load history:", err));
  }, []);
  

  const activeBot = BOTS.find(b => b.id === activeBotId)!;
  const activeHistory = chatHistories[activeBotId];

  const handleSendMessage = async (text: string) => {
    const newUserMessage: ChatMessage = { id: crypto.randomUUID(), sender: 'user', text };
    setChatHistories(prev => ({
      ...prev,
      [activeBotId]: [...prev[activeBotId], newUserMessage],
    }));

    setIsBotLoading(true);
    const { text: botReply, message_id } = await fetchBotResponse(text, activeBot.id);
    const newBotMessage: ChatMessage = {
      id: message_id,
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

    const targetMsg = chatHistories[activeBotId].find(m => m.id === id);
    const finalRating = targetMsg?.rating === rating ? null : rating; // toggle logic
    sendFeedback({
        message_id: id,
        bot_id: activeBotId,
        rating: finalRating,
        comment: targetMsg?.comment || null,
    });
  };

  const handleSubmitComment = (id: string, comment: string) => {
    setChatHistories(prev => {
      const updated = prev[activeBotId].map(msg =>
        msg.id === id ? { ...msg, comment: comment.trim() || null } : msg
      );
      return { ...prev, [activeBotId]: updated };
    });
    const targetMsg = chatHistories[activeBotId].find(m => m.id === id);
    sendFeedback({
        message_id: id,
        bot_id: activeBotId,
        rating: targetMsg?.rating || null,
        comment: comment.trim() || null,
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
