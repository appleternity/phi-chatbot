import { useState, useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import WelcomeMessage from './WelcomeMessage'
import { useStreamingChat } from '../hooks/useStreamingChat'
import { sendMessage } from '../services/api'
import { setSessionId } from '../utils/session'
import type { Message } from '../types'

interface ChatContainerProps {
  userId: string
  sessionId: string | null
  streamingEnabled: boolean
  onSessionUpdate: (sessionId: string) => void
}

export default function ChatContainer({ userId, sessionId, streamingEnabled, onSessionUpdate }: ChatContainerProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionId)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Streaming hook with stage tracking, token management, and session extraction
  const { tokens, stage, isStreaming, error: streamError, sessionId: streamSessionId, streamMessage, stopStreaming, clearTokens } = useStreamingChat()

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

  // Persist streaming session_id when received from backend
  useEffect(() => {
    // Only persist if we don't have a session_id yet and streaming provided one
    if (currentSessionId === null && streamSessionId !== null) {
      setCurrentSessionId(streamSessionId)
      setSessionId(streamSessionId)  // Persist to localStorage
      onSessionUpdate(streamSessionId)  // Notify parent (App.tsx) to update Header
      console.log(`✅ Streaming session initialized: ${streamSessionId}`)
    }
  }, [streamSessionId, currentSessionId, onSessionUpdate])

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isStreaming || isLoading || !userId) return

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMessage])

    try {
      if (streamingEnabled) {
        // Streaming mode: Use SSE streaming
        await streamMessage(content, userId, currentSessionId)
      } else {
        // Non-streaming mode: Traditional request/response
        setIsLoading(true)
        const response = await sendMessage(userId, content, currentSessionId)

        // Store backend-generated session_id if this was first message
        if (currentSessionId === null) {
          setCurrentSessionId(response.session_id)
          setSessionId(response.session_id)
          onSessionUpdate(response.session_id)  // Notify parent (App.tsx) to update Header
        }

        // Add assistant response
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.message,
          timestamp: Date.now(),
        }
        setMessages((prev) => [...prev, assistantMessage])
      }
    } catch (error) {
      const errorMessage: Message = {
        role: 'error',
        content: `Failed to get response: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  // Add streaming tokens to messages when stream completes
  useEffect(() => {
    if (!isStreaming && tokens.length > 0) {
      // Capture final content immediately to prevent race conditions
      const finalContent = tokens.join('')

      // Stream completed - add assistant message with accumulated tokens
      const assistantMessage: Message = {
        role: 'assistant',
        content: finalContent,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMessage])

      // Small delay before clearing to ensure message is rendered
      // This prevents race conditions where tokens are cleared before render
      setTimeout(() => clearTokens(), 50)
    }
  }, [isStreaming, tokens, clearTokens])  // Effect runs on streaming state changes

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

  // Export conversation history as JSON file
  const handleExport = () => {
    const exportData = {
      format: 'medical-chatbot-v1',
      exportDate: new Date().toISOString(),
      sessionId: sessionId,
      messageCount: messages.length,
      messages: messages,
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `chat-history-${new Date().toISOString().split('T')[0]}-${Date.now()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Import conversation history from JSON file
  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const data = JSON.parse(content)

        // Validate format
        if (!data.messages || !Array.isArray(data.messages)) {
          alert('Invalid file format: missing messages array')
          return
        }

        // Basic validation of message structure
        const isValid = data.messages.every((msg: any) =>
          msg.role && msg.content && msg.timestamp
        )

        if (!isValid) {
          alert('Invalid file format: messages have invalid structure')
          return
        }

        // Import messages
        setMessages(data.messages)
        alert(`Successfully imported ${data.messages.length} messages`)
      } catch (error) {
        alert(`Failed to import: ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
    }

    reader.onerror = () => {
      alert('Failed to read file')
    }

    reader.readAsText(file)

    // Reset input so same file can be imported again
    if (event.target) {
      event.target.value = ''
    }
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="flex-1 bg-white rounded-b-2xl shadow-lg flex flex-col overflow-hidden">
      {/* Dev Tools: Export/Import */}
      <div className="bg-gray-100 border-b border-gray-200 px-4 py-2 flex items-center gap-2">
        <span className="text-xs text-gray-500 font-medium">Dev Tools:</span>
        <button
          onClick={handleExport}
          disabled={messages.length === 0}
          className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          title="Export conversation history as JSON"
        >
          📥 Export JSON
        </button>
        <button
          onClick={triggerFileInput}
          className="px-3 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
          title="Import conversation history from JSON"
        >
          📤 Import JSON
        </button>
        <span className="text-xs text-gray-400 ml-auto">
          {messages.length} messages
        </span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleImport}
          className="hidden"
        />
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
        {messages.length === 0 && <WelcomeMessage />}
        {messages.map((message, index) => (
          <ChatMessage key={index} message={message} />
        ))}
        {/* Progressive token rendering with stage status */}
        {isStreaming && (
          <div className="flex justify-start mb-4">
            <div className="flex flex-col gap-1">
              {/* Streaming Message - Show different UI based on token availability */}
              {tokens.length > 0 ? (
                // Show message box with content + three-dot cursor
                <div className="max-w-[75%] bg-white text-gray-800 rounded-2xl px-5 py-3 shadow-md border border-gray-200">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                    {tokens.join('')}
                    {/* Three-dot typing indicator with staggered animation */}
                    <span className="inline-flex gap-0.5 ml-1 items-end">
                      <span className="w-1 h-1 rounded-full bg-gray-700 animate-pulse"></span>
                      <span className="w-1 h-1 rounded-full bg-gray-700 animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                      <span className="w-1 h-1 rounded-full bg-gray-700 animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                    </span>
                  </p>
                </div>
              ) : (
                // Before tokens arrive, show minimal typing indicator
                <div className="flex items-center gap-1 px-4 py-2">
                  <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></span>
                  <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.1s' }}></span>
                  <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                </div>
              )}
              {/* Stage Status - Small text below message */}
              {stage && (
                <div className="text-xs text-gray-500 px-2">
                  {stage === 'routing' && 'Routing...'}
                  {stage === 'retrieval' && 'Searching knowledge base...'}
                  {stage === 'reranking' && 'Analyzing context...'}
                  {stage === 'generation' && 'Writing response...'}
                </div>
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      {/* Pass both streaming and loading states to ChatInput */}
      <ChatInput
        onSend={handleSendMessage}
        onStop={handleStopStreaming}
        isStreaming={isStreaming}
        isLoading={isLoading}
      />
    </div>
  )
}
