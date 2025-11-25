from pydantic_settings import BaseSettings
from typing import Optional



class Settings(BaseSettings):
    PROJECT_NAME: str = "Punch Chat"
    DEBUG: bool = True

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SUMMARIZER_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
