"""Settings, read from environment variables (see .env.example at the repo root)."""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Env = Literal["dev", "test", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: Env = "dev"
    app_name: str = "CompanyMgmt"

    # The runtime role must not own the tables and must not have BYPASSRLS.
    database_url: SecretStr = SecretStr("postgresql+psycopg://cm_app:cm_app@localhost:5432/companymgmt")
    # Used only by migrations and admin scripts.
    migrations_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://cm_owner:cm_owner@localhost:5432/companymgmt"
    )
    app_db_role: str = "cm_app"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    web_base_url: str = "http://localhost:3000"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Ed25519 keys in PEM. Generated per process in dev/test when empty.
    jwt_private_key: SecretStr = SecretStr("")
    jwt_public_key: str = ""
    jwt_issuer: str = "companymgmt"
    jwt_audience: str = "companymgmt-web"
    access_token_minutes: int = 10
    refresh_idle_days: int = 7
    refresh_absolute_days: int = 30
    # A refresh token used again within this window is treated as a benign race
    # (two tabs refreshing at once), not as theft.
    refresh_reuse_grace_seconds: int = 10
    step_up_minutes: int = 5
    # New workspaces per IP address per hour (raised only for end-to-end test runs).
    signup_limit_per_hour: int = 10
    # Sign-ins per IP address per five minutes (raised only for end-to-end test runs, which
    # sign thirty people in from one address).
    login_limit_per_ip: int = 30

    # {"key id": "base64 32-byte key"}; the active id encrypts, all ids decrypt.
    field_encryption_keys: SecretStr = SecretStr("")
    field_encryption_active_kid: str = "k1"

    email_backend: Literal["console", "memory", "smtp"] = "console"
    smtp_url: SecretStr = SecretStr("")
    mail_from: str = "CompanyMgmt <no-reply@localhost>"

    turnstile_secret: SecretStr = SecretStr("")
    # Failed logins (per account or IP) before a Turnstile challenge is required.
    captcha_after_failures: int = 5

    # Shared secret for /internal/* (Cloud Scheduler sends it as X-Internal-Token).
    internal_token: SecretStr = SecretStr("")

    trust_proxy_headers: bool = False
    # Shared with the Cloudflare Pages Function that serves /v1 on the web origin. When
    # set, /v1 requests must come through that proxy (header X-CM-Proxy-Token), and the
    # client IP comes from the X-CM-Client-IP it adds (Cloudflare's CF-Connecting-IP), so
    # nobody can dodge per-IP rate limits by calling the API directly with a forged
    # X-Forwarded-For.
    proxy_token: SecretStr = SecretStr("")
    sentry_dsn: SecretStr = SecretStr("")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _production_requirements(self) -> Settings:
        if self.env in ("staging", "prod"):
            missing = [
                name
                for name, value in (
                    ("JWT_PRIVATE_KEY", self.jwt_private_key.get_secret_value()),
                    ("FIELD_ENCRYPTION_KEYS", self.field_encryption_keys.get_secret_value()),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required settings in {self.env}: {', '.join(missing)}")
            if self.email_backend in ("console", "memory"):
                raise ValueError("A real email backend is required outside dev and test.")
        return self

    @property
    def is_production_like(self) -> bool:
        return self.env in ("staging", "prod")

    def encryption_keys(self) -> dict[str, bytes]:
        raw = self.field_encryption_keys.get_secret_value()
        if not raw:
            # Deterministic dev/test key. Never used in staging or prod (see validator).
            return {self.field_encryption_active_kid: b"\x00" * 32}
        keys = {kid: base64.b64decode(v) for kid, v in json.loads(raw).items()}
        if any(len(k) != 32 for k in keys.values()):
            raise ValueError("Field encryption keys must be 32 bytes.")
        if self.field_encryption_active_kid not in keys:
            raise ValueError("The active encryption key id is not in FIELD_ENCRYPTION_KEYS.")
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
