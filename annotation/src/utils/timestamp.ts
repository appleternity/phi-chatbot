/**
 * Get current timestamp in ISO 8601 format
 */
export function getCurrentTimestamp(): string {
  return new Date().toISOString();
}

/**
 * Generate unique message ID using timestamp and random string
 */
export function generateMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Format ISO 8601 timestamp to user-friendly time display
 * @param timestamp - ISO 8601 timestamp string
 * @returns Formatted time string (e.g., "12:34 PM")
 */
export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}
