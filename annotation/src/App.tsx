import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";
import { getToken, logout } from "./services/authService";
import { useEffect, useState } from "react";
import { jwtDecode } from "jwt-decode";

interface DecodedToken {
  sub: string;
  exp: number;
}

// Utility function to check token validity
function isTokenValid(token: string | null): boolean {
  if (!token) return false;
  try {
    const decoded = jwtDecode<DecodedToken>(token);
    if (!decoded.exp) return false;
    return decoded.exp * 1000 > Date.now(); // check expiry
  } catch {
    return false;
  }
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (isTokenValid(token)) {
      setIsAuthenticated(true);
    } else {
      logout();
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* Default route: redirect based on auth state */}
        <Route
          path="/"
          element={<Navigate to={isAuthenticated ? "/chat" : "/login"} />}
        />

        {/* Public route: Login */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected route: Chat */}
        <Route
          path="/chat"
          element={
            isAuthenticated ? <ChatPage /> : <Navigate to="/login" replace />
          }
        />

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}