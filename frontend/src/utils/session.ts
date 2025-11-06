// User ID management
export function generateUserId(): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(2, 11)
  return `user_${timestamp}_${random}`
}

export function getUserId(): string | null {
  return localStorage.getItem('user_id')
}

export function setUserId(userId: string): void {
  localStorage.setItem('user_id', userId)
}

// Session ID management (backend-generated)
export function getSessionId(): string | null {
  return localStorage.getItem('session_id')
}

export function setSessionId(sessionId: string): void {
  localStorage.setItem('session_id', sessionId)
}

export function clearSession(): void {
  // Clear session-specific data only (keep user_id)
  localStorage.removeItem('session_id')
  localStorage.removeItem('chat_history')
}
