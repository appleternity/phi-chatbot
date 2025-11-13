from pydantic import BaseModel

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