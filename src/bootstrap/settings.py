"""Platform V2 runtime settings."""

from enum import StrEnum

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class ProcessRole(StrEnum):
    """Backend process role."""

    API = "api"
    WORKER = "worker"
    SCHEDULER = "scheduler"


class Settings(BaseSettings):
    """Runtime configuration for the API, Worker, and Scheduler processes.

    External service URLs are secret-bearing and use ``SecretStr`` so they are
    redacted from repr/log output. SQLite is never a V2 default; non-production
    configurations may leave the URLs unset, while production requires all three.
    """

    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    process_role: ProcessRole = ProcessRole.API

    database_url: SecretStr | None = None
    checkpoint_database_url: SecretStr | None = None
    redis_url: SecretStr | None = None

    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)
    checkpoint_pool_size: int = Field(default=5, ge=1)
    checkpoint_max_overflow: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def production_requires_external_urls(self) -> "Settings":
        """Reject production configuration that lacks the three external URLs."""
        if self.environment is not Environment.PRODUCTION:
            return self
        missing = [
            name
            for name in ("database_url", "checkpoint_database_url", "redis_url")
            if getattr(self, name) is None or not getattr(self, name).get_secret_value()
        ]
        if missing:
            raise ValueError(
                "production settings require external service URLs; missing: "
                + ", ".join(missing)
            )
        return self
