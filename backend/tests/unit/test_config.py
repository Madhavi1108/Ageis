import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_valid(monkeypatch):
    monkeypatch.delenv("AEGIS_ENVIRONMENT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment == "dev"
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("sqlite")


def test_valid_env_overrides(monkeypatch):
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "prod")
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "debug")
    settings = Settings(_env_file=None)
    assert settings.environment == "prod"
    assert settings.log_level == "DEBUG"


def test_malformed_environment_raises_clear_error(monkeypatch):
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "not-a-real-env")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "environment" in str(exc_info.value)


def test_malformed_log_level_raises_clear_error(monkeypatch):
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "SUPER_VERBOSE")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "log_level" in str(exc_info.value)


def test_unknown_env_var_is_ignored_not_fatal(monkeypatch):
    # pydantic-settings does not extend extra="forbid" to the process
    # environment (only to direct constructor kwargs) -- an unrecognized
    # AEGIS_*-prefixed env var should not prevent startup.
    monkeypatch.setenv("AEGIS_NOT_A_REAL_SETTING", "x")
    settings = Settings(_env_file=None)
    assert settings.environment == "dev"


def test_unknown_constructor_kwarg_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, not_a_real_setting="x")
