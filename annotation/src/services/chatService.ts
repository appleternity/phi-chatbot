const FASTAPI_URL = 'http://127.0.0.1:8000';

export async function login(username: string, password: string) {
  const res = await fetch(`${FASTAPI_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function register(username: string, password: string) {
  const res = await fetch(`${FASTAPI_URL}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

export async function getHistory(userId: string) {
  const res = await fetch(`${FASTAPI_URL}/history/${userId}`);
  if (!res.ok) throw new Error("Could not fetch history");
  return res.json();
}

export async function fetchBotResponse(
  message: string,
  botId: string,
  userId: string
): Promise<string> {
  try {
    const response = await fetch(`${FASTAPI_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, bot_id: botId, user_id: userId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return { text: data.response, messageId: data.message_id };
  } catch (err) {
    console.error('Error fetching from FastAPI:', err);
    return {
      text: `(Server Error) Could not connect to FastAPI.`,
      messageId: crypto.randomUUID(),
    };
  }
}

export async function sendFeedback({
  messageId,
  botId,
  userId,
  rating,
  comment,
}: {
  messageId: string;
  botId: string;
  userId: string;
  rating: 'up' | 'down' | null;
  comment?: string | null;
}) {
  try {
    const response = await fetch(`${FASTAPI_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_id: messageId,
        bot_id: botId,
        user_id: userId,
        rating,
        comment,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    console.log('✅ Feedback sent successfully');
  } catch (err) {
    console.error('Error sending feedback to FastAPI:', err);
  }
}