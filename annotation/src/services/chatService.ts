const FASTAPI_URL = 'http://127.0.0.1:8000/chat';

export async function fetchBotResponse(
  message: string,
  botId: string,
  userId: string
): Promise<string> {
  try {
    const response = await fetch(FASTAPI_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, bot_id: botId, user_id: userId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.response;
  } catch (err) {
    console.error('Error fetching from FastAPI:', err);
    return `(Server Error) Could not connect to FastAPI at ${FASTAPI_URL}. Please ensure the server is running.`;
  }
}
