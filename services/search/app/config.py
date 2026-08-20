from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = None
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_generation_model: str = "gemini-3.6-flash"
    embedding_dimensions: int = 768

    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None

    rag_match_count: int = 5
    rag_match_threshold: float = 0.45
    rag_max_context_chars: int = 12000


@lru_cache
def get_settings() -> Settings:
    return Settings()
