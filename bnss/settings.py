import logging
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BNSS_")

    token: str
    prefix: Optional[str] = "!"
    log_level: Optional[int] = logging.INFO
    debug: Optional[bool] = True


@lru_cache()
def get_settings() -> Settings:
    """Return the settings for the bot."""

    return Settings()
