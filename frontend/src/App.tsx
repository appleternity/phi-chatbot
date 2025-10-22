import { useState, useEffect } from 'react'
import ChatContainer from './components/ChatContainer'
import Header from './components/Header'
import { generateSessionId, getSessionId, setSessionId } from './utils/session'

function App() {
  const [sessionId, setCurrentSessionId] = useState<string>('')

  useEffect(() => {
    // Get or create session ID on mount
    let sid = getSessionId()
    if (!sid) {
      sid = generateSessionId()
      setSessionId(sid)
    }
    setCurrentSessionId(sid)
  }, [])

  const handleNewSession = () => {
    const newSessionId = generateSessionId()
    setSessionId(newSessionId)
    setCurrentSessionId(newSessionId)
    // Clear localStorage history
    localStorage.removeItem('chat_history')
    // Reload to reset state
    window.location.reload()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-500 to-secondary-500">
      <div className="container mx-auto px-4 py-6 h-screen flex flex-col">
        <Header sessionId={sessionId} onNewSession={handleNewSession} />
        <ChatContainer sessionId={sessionId} />
      </div>
    </div>
  )
}

export default App
