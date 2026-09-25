"""Application configuration loaded from environment variables.

All settings can be overridden via environment variables or a local ``.env``
file (see ``.env.example``). Nothing secret is hard-coded.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "Candidate Assessment API"
    environment: Literal["development", "production", "test"] = "development"
    # Comma-separated list of allowed CORS origins (the frontend URLs).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ---
    # Default: local SQLite file. Swap for a Postgres URL to scale up.
    database_url: str = "sqlite:///./data/app.db"

    # --- Auth ---
    # The single admin account. In production, set a strong password + secret.
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-in-prod"
    jwt_secret: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12  # 12h
    # When False, the admin console is open (no login) — handy for local/demo use.
    auth_enabled: bool = True

    # --- Uploads / limits ---
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    # Candidate links expire after this many days (0 = never).
    session_expiry_days: int = 14

    # --- Storage (Cloudflare R2 / S3-compatible) ---
    # When r2_endpoint_url is empty we fall back to local disk storage (dev).
    storage_backend: Literal["r2", "local"] = "local"
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "assessments"
    r2_region: str = "auto"
    # Directory used by the local storage fallback.
    local_storage_dir: str = "./data/files"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
