export interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
  agent?: string
  timestamp: number
}

export interface ChatResponse {
  session_id: string
  message: string
  agent: string
  metadata?: Record<string, any>
}

export interface ChatRequest {
  session_id: string
  message: string
}
