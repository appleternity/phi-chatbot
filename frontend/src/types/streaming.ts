/**
 * Streaming event types matching backend StreamEvent schema
 */

export type StreamEventType = 'token' | 'stage' | 'done' | 'error' | 'cancelled'

export interface StreamEvent {
  type: StreamEventType
  content?: string
  stage?: string
  error?: string
  timestamp?: number
}

/**
 * Token event: Individual text token from LLM response
 */
export interface TokenEvent extends StreamEvent {
  type: 'token'
  content: string
}

/**
 * Stage event: Processing stage transition (e.g., "rag_agent", "emotional_support")
 */
export interface StageEvent extends StreamEvent {
  type: 'stage'
  stage: string
}

/**
 * Done event: Stream completion marker
 */
export interface DoneEvent extends StreamEvent {
  type: 'done'
}

/**
 * Error event: Backend error during processing
 */
export interface ErrorEvent extends StreamEvent {
  type: 'error'
  error: string
}

/**
 * Cancelled event: Client-initiated stream cancellation
 */
export interface CancelledEvent extends StreamEvent {
  type: 'cancelled'
}

/**
 * Type guard for token events
 */
export function isTokenEvent(event: StreamEvent): event is TokenEvent {
  return event.type === 'token' && typeof event.content === 'string'
}

/**
 * Type guard for stage events
 */
export function isStageEvent(event: StreamEvent): event is StageEvent {
  return event.type === 'stage' && typeof event.stage === 'string'
}

/**
 * Type guard for done events
 */
export function isDoneEvent(event: StreamEvent): event is DoneEvent {
  return event.type === 'done'
}

/**
 * Type guard for error events
 */
export function isErrorEvent(event: StreamEvent): event is ErrorEvent {
  return event.type === 'error' && typeof event.error === 'string'
}

/**
 * Type guard for cancelled events
 */
export function isCancelledEvent(event: StreamEvent): event is CancelledEvent {
  return event.type === 'cancelled'
}
