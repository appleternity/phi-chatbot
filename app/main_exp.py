import os
import json
import httpx
import asyncio
import hashlib
from uuid import uuid4
from jose import JWTError, jwt
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

from app.prompts import BOT_PROMPTS

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# =========================
# Configuration
# =========================

CHAT_DB_URL = os.getenv("CHAT_DB_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

# --- JWT Settings ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5 #60 * 2  # 2 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# =========================
# Database Setup
# =========================
Base = declarative_base()
engine = create_engine(CHAT_DB_URL)
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    bot_id = Column(String, index=True)
    sender = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    rating = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    user = relationship("User", back_populates="messages")

Base.metadata.create_all(bind=engine)

# =========================
# Security Utilities
# =========================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# =========================
# FastAPI Setup
# =========================
app = FastAPI(title="Chatbot Backend Service")

origins = ["*", "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173/"]
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
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserMessage(BaseModel):
    message: str
    bot_id: str

class BotResponse(BaseModel):
    response: str
    message_id: str

class FeedbackRequest(BaseModel):
    message_id: str
    bot_id: str
    rating: str | None = None
    comment: str | None = None

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token: no user_id")
    return user_id

# =========================
# Routes
# =========================
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chatbot backend running with PostgreSQL & OpenRouter."}


@app.post("/register")
def register(req: RegisterRequest):
    session = SessionLocal()
    existing = session.query(User).filter_by(username=req.username).first()
    if existing:
        session.close()
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    new_user = User(username=req.username, password_hash=hash_password(req.password))
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    session.close()
    print(f"User registered: {new_user.username} (ID: {new_user.id})")
    return {"user_id": new_user.id, "username": new_user.username}


@app.post("/login")
def login(req: LoginRequest):
    session = SessionLocal()
    user = session.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        session.close()
        print("Failed login attempt for username:", req.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    access_token = create_access_token({"sub": user.id})
    session.close()
    print(f"User logged in: {user.username} (ID: {user.id})")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
    }


@app.post("/chat", response_model=BotResponse)
async def chat_endpoint(user_data: UserMessage, current_user: str = Depends(get_current_user)):
    """Send user's message to OpenRouter and return the model's response."""
    user_id = current_user  # use authenticated user's ID instead of request body
    if user_data:
        print(f"[User {user_id}] to [{user_data.bot_id}]: {user_data.message}")

    # Store user's message
    session = SessionLocal()
    user_message = Message(
        id=str(uuid4()),
        user_id=user_id,
        bot_id=user_data.bot_id,
        sender="user",
        text=user_data.message,
    )
    session.add(user_message)
    session.commit()

    # Prepare API request
    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.", message_id=str(uuid4()))

    system_prompt = BOT_PROMPTS[user_data.bot_id]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
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
    print(f"[Bot {user_data.bot_id}] to [{user_id}]: {reply} (Message ID: {message_id})")

    # Store bot message
    bot_message = Message(
        id=message_id,
        user_id=user_id,
        bot_id=user_data.bot_id,
        sender="bot",
        text=reply,
    )
    session.add(bot_message)
    session.commit()
    session.close()

    return BotResponse(response=reply, message_id=message_id)


@app.post("/feedback")
def feedback(req: FeedbackRequest, current_user: str = Depends(get_current_user)):
    """Store feedback for a specific bot message."""
    session = SessionLocal()
    user_id = current_user
    message = session.query(Message).filter_by(id=req.message_id).first()
    if message:
        message.rating = req.rating
        message.comment = req.comment
        session.commit()
        print("Received feedback:", req.dict())
        session.close()
        return {"status": "ok", "message": "Feedback saved."}
    else:
        print("Message not found for feedback:", req.dict())
        session.close()
        return {"status": "error", "message": "Message not found."}


@app.get("/history")
def get_chat_history(user_id: str = Depends(get_current_user)):
    session = SessionLocal()
    try:
        messages = (
            session.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
    except Exception as e:
        print(f"Error fetching chat history for user {user_id}: {e}\n-----\n")
        messages = []
    
    print(f"Fetched chat history for user: {user_id}, total messages: {len(messages)}")
    if len(messages) == 0:
        welcome_messages = [
            {"bot_id": "bot_1", "text": "您好，我是欣宁 🙂\n我可以陪您一起探讨孩子的情绪变化、沟通方式，或您自己在育儿中的压力。\n请放心表达，我会尽力以温和、专业的方式倾听和回应。"},
            {"bot_id": "bot_2", "text": "你好呀～我是小安😊\n有时候孩子的情绪、学习、沟通真的挺让人头疼的。\n你可以跟我聊聊最近让你最烦心或最担心的事，我们一起来想办法！"},
            {"bot_id": "bot_3", "text": "您好，很高兴能和您聊聊。作为家长，关心孩子的情绪和成长真的非常不容易。\n\n您可以把我当作一个安全、不带评判的\"树洞\"，和我聊聊您的困惑和担忧。我也会尽力为您提供一些科学的心理健康科普、实用的沟通技巧和初步的应对建议。\n\n您今天想从哪里开始聊起呢？"},
        ]
        
        for welcome in welcome_messages:
            welcome_message = Message(
                id=str(uuid4()),
                user_id=user_id,
                bot_id=welcome["bot_id"],
                sender="bot",
                text=welcome["text"],
            )
            session.add(welcome_message)
            print('Add welcome message:', welcome_message.text)
        
        session.commit()
        messages = (
            session.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        print(f"Initialized welcome messages for user: {user_id}")
    
    session.close()

    return [
        {
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "bot_id": m.bot_id,
            "rating": m.rating,
            "comment": m.comment,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# Maintain cancel events per user (or per chat session)
cancel_events: dict[str, asyncio.Event] = {}

@app.post("/chat/stream")
async def chat_stream(user_data: UserMessage, current_user: str = Depends(get_current_user)):
    """Stream response from OpenRouter and handle user interruption."""
    user_id = current_user
    if user_data:
        print(f"[User {user_id}] to [{user_data.bot_id}]: {user_data.message}")

    # If there’s an ongoing stream for this user, cancel it
    if user_id in cancel_events:
        cancel_events[user_id].set()

    # Create a new cancel event for this session
    cancel_event = asyncio.Event()
    cancel_events[user_id] = cancel_event

    # Store user's message in DB
    session = SessionLocal()
    user_message = Message(
        id=str(uuid4()), user_id=user_id,
        bot_id=user_data.bot_id, sender="user", text=user_data.message,
    )
    session.add(user_message)
    session.commit()

    # Prepare request
    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.", message_id=str(uuid4()))

    system_prompt = BOT_PROMPTS[user_data.bot_id]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_data.message},
        ],
        "stream": True,
    }

    ENDINGS = ["。", "！", "？", ".", "!", "?", "…", "～", "\n\n", "\n"]

    async def event_generator():
        buffer = ""
        sentence_buffer = ""
        print(f"Streaming start for user={user_id}")

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", OPENROUTER_URL, headers=headers, json=payload) as response:
                    async for chunk in response.aiter_text():
                        if cancel_event.is_set():
                            print(f"Stream cancelled for user {user_id}")
                            break

                        buffer += chunk
                        while True:
                            line_end = buffer.find("\n")
                            if line_end == -1:
                                break
                            line = buffer[:line_end].strip()
                            buffer = buffer[line_end + 1:]

                            if not line or not line.startswith("data: "):
                                continue

                            data = line[6:]
                            if data == "[DONE]":
                                # flush any remaining sentence
                                trimmed = sentence_buffer.strip()
                                if trimmed:
                                    msg_id = _save_message(trimmed, user_id, user_data.bot_id)
                                    print(f"Streaming output: {trimmed}")
                                    yield json.dumps({"response": trimmed, "message_id": msg_id}) + "\n"
                                raise StopAsyncIteration

                            try:
                                data_obj = json.loads(data)
                                delta = data_obj["choices"][0]["delta"]
                                content = delta.get("content", "")
                                if content:
                                    sentence_buffer += content
                                    split_indices = []
                                    for end in ENDINGS:
                                        idx = sentence_buffer.find(end)
                                        while idx != -1:
                                            split_indices.append(idx + len(end))
                                            idx = sentence_buffer.find(end, idx + len(end))

                                    # flush up to the earliest boundary
                                    if split_indices:
                                        split_pos = min(split_indices)
                                        sentence = sentence_buffer[:split_pos].strip()
                                        if sentence:
                                            msg_id = _save_message(sentence, user_id, user_data.bot_id)
                                            print(f"Streaming output: {sentence}")
                                            yield json.dumps({"response": sentence, "message_id": msg_id}) + "\n"
                                        sentence_buffer = sentence_buffer[split_pos:].lstrip()

                            except json.JSONDecodeError:
                                continue

        except StopAsyncIteration:
            pass
        except Exception as e:
            print("Streaming error:", e)
        finally:
            cancel_events.pop(user_id, None)
            yield "[STREAM_END]\n"
            print(f"Stream closed for user={user_id}")

    def _save_message(text: str, user_id: str, bot_id: str):
        """Helper: store one sentence bubble in DB."""
        db_session = SessionLocal()
        msg_id = str(uuid4())
        bot_msg = Message(
            id=msg_id,
            user_id=user_id,
            bot_id=bot_id,
            sender="bot",
            text=text,
        )
        db_session.add(bot_msg)
        db_session.commit()
        db_session.close()
        return msg_id

    return StreamingResponse(event_generator(), media_type="text/plain")