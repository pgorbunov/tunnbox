"""Application settings (environment driven, `.env` supported)."""

from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "change-me-in-production"
_RATE_LIMIT_RE = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour|\d+\s*s)\s*$", re.IGNORECASE)


class Settings(BaseSettings):
    """All environment configuration for TunnBox.

    Values come from the process environment or a `.env` file. Names are
    case-insensitive (`SECRET_KEY` -> `secret_key`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = _DEFAULT_SECRET
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    log_format: str = "text"

    database_path: str = "./data/tunnbox.db"
    database_url: str | None = None  # legacy `sqlite+aiosqlite:///...`

    wg_config_path: str = "/etc/wireguard"
    wg_backend_mode: str = "auto"  # auto | real | mock
    wg_default_endpoint: str = ""
    wg_default_dns: str = "1.1.1.1"
    wg_allow_custom_scripts: bool = False

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    session_absolute_days: int = 30
    login_rate_limit: str = "10/minute"
    lockout_threshold: int = 8
    lockout_minutes: int = 15
    trusted_proxies: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cookie_secure: str = "auto"  # auto | true | false
    bcrypt_rounds: int = 12

    stats_sample_seconds: int = 30
    stats_retention_days: int = 90

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("wg_backend_mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"auto", "real", "mock"}:
            raise ValueError("WG_BACKEND_MODE must be auto, real or mock")
        return value

    @field_validator("login_rate_limit")
    @classmethod
    def _validate_rate_limit(cls, value: str) -> str:
        if not _RATE_LIMIT_RE.match(value):
            raise ValueError("LOGIN_RATE_LIMIT must look like '10/minute'")
        return value

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if self.database_url:
            self.database_path = _path_from_legacy_url(self.database_url)
        if self.secret_key == _DEFAULT_SECRET or not self.secret_key:
            self.secret_key = secrets.token_hex(32)
            logger.warning(
                "SECRET_KEY not set; using a temporary generated key. "
                "Sessions and encrypted keys will not survive a restart."
            )
        return self

    # --- Derived helpers -------------------------------------------------

    @property
    def backend_mode(self) -> str:
        """Resolve `auto` to `real` or `mock`."""
        if self.wg_backend_mode != "auto":
            return self.wg_backend_mode
        if sys.platform.startswith("linux") and shutil.which("wg") and shutil.which("wg-quick"):
            return "real"
        return "mock"

    @property
    def config_dir(self) -> Path:
        """Directory that holds rendered `.conf` files.

        In mock mode an unwritable `WG_CONFIG_PATH` falls back to `./data/wireguard`.
        """
        path = Path(self.wg_config_path)
        if self.backend_mode == "mock" and not _writable(path):
            return Path("./data/wireguard")
        return path

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def login_rate(self) -> tuple[int, int]:
        """(max requests, window seconds) parsed from LOGIN_RATE_LIMIT."""
        match = _RATE_LIMIT_RE.match(self.login_rate_limit)
        assert match is not None
        count, unit = int(match.group(1)), match.group(2).lower().replace(" ", "")
        seconds = {"second": 1, "minute": 60, "hour": 3600}.get(unit)
        if seconds is None:
            seconds = int(unit.rstrip("s"))
        return count, seconds

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]


def _writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def _path_from_legacy_url(url: str) -> str:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            rest = url[len(prefix) :]
            # four slashes means absolute path
            return rest if rest.startswith("/") else ("./" + rest if not rest.startswith(".") else rest)
    return url


@lru_cache
def get_settings() -> Settings:
    """Cached settings; call `get_settings.cache_clear()` to re-read the environment."""
    return Settings()
