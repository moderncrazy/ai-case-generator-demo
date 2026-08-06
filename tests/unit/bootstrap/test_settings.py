import sys
from pathlib import Path

# The V2 runtime is a top-level `src` package without an editable install, so
# expose the repository root when pytest is invoked from the worktree.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from pydantic import SecretStr, ValidationError

from src.bootstrap.settings import Environment, ProcessRole, Settings


def test_settings_expose_approved_runtime_fields() -> None:
    settings = Settings(
        _env_file=None,
        environment="local",
        process_role="api",
        database_url="postgresql+psycopg://user:pass@localhost:5432/app",
        checkpoint_database_url="postgresql+psycopg://user:pass@localhost:5432/checkpoint",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.environment is Environment.LOCAL
    assert settings.process_role is ProcessRole.API
    assert settings.database_url is not None
    assert settings.checkpoint_database_url is not None
    assert settings.redis_url is not None
    assert settings.database_pool_size > 0
    assert settings.database_max_overflow >= 0


def test_settings_define_no_sqlite_defaults() -> None:
    for name in ("database_url", "checkpoint_database_url", "redis_url"):
        field = Settings.model_fields[name]
        default = field.get_default(call_default_factory=True)
        assert default is None or "sqlite" not in repr(default).lower()


def test_secret_urls_are_secretstr_with_redacted_repr() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:topsecret@localhost:5432/app",
        redis_url="redis://:topsecret@localhost:6379/0",
    )
    assert isinstance(settings.database_url, SecretStr)
    assert isinstance(settings.redis_url, SecretStr)
    assert "topsecret" not in repr(settings)


def test_production_rejects_missing_external_urls() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url=None,
            checkpoint_database_url=None,
            redis_url=None,
        )


def test_production_accepts_all_external_urls() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://user:pass@localhost:5432/app",
        checkpoint_database_url="postgresql+psycopg://user:pass@localhost:5432/checkpoint",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.environment is Environment.PRODUCTION
