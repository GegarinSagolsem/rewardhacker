"""Backend settings from environment variables / ``.env``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..config import load_dotenv


class ConfigError(RuntimeError):
    """A required setting is missing or invalid."""


@dataclass(frozen=True)
class ApiSettings:
    database_url: str
    jwt_secret: str
    mongodb_uri: str | None = None  # None = keep traces in memory (dev/tests only)
    mongodb_db: str = "rewardhacker"
    token_ttl_minutes: int = 60 * 12
    storage_dir: Path = Path.home() / ".rewardhacker" / "tasks"
    max_upload_mb: int = 20
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)


def get_api_settings() -> ApiSettings:
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ConfigError("DATABASE_URL is not set (see .env.example)")
    secret = os.environ.get("RH_JWT_SECRET", "").strip()
    if len(secret) < 32:
        raise ConfigError("RH_JWT_SECRET must be set to a random string of at least 32 characters")
    storage = os.environ.get("RH_STORAGE_DIR")
    origins = os.environ.get("RH_CORS_ORIGINS", "http://localhost:5173")
    return ApiSettings(
        database_url=database_url,
        jwt_secret=secret,
        mongodb_uri=os.environ.get("MONGODB_URI", "").strip() or None,
        mongodb_db=os.environ.get("RH_MONGODB_DB", "rewardhacker"),
        token_ttl_minutes=int(os.environ.get("RH_TOKEN_TTL_MINUTES", 60 * 12)),
        storage_dir=Path(storage) if storage else ApiSettings.storage_dir,
        max_upload_mb=int(os.environ.get("RH_MAX_UPLOAD_MB", 20)),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
