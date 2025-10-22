export function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
}

export function getSessionId(): string | null {
  return localStorage.getItem('session_id')
}

export function setSessionId(sessionId: string): void {
  localStorage.setItem('session_id', sessionId)
}

export function clearSession(): void {
  localStorage.removeItem('session_id')
  localStorage.removeItem('chat_history')
}
