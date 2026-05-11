from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    telegram_bot_token: str = ""
    tavily_api_key: str = ""
    forge_encryption_key: str = ""
    langchain_tracing_v2: str = ""
    langchain_api_key: str = ""
    langchain_project: str = "forge"

    class Config:
        env_file = "../.env"
        extra = "ignore"


settings = Settings()
