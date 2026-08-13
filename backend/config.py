"""App-wide settings, loaded from environment / .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Each LLM-calling layer gets its own model so cost/quality tiers can
    # differ (and later be swapped to another provider) without touching
    # call sites — see providers/llm.py.
    archetype_model: str = "qwen/qwen3.6-27b"
    delta_model: str = "qwen/qwen3.6-27b"
    chat_model: str = "qwen/qwen3.6-27b"

    archetypes_dir: str = "data/archetypes"
    common_template_path: str = "data/common_template.txt"
    tools_dir: str = "data/tools"

    # Phase 3: scheduled callbacks. Abuse bounds + poll/retry timing for
    # scheduler/ — see scheduler/tool.py and scheduler/dispatcher.py.
    scheduled_callback_max_window_days: int = 30
    scheduled_callback_max_pending_per_number: int = 3
    scheduled_callback_poll_interval_seconds: int = 30
    scheduled_callback_retry_delay_seconds: int = 300

    # Plain postgresql:// (or postgresql+asyncpg://) form — db/session.py
    # normalizes the driver, so either works here.
    database_url: str

    # No default: an app-wide secret must never silently fall back to a
    # committed value. Generate one with `openssl rand -hex 32`.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
