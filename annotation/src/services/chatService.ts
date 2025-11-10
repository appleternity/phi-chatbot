const FASTAPI_URL = 'http://127.0.0.1:8000';
import { getToken } from "./authService";

export async function fetchBotResponse(message: string, botId: string) {
  const token = getToken();
  const response = await fetch(`${FASTAPI_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, bot_id: botId }),
  });
  const data = await response.json();
  return { text: data.response, message_id: data.message_id };
}

export async function getChatHistory() {
  const token = getToken();
  const res = await fetch(`${FASTAPI_URL}/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}

export async function sendFeedback(payload: any) {
  const token = getToken();
  await fetch(`${FASTAPI_URL}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}


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
