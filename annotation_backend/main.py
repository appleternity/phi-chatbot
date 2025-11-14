from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth, bot, chat

app = FastAPI(title="Chatbot Backend Service")

origins = [
    "http://localhost:3000", "http://127.0.0.1:3000", 
    "http://localhost:5173", "http://127.0.0.1:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Tables (dev only)
# TODO: Remove this in production and use migrations instead
from db.base import Base, engine
from db import models
@app.on_event("startup")
def on_startup():
    print("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)

# Routers
app.include_router(auth.router)
app.include_router(bot.router)
app.include_router(chat.router)
