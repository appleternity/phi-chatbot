from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL: str = "qwen/qwen3-max"

    CHAT_DB_URL: str = "postgresql://postgres:postgres@localhost:5433/chatdb"

    # JWT Configuration
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Bot Info
    BOT_INFO_PATH: str = "data/bots.json"

settings = Settings()