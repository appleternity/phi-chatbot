import { BACKEND_URL } from "../config";

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
