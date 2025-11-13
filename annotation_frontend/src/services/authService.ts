import { BACKEND_URL } from "../config";


export async function login(username: string, password: string) {
  const res = await fetch(`${BACKEND_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("username", data.username);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
}

export function getToken() {
  return localStorage.getItem("token");
}

export async function register(username: string, password: string) {
  const res = await fetch(`${BACKEND_URL}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}