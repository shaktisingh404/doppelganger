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

    # Phone-call replies should be a sentence or two, not an essay — the
    # common template already prompts for that (see data/common_template.txt:
    # 1-2 sentences per turn, 3 at most, one point at a time even if there's
    # a multi-step plan to get through). This is the hard backstop behind
    # that prompt: a real ceiling so a model that ignores the instruction
    # still can't turn a multi-point answer into a 12-sentence monologue in
    # one turn. Sized a bit above the prompt's own target (~15-20 tokens/
    # sentence x 2-3 sentences) rather than exactly at it — cut too tight,
    # a model that slightly overshoots the prompt gets truncated mid-
    # sentence, which reads far worse on a call than a reply running one
    # sentence long. providers.llm._warn_if_truncated logs when this cap
    # is actually hit, so a persona that keeps tripping it is visible in
    # logs rather than just sounding randomly cut off. Low, not zero,
    # temperature: consistent and on-script without sounding
    # robotic/repetitive turn to turn.
    chat_max_tokens: int = 150
    chat_temperature: float = 0.4
    # qwen3 (the default chat_model) is a reasoning model: left unset, it
    # spends completion tokens on hidden chain-of-thought before ever
    # writing the visible reply, and with chat_max_tokens capped low that
    # reasoning alone can exhaust the budget -- finish_reason="length"
    # with an EMPTY reply, no error raised. "none" skips reasoning
    # entirely, which is also just the right call for short phone-call
    # answers that don't need step-by-step thinking. Set to None if
    # chat_model is ever swapped to a model that doesn't support this
    # Groq-specific param (an unrecognized param is a 400, not a no-op).
    chat_reasoning_effort: str | None = "none"

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
