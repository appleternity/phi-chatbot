from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth, bot, chat

app = FastAPI(title="Chatbot Backend Service")

origins = ["*", "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173/"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(bot.router)
app.include_router(chat.router)
