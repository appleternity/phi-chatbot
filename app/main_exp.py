from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from uuid import uuid4
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import httpx
import os

# =========================
# Configuration
# =========================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

CHAT_DB_URL = os.getenv("CHAT_DB_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

# =========================
# Database Setup
# =========================
Base = declarative_base()
engine = create_engine(CHAT_DB_URL)
SessionLocal = sessionmaker(bind=engine)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    bot_id = Column(String, index=True)
    sender = Column(String)  # "user" or "bot"
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    rating = Column(String, nullable=True)
    comment = Column(Text, nullable=True)


Base.metadata.create_all(bind=engine)

# =========================
# FastAPI Setup
# =========================
app = FastAPI(title="Chatbot Backend Service")

origins = ["*", "http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Pydantic Models
# =========================
class UserMessage(BaseModel):
    message: str
    bot_id: str
    user_id: str


class BotResponse(BaseModel):
    response: str
    message_id: str


class FeedbackRequest(BaseModel):
    message_id: str
    bot_id: str
    user_id: str
    rating: str | None = None
    comment: str | None = None


# =========================
# Routes
# =========================
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chatbot backend running with PostgreSQL & OpenRouter."}


@app.post("/chat", response_model=BotResponse)
async def chat_endpoint(user_data: UserMessage):
    """Send user's message to OpenRouter and return the model's response."""
    if user_data:
        print(f"[User {user_data.user_id}] to [{user_data.bot_id}]: {user_data.message}")

    # Store user's message
    session = SessionLocal()
    user_message = Message(
        id=str(uuid4()),
        user_id=user_data.user_id,
        bot_id=user_data.bot_id,
        sender="user",
        text=user_data.message,
    )
    session.add(user_message)
    session.commit()

    # Prepare API request
    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.", message_id=str(uuid4()))

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

    # Create bot message ID
    message_id = str(uuid4())
    print(f"[{message_id}] [Bot {user_data.bot_id}] to [{user_data.user_id}]: {reply}")

    # Store bot message
    bot_message = Message(
        id=message_id,
        user_id=user_data.user_id,
        bot_id=user_data.bot_id,
        sender="bot",
        text=reply,
    )
    session.add(bot_message)
    session.commit()
    session.close()

    return BotResponse(response=reply, message_id=message_id)


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Store feedback for a specific bot message."""
    session = SessionLocal()
    message = session.query(Message).filter_by(id=req.message_id).first()
    if message:
        message.rating = req.rating
        message.comment = req.comment
        session.commit()
        print("Received feedback:", req.dict())
        session.close()
        return {"status": "ok", "message": "Feedback saved."}
    else:
        session.close()
        return {"status": "error", "message": "Message not found."}
