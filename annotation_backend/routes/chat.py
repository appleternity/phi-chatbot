import os
import json
import httpx
import asyncio
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from schemas.message import UserMessage, BotResponse, FeedbackRequest
from db.base import get_db
from db.crud import get_current_user
from db.models import Message
from core.config import settings
from prompts import BOT_PROMPTS

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

router = APIRouter()

@router.post("/chat", response_model=BotResponse)
async def chat_endpoint(user_data: UserMessage, 
                        current_user: str = Depends(get_current_user), 
                        db: Session = Depends(get_db)):
    """Send user's message to OpenRouter and return the model's response."""
    user_id = current_user  # use authenticated user's ID instead of request body
    if user_data:
        print(f"[User {user_id}] to [{user_data.bot_id}]: {user_data.message}")

    # # Store user's message
    user_message = Message(
        id=str(uuid4()),
        user_id=user_id,
        bot_id=user_data.bot_id,
        sender="user",
        text=user_data.message,
    )
    db.add(user_message)
    db.commit()

    # Prepare API request
    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.", message_id=str(uuid4()))

    system_prompt = BOT_PROMPTS[user_data.bot_id]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_data.message},
        ],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(settings.OPENROUTER_URL, headers=headers, json=payload)
        data = response.json()

    if "choices" in data and len(data["choices"]) > 0:
        reply = data["choices"][0]["message"]["content"]
    else:
        reply = "Sorry, I couldn't generate a response."

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
    db.add(bot_message)
    db.commit()
    return BotResponse(response=reply, message_id=message_id)


# Maintain cancel events per user (or per chat session)
cancel_events: dict[str, asyncio.Event] = {}

@router.post("/chat/stream")
async def chat_stream(
    user_data: UserMessage,
    request: Request,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream response from OpenRouter and handle user interruption."""
    user_id = current_user
    if user_data:
        print(f"[User {user_id}] to [{user_data.bot_id}]: {user_data.message}")

    # If there's an ongoing stream for this user, cancel it
    if user_id in cancel_events:
        cancel_events[user_id].set()

    # Create a new cancel event for this session
    cancel_event = asyncio.Event()
    cancel_events[user_id] = cancel_event

    # Store user's message in DB
    user_message = Message(
        id=str(uuid4()), user_id=user_id,
        bot_id=user_data.bot_id, sender="user", text=user_data.message,
    )
    db.add(user_message)
    db.commit()

    # Prepare request
    if not OPENROUTER_API_KEY:
        return BotResponse(response="Error: Missing OpenRouter API key.", message_id=str(uuid4()))

    # Get history
    chat_history = (
        db.query(Message)
        .filter(Message.user_id == user_id, Message.bot_id == user_data.bot_id)
        .order_by(Message.created_at.desc())
        .limit(5+1) # include the current user message
        .all()
    )
    chat_history = list(reversed(chat_history))  # Get chronological order (oldest to newest)

    system_prompt = BOT_PROMPTS[user_data.bot_id]

    # Build messages array with history
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    for msg in chat_history:
        if msg.sender == "user":
            messages.append({"role": "user", "content": msg.text})
        elif msg.sender == "bot":
            messages.append({"role": "assistant", "content": msg.text})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.DEFAULT_MODEL,
        "messages": messages,
        "stream": True,
    }

    ENDINGS = ["|", "\n\n", "\n"] #["。", "！", "？", ".", "!", "?", "…", "～", "\n\n", "\n"]

    async def event_generator():
        buffer = ""
        sentence_buffer = ""
        print(f"Streaming start for user={user_id}")

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", settings.OPENROUTER_URL, headers=headers, json=payload) as response:
                    async for chunk in response.aiter_text():
                        # stop if another server-side cancel_event was set
                        if cancel_event.is_set():
                            print(f"Stream cancelled by server for user {user_id}")
                            break

                        # stop if client disconnected (frontend aborted the request)
                        if await request.is_disconnected():
                            print(f"Client disconnected for user {user_id} — stopping stream")
                            # propagate cancel flag so other parts / future requests know
                            cancel_event.set()
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
                                    msg_id = _save_message(trimmed, user_id, user_data.bot_id, db)
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
                                        if sentence and sentence not in ENDINGS:
                                            msg_id = _save_message(sentence, user_id, user_data.bot_id, db)
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
            # ensure we remove the cancel event and signal cancellation
            cancel_events.pop(user_id, None)
            # if client disconnected, try to persist any leftover buffered sentence (optional)
            # flush buffer if necessary
            yield "[STREAM_END]\n"
            print(f"Stream closed for user={user_id}")

    def _save_message(text: str, user_id: str, bot_id: str, db: Session):
        """Helper: store one sentence bubble in DB."""
        msg_id = str(uuid4())
        bot_msg = Message(
            id=msg_id,
            user_id=user_id,
            bot_id=bot_id,
            sender="bot",
            text=text,
        )
        db.add(bot_msg)
        db.commit()
        return msg_id

    return StreamingResponse(event_generator(), media_type="text/plain")




@router.post("/feedback")
def feedback(req: FeedbackRequest, 
             current_user: str = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Store feedback for a specific bot message."""
    user_id = current_user
    message = db.query(Message).filter_by(id=req.message_id).first()
    if message:
        message.rating = req.rating
        message.comment = req.comment
        db.commit()
        print("Received feedback:", req.dict())
        return {"status": "ok", "message": "Feedback saved."}
    else:
        print("Message not found for feedback:", req.dict())
        return {"status": "error", "message": "Message not found."}


@router.get("/history")
def get_chat_history(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get chat history for a specific user.
    """
    try:
        messages = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
    except Exception as e:
        print(f"Error fetching chat history for user {user_id}: {e}\n-----\n")
        messages = []

    print(f"Fetched chat history for user: {user_id}, total messages: {len(messages)}")
    if len(messages) == 0:
        with open(settings.BOT_INFO_PATH, "r", encoding="utf-8") as f:
            bots = json.load(f)
        for bot in bots:
            welcome_message = Message(
                id=str(uuid4()),
                user_id=user_id,
                bot_id=bot["id"],
                sender="bot",
                text=bot["welcome_message"],
            )
            db.add(welcome_message)
            print('Add welcome message:', welcome_message.text)
        db.commit()
        messages = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        print(f"Initialized welcome messages for user: {user_id}")

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
