"""Typed runtime configuration for the trading bot.

Values are loaded from environment variables (and an optional ``.env`` file).
See ``.env.example`` for the available settings. No secrets are hard-coded.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated and loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Exchange / API
    exchange_id: str = "binance"
    api_key: str = ""
    api_secret: str = ""

    # Trading
    trading_symbol: str = "BTC/USDT"
    trading_timeframe: str = "1d"
    dry_run: bool = True

    # Logging
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Return a freshly-loaded :class:`Settings` instance."""
    return Settings()
