import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, register } from "../services/authService";

interface LoginPageProps {
  onLoginSuccess?: () => void;
}

export default function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      if (isRegistering) {
        await register(username, password);
        setIsRegistering(false);
        setUsername("");
        setPassword("");
        return;
      } 
      
      const user = await login(username, password);
      localStorage.setItem("user_id", user.user_id);
      localStorage.setItem("username", user.username);
      onLoginSuccess?.(); // Notify parent component
      navigate("/chat");
    } catch (err) {
      const errorMessage = (err as Error).message;
      setError(errorMessage);
      console.error(errorMessage);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-80">
        <h2 className="text-2xl font-bold mb-4 text-center">
          {isRegistering ? "Create Account" : "Login"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            placeholder="Username"
            className="w-full p-2 border rounded-md"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            className="w-full p-2 border rounded-md"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
          >
            {isRegistering ? "Register" : "Login"}
          </button>
        </form>
        {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        <p className="text-sm text-gray-600 text-center mt-4">
          {isRegistering ? (
            <>
              Already have an account?{" "}
              <button
                onClick={() => setIsRegistering(false)}
                className="text-blue-600 underline"
              >
                Login
              </button>
            </>
          ) : (
            <>
              No account?{" "}
              <button
                onClick={() => setIsRegistering(true)}
                className="text-blue-600 underline"
              >
                Register
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
