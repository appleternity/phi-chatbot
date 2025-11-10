import { useState, useEffect } from 'react'
import ChatContainer from './components/ChatContainer'
import Header from './components/Header'
import {
  generateUserId,
  getUserId,
  setUserId,
  getSessionId,
  clearSession,
} from './utils/session'

function App() {
  const [userId, setCurrentUserId] = useState<string>('')
  const [sessionId, setCurrentSessionId] = useState<string | null>(null)

  // Streaming toggle state (default: disabled as per plan)
  const [streamingEnabled, setStreamingEnabled] = useState(() => {
    const saved = localStorage.getItem('streaming_enabled')
    return saved === 'true' // Default false if not set
  })

  useEffect(() => {
    // Get or create user ID on mount
    let uid = getUserId()
    if (!uid) {
      uid = generateUserId()
      setUserId(uid)
    }
    setCurrentUserId(uid)

    // Load session ID (may be null for new session)
    const sid = getSessionId()
    setCurrentSessionId(sid)
  }, [])

  const handleNewSession = () => {
    // Clear session-specific data (keep user_id)
    clearSession()
    setCurrentSessionId(null)
    // Reload to reset state
    window.location.reload()
  }

  const handleStreamingToggle = (enabled: boolean) => {
    setStreamingEnabled(enabled)
  }

  const handleSessionUpdate = (newSessionId: string) => {
    setCurrentSessionId(newSessionId)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-500 to-secondary-500">
      <div className="container mx-auto px-4 py-6 h-screen flex flex-col">
        <Header
          sessionId={sessionId || 'New Session'}
          onNewSession={handleNewSession}
          streamingEnabled={streamingEnabled}
          onStreamingToggle={handleStreamingToggle}
        />
        <ChatContainer
          userId={userId}
          sessionId={sessionId}
          streamingEnabled={streamingEnabled}
          onSessionUpdate={handleSessionUpdate}
        />
      </div>
    </div>
  )
}

export default App
