from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    # App
    secret_key: str = "change-me-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./tunnbox.db"

    # WireGuard
    wg_config_path: str = "/etc/wireguard"
    wg_default_dns: str = "1.1.1.1"
    wg_default_endpoint: str = ""
    wg_backend_mode: str = "auto"  # "auto", "real", "mock"

    # Auth
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Security
    wg_allow_custom_scripts: bool = False
    rate_limit_enabled: bool = True
    rate_limit_redis_url: str = ""
    trusted_proxies: str = ""
    csrf_protection_enabled: bool = False  # Set to True in production
    cors_origins: list[str] | str = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [i.strip() for i in v.split(",")]
        return v

    def model_post_init(self, __context):
        if self.secret_key == "change-me-in-production":
            self.secret_key = secrets.token_hex(32)
            print("WARNING: SECRET_KEY not set in environment. Using generated temporary key. Sessions will be invalidated on restart.")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
