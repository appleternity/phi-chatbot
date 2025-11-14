from pydantic_settings import BaseSettings

# TODO: Include API Key placeholder here (e.g., JWT or OPENROUTER_API_KEY) as a reference
# TODO: Don't need to include a value here, just the variable name
# TODO: This helps to keep track of all required environment variables in one place

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