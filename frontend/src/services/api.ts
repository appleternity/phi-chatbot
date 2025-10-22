import axios from 'axios'
import type { ChatResponse } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
})

export async function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>('/chat', {
    session_id: sessionId,
    message,
  })
  return response.data
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await api.get('/health')
  return response.data
}
