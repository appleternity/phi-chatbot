/**
 * Streaming event types matching backend StreamEvent schema
 */

export type StreamEventType =
  | 'metadata'
  | 'routing_start'
  | 'routing_complete'
  | 'retrieval_start'
  | 'retrieval_complete'
  | 'reranking_start'
  | 'reranking_complete'
  | 'generation_start'
  | 'generation_complete'
  | 'token'
  | 'done'
  | 'error'
  | 'cancelled'

export interface StreamEvent {
  type: StreamEventType
  content?: string | { stage?: string; status?: string; [key: string]: any }
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
 * Stage event: Processing stage transition
 * Covers routing, retrieval, reranking, and generation stages
 */
export interface StageEvent extends StreamEvent {
  type: 'routing_start' | 'routing_complete' | 'retrieval_start' | 'retrieval_complete'
       | 'reranking_start' | 'reranking_complete' | 'generation_start' | 'generation_complete'
  content: { stage: string; status: string; [key: string]: any }
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
 * Metadata event: Session initialization information
 * Emitted at the start of streaming to provide session_id for persistence
 */
export interface MetadataEvent extends StreamEvent {
  type: 'metadata'
  content: { session_id: string }
}

/**
 * Type guard for token events
 */
export function isTokenEvent(event: StreamEvent): event is TokenEvent {
  return event.type === 'token' && typeof event.content === 'string'
}

/**
 * Type guard for stage events
 * Recognizes all stage transition events: routing, retrieval, reranking, generation
 */
export function isStageEvent(event: StreamEvent): event is StageEvent {
  const stageTypes: StreamEventType[] = [
    'routing_start',
    'routing_complete',
    'retrieval_start',
    'retrieval_complete',
    'reranking_start',
    'reranking_complete',
    'generation_start',
    'generation_complete'
  ]
  return stageTypes.includes(event.type)
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

/**
 * Type guard for metadata events
 */
export function isMetadataEvent(event: StreamEvent): event is MetadataEvent {
  return (
    event.type === 'metadata' &&
    typeof event.content === 'object' &&
    event.content !== null &&
    'session_id' in event.content &&
    typeof event.content.session_id === 'string'
  )
}
