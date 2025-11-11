import { useEffect, useRef, useState } from 'react';
import { Bot, User, SendHorizontal, ArrowLeft, ThumbsUp, ThumbsDown, Edit, X } from 'lucide-react';
import { ChatMessage, BotProfile } from '../types/chat';

interface ChatWindowProps {
  bot: BotProfile;
  history: ChatMessage[];
  onSendMessage: (text: string) => void;
  isLoading: boolean;
  onReturn: () => void;
  onRateMessage: (id: string, rating: 'up' | 'down') => void;
  onSubmitComment: (id: string, comment: string) => void;
}

export default function ChatWindow({
  bot,
  history,
  onSendMessage,
  isLoading,
  onReturn,
  onRateMessage,
  onSubmitComment,
}: ChatWindowProps) {
  const [message, setMessage] = useState('');
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  const [currentCommentText, setCurrentCommentText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim()) {
      onSendMessage(message);
      setMessage('');
    }
  };

  const handleSaveComment = () => {
    if (editingCommentId) {
      onSubmitComment(editingCommentId, currentCommentText);
      setEditingCommentId(null);
      setCurrentCommentText('');
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="flex items-center p-4 border-b bg-white shadow-sm">
        <button
          onClick={onReturn}
          className="mr-2 p-2 rounded-full hover:bg-gray-100 md:hidden"
          aria-label="Back"
        >
          <ArrowLeft size={20} className="text-gray-600" />
        </button>
        <div
          className={`w-10 h-10 rounded-full ${bot.avatarColor} flex items-center justify-center text-white mr-3`}
        >
          <Bot size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{bot.name}</h2>
          <p className="text-sm text-gray-500">{bot.description}</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 p-6 space-y-4 overflow-y-auto">  {/* whitespace-pre-wrap */}
        {history.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.sender === 'bot' && (
                <div
                  className={`w-8 h-8 rounded-full ${bot.avatarColor} flex items-center justify-center text-white mr-2 flex-shrink-0`}
                >
                  <Bot size={16} />
                </div>
              )}
              <div
                className={`p-3 rounded-lg max-w-xs md:max-w-md lg:max-w-lg shadow-sm ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-800 border'
                }`}
              >
                {msg.text}
              </div>
              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 ml-2 flex-shrink-0">
                  <User size={16} />
                </div>
              )}
            </div>

            {/* Feedback & Comments */}
            {msg.sender === 'bot' && (
              <div className="flex items-center space-x-1 mt-1 ml-10">
                <button
                  onClick={() => onRateMessage(msg.id, 'up')}
                  className={`p-1 rounded-full ${msg.rating === 'up' ? 'text-green-600 bg-green-100' : 'text-gray-400 hover:text-green-600 hover:bg-gray-100'}`}
                >
                  <ThumbsUp size={16} fill={msg.rating === 'up' ? 'currentColor' : 'none'} />
                </button>
                <button
                  onClick={() => onRateMessage(msg.id, 'down')}
                  className={`p-1 rounded-full ${msg.rating === 'down' ? 'text-red-600 bg-red-100' : 'text-gray-400 hover:text-red-600 hover:bg-gray-100'}`}
                >
                  <ThumbsDown size={16} fill={msg.rating === 'down' ? 'currentColor' : 'none'} />
                </button>
                <button
                  onClick={() => {
                    setEditingCommentId(msg.id);
                    setCurrentCommentText(msg.comment || '');
                  }}
                  className={`p-1 rounded-full flex items-center text-xs ml-2 ${
                    msg.comment ? 'text-blue-600 bg-blue-100' : 'text-gray-400 hover:bg-gray-200'
                  }`}
                >
                  <Edit size={16} className="mr-1" />
                </button>
              </div>
            )}

            {/* Display existing comment */}
            {msg.comment && editingCommentId !== msg.id && (
                <div className={`mt-2 p-2 rounded-lg text-xs max-w-lg shadow-sm border ml-10 bg-gray-100 text-gray-700 border-gray-200}`}>
                    <p className="font-semibold mb-1">Feedback:</p>
                    <p className="text-gray-800 italic">{msg.comment}</p>
                </div>
            )}

            {editingCommentId === msg.id && (
              <div className="mt-2 ml-10 bg-white border border-gray-300 p-3 rounded-lg w-80 max-w-lg">
                <textarea
                  value={currentCommentText}
                  onChange={(e) => setCurrentCommentText(e.target.value)}
                  placeholder="Add your comment..."
                  className="w-full border border-gray-200 rounded-md p-2 text-sm"
                />
                <div className="flex justify-end space-x-2 mt-2">
                  <button onClick={() => setEditingCommentId(null)} className="flex items-center text-gray-600">
                    <X size={16} className="mr-1" /> Cancel
                  </button>
                  <button
                    onClick={handleSaveComment}
                    className="bg-blue-600 text-white px-3 py-1 rounded-md hover:bg-blue-700"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center text-gray-500">
            <div className={`w-8 h-8 rounded-full ${bot.avatarColor} flex items-center justify-center text-white mr-2`}>
              <Bot size={16} />
            </div>
            <div className="animate-pulse">...</div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white">
        <form onSubmit={handleSubmit} className="flex items-center space-x-3">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={`Message ${bot.name}...`}
            className="flex-1 border border-gray-300 rounded-full py-3 px-5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className="bg-blue-600 text-white rounded-full p-3 hover:bg-blue-700"
          >
            <SendHorizontal size={20} />
          </button>
        </form>
      </div>
    </div>
  );
}
