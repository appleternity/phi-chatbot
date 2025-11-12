import axios from 'axios'
import type { ChatResponse } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_TOKEN = import.meta.env.VITE_CHAT_API_TOKEN

// Validate token at module load time (fail-fast)
if (!API_TOKEN) {
  console.error('❌ VITE_CHAT_API_TOKEN is not configured. Please set it in .env file.')
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    ...(API_TOKEN && { 'Authorization': `Bearer ${API_TOKEN}` }),
  },
  timeout: 120000, // 120 seconds (2 minutes) - increased for RAG operations
})

// Add response interceptor for authentication error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('Authentication failed: Invalid or expired token')
      throw new Error('Authentication failed: Invalid or expired token')
    }
    if (error.response?.status === 403) {
      console.error('Access denied: Insufficient permissions')
      throw new Error('Access denied: Insufficient permissions')
    }
    throw error
  }
)

export async function sendMessage(
  userId: string,
  message: string,
  sessionId: string | null
): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>('/chat', {
    user_id: userId,
    session_id: sessionId,
    message,
  })
  return response.data
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await api.get('/health')
  return response.data
}
