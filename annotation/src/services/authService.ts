const BASE_URL = "http://127.0.0.1:8000";

export async function register(username: string, password: string) {
  const res = await fetch(`${BASE_URL}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

export async function login(username: string, password: string) {
  const res = await fetch(`${BASE_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function getChatHistory(userId: string) {
  const res = await fetch(`${BASE_URL}/history/${userId}`);
  if (!res.ok) throw new Error("Failed to fetch chat history");
  return res.json();
}
