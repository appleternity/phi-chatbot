import type { Message } from '../types'

interface ChatMessageProps {
  message: Message
}

const agentInfo: Record<string, { name: string; icon: string; color: string }> = {
  emotional_support: {
    name: 'Emotional Support',
    icon: '💬',
    color: 'text-blue-600',
  },
  rag_agent: {
    name: 'Medical Information',
    icon: '📚',
    color: 'text-purple-600',
  },
  supervisor: {
    name: 'Supervisor',
    icon: '🎯',
    color: 'text-gray-600',
  },
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'
  const agent = message.agent ? agentInfo[message.agent] : null

  if (isError) {
    return (
      <div className="flex justify-center mb-4">
        <div className="max-w-[90%] bg-red-50 border-2 border-red-200 rounded-xl px-5 py-3 text-center">
          <p className="text-sm text-red-600">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[75%] ${isUser ? 'order-last' : 'order-first'}`}>
        {agent && (
          <div className="flex items-center gap-2 mb-1 px-1">
            <span className="text-xs">{agent.icon}</span>
            <span className={`text-xs font-semibold uppercase tracking-wide ${agent.color}`}>
              {agent.name}
            </span>
          </div>
        )}
        <div
          className={`rounded-2xl px-5 py-3 ${
            isUser
              ? 'bg-gradient-to-br from-primary-500 to-secondary-500 text-white shadow-lg'
              : 'bg-white text-gray-800 shadow-md border border-gray-200'
          }`}
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>
      </div>
    </div>
  )
}
