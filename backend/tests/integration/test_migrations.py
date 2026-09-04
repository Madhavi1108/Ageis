"""Alembic upgrade/downgrade against a throwaway SQLite file.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10 Integration tests: "Alembic
upgrade then downgrade on a fresh SQLite file."
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config(db_path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option(
        "script_location", str(BACKEND_DIR / "app" / "db" / "migrations")
    )
    config.attributes["sqlalchemy.url"] = f"sqlite:///{db_path}"
    import os

    os.environ["AEGIS_DATABASE_URL"] = f"sqlite:///{db_path}"
    return config


def test_upgrade_then_downgrade_is_clean(tmp_path, monkeypatch):
    from alembic import command

    db_path = tmp_path / "migration_test.db"
    monkeypatch.setenv("AEGIS_DATABASE_URL", f"sqlite:///{db_path}")

    from app.core.config import get_settings

    get_settings.cache_clear()
    config = _alembic_config(db_path)

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert {"job", "audit_log"}.issubset(tables)
    engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert "job" not in tables
    assert "audit_log" not in tables
    engine.dispose()

    get_settings.cache_clear()
