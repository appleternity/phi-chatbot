from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import os

# --- Pydantic Models ---
class UserMessage(BaseModel):
    message: str
    bot_id: str
    user_id: str

class BotResponse(BaseModel):
    response: str

# --- FastAPI App Setup ---
app = FastAPI(title="Chatbot Backend Service")

origins = [
    "*",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- OpenRouter Settings ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("MODEL_NAME")  # You can replace with any model name from OpenRouter

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chatbot backend is running with OpenRouter."}

@app.post("/chat", response_model=BotResponse)
async def chat_endpoint(user_data: UserMessage):
    """Send user's message to OpenRouter and return the model's response."""
    if user_data:
        print(f"[{user_data.bot_id}] {user_data.user_id}: {user_data.message}")

    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": f"You are {user_data.bot_id}, a helpful assistant."},
            {"role": "user", "content": user_data.message},
        ],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        data = response.json()

    if "choices" in data and len(data["choices"]) > 0:
        reply = data["choices"][0]["message"]["content"]
    else:
        reply = "Sorry, I couldn’t generate a response."

    return BotResponse(response=reply)
