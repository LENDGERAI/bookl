from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOKLIFY_", env_file=".env", extra="ignore")

    app_name: str = "Booklify API"
    api_prefix: str = "/api/v1"
    environment: str = "dev"
    database_url: str = "sqlite:///./booklify.db"
    upload_dir: str = "./uploads"
    export_dir: str = "./exports"
    queue_mode: str = "inline"
    queue_workers: int = 4
    max_upload_files: int = 100
    high_volume_upload_threshold: int = 25
    default_language: str = "en"
    encryption_key: str | None = None

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def export_path(self) -> Path:
        return Path(self.export_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.export_path.mkdir(parents=True, exist_ok=True)
    return settings

