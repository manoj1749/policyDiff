from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_db: str = "policydiff"
    clickhouse_secure: bool = False
    clickhouse_verify: bool = True
    nimble_api_key: str = ""
    nimble_api_url: str = "https://api.nimbleway.com/v1/extract"
    nimble_request_timeout_seconds: int = 105
    nimble_html_extract_timeout_seconds: int = 45
    nimble_pdf_extract_timeout_seconds: int = 90
    nimble_max_retries: int = 3
    nimble_retry_backoff_seconds: float = 2.0
    poll_interval_minutes: int = 30
    watchlist_path: Path = Field(default_factory=lambda: SERVICE_ROOT / "config" / "watchlist.yaml")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
