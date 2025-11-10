import { Bot, MessageSquare } from 'lucide-react';
import { BotProfile } from '../types/chat';

interface BotSelectorProps {
  bots: BotProfile[];
  activeBotId: string;
  onSelectBot: (id: string) => void;
}

export default function BotSelector({ bots, activeBotId, onSelectBot }: BotSelectorProps) {
  return (
    <div className="w-full md:w-80 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b">
        <h1 className="text-xl font-bold text-gray-900 flex items-center">
          <MessageSquare size={24} className="mr-2 text-blue-600" />
          ChatBots
        </h1>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {bots.map((bot) => (
          <button
            key={bot.id}
            onClick={() => onSelectBot(bot.id)}
            className={`w-full text-left p-3 rounded-lg flex items-center space-x-3 ${
              activeBotId === bot.id
                ? 'bg-blue-100 text-blue-700 font-semibold'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <div
              className={`w-8 h-8 rounded-full ${bot.avatarColor} flex items-center justify-center text-white flex-shrink-0`}
            >
              <Bot size={16} />
            </div>
            <div>
              <div className="text-sm">{bot.name}</div>
              {/* <p className="text-xs text-gray-500 truncate">{bot.description}</p> */}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
