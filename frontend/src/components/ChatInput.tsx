import { useState, KeyboardEvent } from 'react'
import { Send, Square } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
  isLoading?: boolean  // For non-streaming requests
}

export default function ChatInput({ onSend, onStop, isStreaming, isLoading = false }: ChatInputProps) {
  const [input, setInput] = useState('')

  // Disable input during both streaming and non-streaming loading
  const isDisabled = isStreaming || isLoading

  const handleSend = () => {
    if (input.trim() && !isDisabled) {
      onSend(input)
      setInput('')
    }
  }

  const handleStop = () => {
    onStop()
  }

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isDisabled) {
        handleSend()
      }
    }
  }

  return (
    <div className="border-t-2 border-gray-200 p-6 bg-white">
      <div className="flex gap-3">
        {/* Disable text input during streaming or non-streaming loading */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message... (e.g., 'I'm feeling anxious' or 'What is Sertraline?')"
          disabled={isDisabled}
          className="flex-1 px-5 py-3 border-2 border-gray-300 rounded-full focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        />
        {/* Show stop button during streaming, send button otherwise */}
        {isStreaming ? (
          <button
            onClick={handleStop}
            className="px-6 py-3 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-full hover:shadow-lg transition-all duration-200 hover:scale-105 flex items-center gap-2 font-medium"
          >
            <span>Stop</span>
            <Square size={18} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-6 py-3 bg-gradient-to-r from-primary-500 to-secondary-500 text-white rounded-full hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 hover:scale-105 flex items-center gap-2 font-medium"
          >
            <span>{isLoading ? 'Loading...' : 'Send'}</span>
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  )
}
