import { BACKEND_URL } from "../config";
import { BotProfile, ChatMessage } from '../types/chat';

export async function fetchBots() {
  try {
    const response = await fetch(`${BACKEND_URL}/bots`);
    if (!response.ok) {
      throw new Error(`Failed to fetch bots: ${response.statusText}`);
    }
    const data = await response.json();
    return { bots: data.bots };
  } catch (error) {
    console.error("Failed to fetch bots:", error);
    return { bots: [] };
  }
}

export function createInitialHistories(bots: BotProfile[]): Record<string, ChatMessage[]> {
  const result: Record<string, ChatMessage[]> = {};
  bots.forEach(bot => {
    result[bot.id] = [{
      id: crypto.randomUUID(),
      sender: 'bot',
      text: bot.welcome_message,
      rating: null,
      comment: null,
    }];
  });
  return result;
}
