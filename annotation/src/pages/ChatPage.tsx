import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BotProfile, ChatMessage } from '../types/chat';
import ChatWindow from '../components/ChatWindow';
import BotSelector from '../components/BotSelector';
import { fetchBotResponse, fetchBotStreamResponse, sendFeedback, getChatHistory } from '../services/chatService';
import { getToken, logout } from "../services/authService";
import { fetchBots, createInitialHistories } from '../services/botService';


export default function ChatPage() {
  const [bots, setBots] = useState<BotProfile[]>([]);
  const [activeBotId, setActiveBotId] = useState<string | null>(null);
  const [chatHistories, setChatHistories] = useState<Record<string, ChatMessage[]>>({});
  const [isBotLoading, setIsBotLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchBots().then((data) => {
      if (data.bots && data.bots.length > 0) {
        setBots(data.bots);
        setActiveBotId(data.bots[0]?.id || null);
        setChatHistories(createInitialHistories(data.bots));
      } else {
        console.error("No bots found.");
      }
    }).catch((error) => {
      console.error("Failed to fetch bots:", error);
    });
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    // Load chat history for this user
    getChatHistory()
      .then((messages) => {
        if (!messages || messages.length === 0) {
          console.log("No previous history for this user.");
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

  const activeBot = bots.find(b => b.id === activeBotId) || bots[0];
  const activeHistory = chatHistories[activeBotId || ""] || [];

  const handleSendMessage = async (text: string) => {
    const newUserMessage: ChatMessage = { id: crypto.randomUUID(), sender: 'user', text };
    setChatHistories(prev => ({
      ...prev,
      [activeBotId!]: [...prev[activeBotId!], newUserMessage],
    }));

    setIsBotLoading(true);
    // const controllerRef = { current: undefined as AbortController | undefined };

    // cancel previous ongoing stream (if any)
    // if (controllerRef.current) controllerRef.current.abort();

    const newControllerRef = { current: undefined as AbortController | undefined };
    // controllerRef.current = newControllerRef.current;
    let isFirstChunk = true;

    try {
      await fetchBotStreamResponse(
        text,
        activeBotId!,
        async (chunk, messageId) => {
          const trimmed = chunk.trim();
          if (!trimmed) return;

          if (!isFirstChunk) {
            await new Promise(res => setTimeout(res, 3000));
          } else {
            isFirstChunk = false;
          }

          const newBubble: ChatMessage = {
            id: messageId,
            sender: 'bot',
            text: trimmed,
            rating: null,
            comment: null,
          };
          setChatHistories(prev => ({
            ...prev,
            [activeBotId!]: [...prev[activeBotId!], newBubble],
          }));
        },
        newControllerRef
      );

    } catch (err) {
      console.error("Streaming error:", err);
    } finally {
      setIsBotLoading(false);
    }
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

  const handleLogout = () => {
    logout();
    window.dispatchEvent(new Event('storage'));
    navigate("/login");
  };

  if (bots.length === 0) {
    return <div className="flex h-screen items-center justify-center">Loading bots...</div>;
  }
  return (
    <div className="flex h-screen text-gray-800">
      <div className={`${isChatOpen ? 'hidden' : 'flex w-full'} md:flex md:w-80 flex-col`}>
        <div className="flex-1 overflow-auto">
          <BotSelector bots={bots} activeBotId={activeBotId} onSelectBot={(id) => { setActiveBotId(id); setIsChatOpen(true); }} />
        </div>
        <div className="border-t p-4">
          <button
            onClick={handleLogout}
            className="w-full bg-red-600 text-white py-2 rounded-md hover:bg-red-700 transition"
          >
            Logout
          </button>
        </div>
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
