"""Application configuration. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10.

Settings are validated eagerly at process start (``create_app()`` calls
``get_settings()`` before anything else) so a missing or malformed
environment variable fails fast with a clear error, rather than surfacing
lazily on first request.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_ENVIRONMENTS = {"dev", "test", "prod"}


class Settings(BaseSettings):
    """Process-wide configuration, sourced from environment variables / .env.

    All AEGIS-specific variables are prefixed ``AEGIS_`` (e.g. ``AEGIS_LOG_LEVEL``).
    ``extra="forbid"`` rejects unknown keys passed directly to the constructor
    (e.g. in tests); pydantic-settings does not extend that check to the
    process environment itself, so an unrecognized ``AEGIS_*`` env var is
    ignored rather than rejected -- other tools' env vars may share the
    prefix, and this avoids fail-fast being overly strict about that.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AEGIS_",
        extra="forbid",
        case_sensitive=False,
    )

    environment: str = Field(default="dev", description="dev | test | prod")
    log_level: str = Field(default="INFO")
    database_url: str = Field(default="sqlite:///./aegis.db")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    request_max_body_bytes: int = Field(default=1_000_000, gt=0)

    # Ingestion (Phase 3, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11 / ADR-0012).
    ingestion_local_roots: list[str] = Field(
        default_factory=lambda: ["../test-repositories"]
    )
    ingestion_allowed_remote_hosts: list[str] = Field(
        default_factory=lambda: ["github.com"]
    )
    ingestion_max_repo_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    ingestion_max_files: int = Field(default=25_000, gt=0)
    ingestion_max_file_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    ingestion_max_history_depth: int = Field(default=500, gt=0)
    ingestion_default_clone_depth: int = Field(default=50, gt=0)
    ingestion_clone_timeout_s: int = Field(default=120, gt=0)
    artifacts_root: str = Field(default="./artifacts")

    # Task / issue ingestion (Phase 6, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14).
    # Issue text above this byte budget is truncated (not rejected), with the
    # original size recorded on the create response for provenance.
    task_max_description_bytes: int = Field(default=50_000, gt=0)
    task_max_title_chars: int = Field(default=200, gt=0)

    @field_validator("ingestion_local_roots")
    @classmethod
    def _resolve_local_roots(cls, v: list[str]) -> list[str]:
        # Resolved once here so url_validator.validate_local_path can do a plain
        # containment check against already-absolute paths on both sides.
        return [str(Path(root).resolve()) for root in v]

    @field_validator("environment")
    @classmethod
    def _valid_environment(cls, v: str) -> str:
        if v not in _VALID_ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {sorted(_VALID_ENVIRONMENTS)}, got {v!r}"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {v!r}"
            )
        return upper


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (constructed once, cached)."""
    return Settings()
