import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.user import RegisterRequest, LoginRequest
from db.models import User, Message
from db.base import get_db
from core.security import hash_password, verify_password, create_access_token
from core.config import settings

router = APIRouter(tags=["Auth"])

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # TODO: We will need to also comment out this route when deploying
    existing = db.query(User).filter_by(username=req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    new_user = User(username=req.username, password_hash=hash_password(req.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"User registered: {new_user.username} (ID: {new_user.id})")

    with open(settings.BOT_INFO_PATH, "r", encoding="utf-8") as f:
        bots = json.load(f)
    for bot in bots:
        welcome_message = Message(
            id=str(uuid4()),
            user_id=new_user.id,
            bot_id=bot["id"],
            sender="bot",
            text=bot["welcome_message"],
        )
        db.add(welcome_message)
        print('Add welcome message:', welcome_message.text)
    db.commit()

    return {"user_id": new_user.id, "username": new_user.username}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        print("Failed login attempt for username:", req.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    access_token = create_access_token({"sub": user.id})
    print(f"User logged in: {user.username} (ID: {user.id})")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
    }