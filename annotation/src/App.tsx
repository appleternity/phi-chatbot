import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  const userId = localStorage.getItem("user_id");

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={userId ? "/chat" : "/login"} />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}
