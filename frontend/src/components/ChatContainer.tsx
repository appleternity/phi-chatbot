import { useState, useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import WelcomeMessage from './WelcomeMessage'
import { useStreamingChat } from '../hooks/useStreamingChat'
import type { Message } from '../types'

interface ChatContainerProps {
  sessionId: string
}

export default function ChatContainer({ sessionId }: ChatContainerProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // T021: Use streaming hook instead of direct API call
  const { tokens, isStreaming, error: streamError, streamMessage, stopStreaming } = useStreamingChat()

  // Load history from localStorage
  useEffect(() => {
    const savedHistory = localStorage.getItem('chat_history')
    if (savedHistory) {
      try {
        setMessages(JSON.parse(savedHistory))
      } catch (e) {
        console.error('Failed to load history:', e)
      }
    }
  }, [])

  // Save history to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('chat_history', JSON.stringify(messages))
    }
  }, [messages])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isStreaming) return

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMessage])

    // Start streaming (T021)
    await streamMessage(content, sessionId)
  }

  // T024: Add streaming tokens to messages when stream completes (T026: preserves session context)
  useEffect(() => {
    if (!isStreaming && tokens.length > 0) {
      // Stream completed - add assistant message with accumulated tokens
      const assistantMessage: Message = {
        role: 'assistant',
        content: tokens.join(''),
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    }
  }, [isStreaming, tokens])

  // Handle stream errors
  useEffect(() => {
    if (streamError) {
      const errorMessage: Message = {
        role: 'error',
        content: `Failed to get response: ${streamError}. Please try again.`,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, errorMessage])
    }
  }, [streamError])

  // Handle stop button click (T025)
  const handleStopStreaming = () => {
    stopStreaming()
  }

  return (
    <div className="flex-1 bg-white rounded-b-2xl shadow-lg flex flex-col overflow-hidden">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
        {messages.length === 0 && <WelcomeMessage />}
        {messages.map((message, index) => (
          <ChatMessage key={index} message={message} />
        ))}
        {/* T024: Progressive token rendering - show streaming tokens in real-time */}
        {isStreaming && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[75%] bg-white rounded-2xl px-5 py-3 shadow-md border border-gray-200">
              <div className="text-gray-800 whitespace-pre-wrap">
                {tokens.join('')}
                <span className="inline-block w-2 h-4 bg-primary-500 ml-1 animate-pulse"></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      {/* T022, T023, T025: Pass streaming state to ChatInput */}
      <ChatInput
        onSend={handleSendMessage}
        onStop={handleStopStreaming}
        isStreaming={isStreaming}
      />
    </div>
  )
}
