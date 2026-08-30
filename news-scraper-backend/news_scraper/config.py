"""Application settings.

Pydantic-settings v2 config with a ``get_settings`` provider so a host
application can construct/override settings per-request context and tests can
patch the provider. Environment variables are read from ``.env`` in the
working directory unless overridden.

Safety defaults:
- ``cors_origins`` excludes the wildcard ``*`` (set explicitly for dev).
- ``web_scraping_enabled`` is off unless Selenium is installed and enabled —
  the RSS/HN-API path is the primary, dependency-light source.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment -------------------------------------------------------
    environment: str = "development"

    # API ----------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    api_prefix: str = "/api/news"

    # Database -----------------------------------------------------------
    database_path: str = "news_scraper.db"
    database_url: Optional[str] = None  # future: Postgres connection string

    # Scraping -----------------------------------------------------------
    scraping_timeout: int = 30
    max_articles_per_source: int = 50
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    scraper_min_profit_score: float = 4.0
    # Requires the optional "webscraping" extra (Selenium). RSS/API path
    # never touches this.
    web_scraping_enabled: bool = False

    # Scheduler ----------------------------------------------------------
    default_scraping_time: str = "00:00"
    scheduler_check_interval: int = 60  # seconds
    # Interval mode: > 0 scrapes every N minutes instead of daily at
    # default_scraping_time. Trading integration runs at 5; 0 keeps legacy daily.
    scrape_interval_minutes: int = 0
    # Start the scheduler thread automatically on app startup (production sets
    # this in .env; default False keeps tests and embedded hosts inert).
    scheduler_autostart: bool = False

    # Clustering (Phase 2) ------------------------------------------------
    clustering_enabled: bool = True
    clustering_time_window_hours: int = 12

    # Backtesting (Phase 3) ------------------------------------------------
    backtest_enabled: bool = True
    backtest_time_24h: str = "02:00"  # daily: backtest articles from 24h ago
    backtest_time_7d: str = "14:00"   # daily: backtest articles from 7d ago
    backtest_rate_limit_delay: float = 1.5  # seconds between CoinGecko calls

    # CORS ---------------------------------------------------------------
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    cors_credentials: bool = False
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]

    # Logging ------------------------------------------------------------
    log_level: str = "INFO"

    # Chrome/Selenium (web-scraping extra only) ---------------------------
    chrome_headless: bool = True
    chrome_no_sandbox: bool = True
    chrome_disable_dev_shm: bool = True
    chrome_disable_gpu: bool = True
    chrome_window_size: str = "1920,1080"

    # Slack Notifications -----------------------------------------------
    slack_notification_webhook: Optional[str] = None

    # Helpers ------------------------------------------------------------
    def cors_kwargs(self) -> dict:
        """CORS middleware arguments, driven by one settings object."""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": self.cors_credentials,
            "allow_methods": self.cors_methods,
            "allow_headers": self.cors_headers,
        }


@lru_cache
def get_settings() -> Settings:
    """Provider used by FastAPI dependencies; patchable in tests."""
    return Settings()


settings = get_settings()
