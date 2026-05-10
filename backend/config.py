from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    telegram_bot_token: str = ""
    tavily_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
