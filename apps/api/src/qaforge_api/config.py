"""Typed application configuration.

All env vars are validated at startup. A missing required secret should
produce a clear, actionable error naming the variable (per Story 0.3.5
acceptance criteria).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    """Process-wide settings loaded from env / .env file.

    All variables are prefixed `QAFORGE_` except provider keys, which use
    the provider's canonical env var name so existing tooling works.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="QAFORGE_",
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment = Environment.LOCAL
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104  bind-all is intentional in containers
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://qaforge:qaforge@localhost:5432/qaforge"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = None
    s3_bucket: str = "qaforge-evidence"
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str = "us-east-1"

    default_model: str = "claude-sonnet-4-6"

    jwt_secret: SecretStr = Field(default=SecretStr("dev-only-do-not-use-in-prod"))
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None

    github_app_id: str | None = None
    github_app_private_key_path: str | None = None
    github_webhook_secret: SecretStr | None = None

    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "qaforge-api"

    default_max_cost_usd_per_run: float = 5.00
    default_max_runtime_minutes: int = 30

    @property
    def is_prod(self) -> bool:
        return self.env == Environment.PROD


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Use as a FastAPI dependency."""
    return Settings()
