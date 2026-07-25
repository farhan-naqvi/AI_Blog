from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_CONFIG = SettingsConfigDict(
    env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
)


class OllamaSettings(BaseSettings):
    model_config = ENV_CONFIG

    ollama_base_url: HttpUrl = "http://localhost:11434"
    ollama_model: str = Field(default="qwen2.5:7b", min_length=1, max_length=120)


class Settings(BaseSettings):
    model_config = ENV_CONFIG

    supabase_url: HttpUrl
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr
    ollama_base_url: HttpUrl = "http://localhost:11434"
    ollama_model: str = Field(default="qwen2.5:7b", min_length=1, max_length=120)
    local_worker_id: str = Field(default="owner-laptop", min_length=1, max_length=120)
    github_token: SecretStr | None = None
    huggingface_token: SecretStr | None = None
    max_pending_jobs: int = Field(default=500, ge=10, le=5000)
    max_pending_age_days: int = Field(default=7, ge=1, le=30)
    linkedin_draft_ttl_hours: int = Field(default=48, ge=1, le=168)
    collection_batch_size: int = Field(default=50, ge=1, le=200)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
