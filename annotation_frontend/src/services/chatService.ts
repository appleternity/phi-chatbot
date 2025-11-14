import { BACKEND_URL } from "../config";
import { getToken } from "./authService";


export async function getChatHistory() {
  const token = getToken();
  const res = await fetch(`${BACKEND_URL}/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}

export async function sendFeedback(payload: any) {
  const token = getToken();
  await fetch(`${BACKEND_URL}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export async function fetchBotResponse(message: string, botId: string) {
  const token = getToken();
  const response = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, bot_id: botId }),
  });
  const data = await response.json();
  return { text: data.response, message_id: data.message_id };
}

export async function fetchBotStreamResponse(
  text: string,
  botId: string,
  onChunk: (chunk: string, messageId: string) => void,
  controllerRef?: React.MutableRefObject<AbortController | null>
): Promise<{ message_id: string; fullText: string }> {
  const token = getToken();
  const controller = new AbortController();
  if (controllerRef) controllerRef.current = controller;

  const response = await fetch(`${BACKEND_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message: text, bot_id: botId }),
    signal: controller.signal,
  });

  if (!response.body) throw new Error("No response body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "", fullText = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line === "[STREAM_END]") break;
      if (line.trim()) {
        try {
          const data = JSON.parse(line);
          onChunk(data.response, data.message_id);
          fullText += data.response;
        } catch (e) {
          console.error("Failed to parse chunk:", e);
        }
      }
    }
  }

  return { message_id: crypto.randomUUID(), fullText };
}
