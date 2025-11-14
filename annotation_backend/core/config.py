from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENROUTER_API_KEY: str
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL: str = "qwen/qwen3-max"
    
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "chatdb"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433

    @property
    def CHAT_DB_URL(self):
        print("POSTGRES_HOST:", self.POSTGRES_HOST)
        print("POSTGRES_DB:", self.POSTGRES_DB)
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Bot Info
    BOT_INFO_PATH: str = "data/bots.json"

settings = Settings()