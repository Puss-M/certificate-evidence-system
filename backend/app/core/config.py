from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Certificate Evidence System API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str | None = None
    jwt_secret: str | None = None
    public_verify_base_url: str = "http://127.0.0.1:8000/api/verification"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
