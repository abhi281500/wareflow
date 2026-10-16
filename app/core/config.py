from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "WareFlow"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "postgresql+psycopg://postgres@127.0.0.1:5433/wareflow_dev"
    TEST_DATABASE_URL: str = "postgresql+psycopg://postgres@127.0.0.1:5433/wareflow_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
