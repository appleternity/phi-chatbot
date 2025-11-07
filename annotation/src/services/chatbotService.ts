/**
 * Mock chatbot service for simulating chatbot responses
 * In production, this would integrate with actual chat API endpoints
 */

/**
 * Send a message to a chatbot and receive a response
 * @param chatId - Unique identifier for the chatbot instance
 * @param message - User's message content
 * @returns Promise resolving to bot's response text
 */
export async function sendMessage(chatId: string, message: string): Promise<string> {
  // Simulate API delay (1-2 seconds)
  await new Promise((resolve) => setTimeout(resolve, 1000 + Math.random() * 1000));

  // Mock responses for testing
  const responses = [
    `This is a response from ${chatId} to your message: "${message}"`,
    `I understand you're asking about "${message}". Here's my perspective...`,
    `That's an interesting question about "${message}". Let me explain...`,
    `Regarding "${message}", I would say that...`,
    `Based on "${message}", here's what I think...`,
  ];

  // Return a random response
  return responses[Math.floor(Math.random() * responses.length)];
}
