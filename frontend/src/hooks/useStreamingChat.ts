import { useState, useRef, useCallback } from 'react'
import type { StreamEvent } from '../types/streaming'
import { isTokenEvent, isStageEvent, isDoneEvent, isErrorEvent, isCancelledEvent } from '../types/streaming'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface StreamingState {
  tokens: string[]
  stage: string
  isStreaming: boolean
  error: string | null
}

interface UseStreamingChatReturn {
  tokens: string[]
  stage: string
  isStreaming: boolean
  error: string | null
  streamMessage: (message: string, userId: string, sessionId: string | null) => Promise<void>
  stopStreaming: () => void
  clearTokens: () => void
  resetState: () => void
}

/**
 * Custom hook for streaming chat responses via SSE
 *
 * Implements:
 * - T017: fetch() + ReadableStream pattern for POST requests
 * - T018: AbortController integration for stop button support (FR-018)
 * - T019: Token accumulation state management
 * - T020: SSE parsing logic with buffer handling for incomplete chunks
 *
 * Usage:
 * ```tsx
 * const { tokens, isStreaming, streamMessage, stopStreaming } = useStreamingChat()
 *
 * // Start streaming
 * await streamMessage("Hello", "session-123")
 *
 * // Stop streaming (FR-018)
 * stopStreaming()
 * ```
 */
export function useStreamingChat(): UseStreamingChatReturn {
  const [state, setState] = useState<StreamingState>({
    tokens: [],
    stage: '',
    isStreaming: false,
    error: null,
  })

  // AbortController reference for stop button (FR-018, T018)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Buffer for incomplete SSE chunks (T020)
  const bufferRef = useRef<string>('')

  /**
   * Parse SSE formatted data
   * Handles incomplete chunks by buffering partial data
   *
   * SSE Format:
   * data: {"type": "token", "content": "Hello"}\n\n
   * data: {"type": "done"}\n\n
   */
  const parseSSEChunk = useCallback((chunk: string): StreamEvent[] => {
    // Append to buffer for incomplete chunks
    bufferRef.current += chunk

    const events: StreamEvent[] = []
    const lines = bufferRef.current.split('\n\n')

    // Process all complete events (last element may be incomplete)
    for (let i = 0; i < lines.length - 1; i++) {
      const line = lines[i].trim()

      // Skip empty lines and comments
      if (!line || line.startsWith(':')) continue

      // Parse "data: " prefix
      if (line.startsWith('data: ')) {
        try {
          const jsonStr = line.substring(6) // Remove "data: " prefix
          const event = JSON.parse(jsonStr) as StreamEvent
          events.push(event)
        } catch (error) {
          console.error('Failed to parse SSE event:', line, error)
        }
      }
    }

    // Keep incomplete chunk in buffer
    bufferRef.current = lines[lines.length - 1]

    return events
  }, [])

  /**
   * Stream a message and accumulate tokens progressively
   * Uses fetch() + ReadableStream for POST support (T017, T020)
   */
  const streamMessage = useCallback(async (message: string, userId: string, sessionId: string | null) => {
    // Reset state for new stream
    setState({
      tokens: [],
      stage: '',
      isStreaming: true,
      error: null,
    })

    // Clear buffer from previous stream
    bufferRef.current = ''

    // Create AbortController for stop button (T018, FR-018)
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
          message,
          streaming: true,  // Enable SSE streaming mode
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      // Read stream using ReadableStream API (T017)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          // Stream completed successfully
          break
        }

        // Decode chunk and parse SSE events (T020)
        const chunk = decoder.decode(value, { stream: true })
        const events = parseSSEChunk(chunk)

        // Process each event
        for (const event of events) {
          if (isTokenEvent(event)) {
            // Accumulate token (T019, FR-001, FR-002)
            setState(prev => ({
              ...prev,
              tokens: [...prev.tokens, event.content],
            }))
          } else if (isStageEvent(event)) {
            // Update processing stage (FR-004, FR-005)
            setState(prev => ({
              ...prev,
              stage: event.stage || '',
            }))
          } else if (isDoneEvent(event)) {
            // Stream completed
            setState(prev => ({
              ...prev,
              isStreaming: false,
            }))
            break
          } else if (isErrorEvent(event)) {
            // Backend error (FR-010)
            setState(prev => ({
              ...prev,
              error: event.error || 'Unknown error',
              isStreaming: false,
            }))
            break
          } else if (isCancelledEvent(event)) {
            // Stream was cancelled (FR-019, FR-020)
            setState(prev => ({
              ...prev,
              isStreaming: false,
            }))
            break
          }
        }
      }

      // Final cleanup
      setState(prev => ({
        ...prev,
        isStreaming: false,
      }))

    } catch (error) {
      // Handle fetch errors and cancellations
      if (error instanceof Error && error.name === 'AbortError') {
        // User clicked stop button (FR-018, FR-019)
        console.log('Stream cancelled by user')
        setState(prev => ({
          ...prev,
          isStreaming: false,
        }))
      } else {
        // Network or parsing error
        console.error('Streaming error:', error)
        setState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Unknown error',
          isStreaming: false,
        }))
      }
    } finally {
      // Cleanup AbortController
      abortControllerRef.current = null
    }
  }, [parseSSEChunk])

  /**
   * Stop the current stream (FR-018, T018)
   * Triggers AbortController.abort()
   */
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      console.log('Stopping stream...')
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }, [])

  /**
   * Clear tokens after adding to message history
   * Prevents memory leak and duplicate messages
   */
  const clearTokens = useCallback(() => {
    setState(prev => ({
      ...prev,
      tokens: [],
      stage: '',
    }))
  }, [])

  /**
   * Reset state to initial values
   * Useful for clearing UI after errors
   */
  const resetState = useCallback(() => {
    setState({
      tokens: [],
      stage: '',
      isStreaming: false,
      error: null,
    })
    bufferRef.current = ''
  }, [])

  return {
    tokens: state.tokens,
    stage: state.stage,
    isStreaming: state.isStreaming,
    error: state.error,
    streamMessage,
    stopStreaming,
    clearTokens,
    resetState,
  }
}
