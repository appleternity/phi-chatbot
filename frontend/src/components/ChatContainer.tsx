import { useState, useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import WelcomeMessage from './WelcomeMessage'
import { sendMessage } from '../services/api'
import { setSessionId } from '../utils/session'
import type { Message } from '../types'

interface ChatContainerProps {
  userId: string
  sessionId: string | null
}

export default function ChatContainer({ userId, sessionId }: ChatContainerProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionId)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
    if (!content.trim() || isLoading || !userId) return

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      // Backend creates session_id if currentSessionId is null
      const response = await sendMessage(userId, content, currentSessionId)

      // Store backend-generated session_id if this was first message
      if (currentSessionId === null) {
        setCurrentSessionId(response.session_id)
        setSessionId(response.session_id)
      }

      // Add assistant message
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.message,
        agent: response.agent,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      // Add error message
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
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[75%] bg-white rounded-2xl px-5 py-3 shadow-md border border-gray-200">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">💭 Thinking</span>
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <ChatInput onSend={handleSendMessage} isLoading={isLoading} />
    </div>
  )
}
