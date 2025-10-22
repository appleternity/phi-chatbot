import { RefreshCw } from 'lucide-react'

interface HeaderProps {
  sessionId: string
  onNewSession: () => void
}

export default function Header({ sessionId, onNewSession }: HeaderProps) {
  return (
    <div className="bg-white rounded-t-2xl shadow-lg px-6 py-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
            🏥 Medical Chatbot
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Mental Health Support & Medication Information
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-gray-500 mb-1">Session ID</p>
            <code className="text-xs bg-gray-100 px-3 py-1 rounded-md font-mono text-gray-700">
              {sessionId.substring(0, 16)}...
            </code>
          </div>
          <button
            onClick={onNewSession}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary-500 to-secondary-500 text-white rounded-lg hover:shadow-lg transition-all duration-200 hover:scale-105"
            title="Start a new conversation"
          >
            <RefreshCw size={16} />
            <span className="text-sm font-medium">New Session</span>
          </button>
        </div>
      </div>
    </div>
  )
}
