"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model name")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://rca_user:rca_password@localhost:5432/rca_bot"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://rca_user:rca_password@localhost:5432/rca_bot"
    )

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4317")
    otel_service_name: str = Field(default="incident-rca-bot")

    # Ticketing
    ticketing_webhook_url: str = Field(default="http://localhost:8080/api/tickets")

    # App
    log_level: str = Field(default="INFO")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()