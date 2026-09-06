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
    assert {
        "job",
        "audit_log",
        "repository",
        "repository_snapshot",
        "repository_file",
        "artifact",
        "repository_symbol",
        "dependency",
        "repository_analysis",
        "graph_node",
        "graph_edge",
        "issue",
        "task",
        "task_step",
        "code_mapping",
        "impact_analysis",
        "engineering_plan",
        "implementation",
        "patch",
        "test_case",
        "test_execution",
        "failure",
        "investigation",
        "repair_attempt",
        "regression_plan",
    }.issubset(tables)
    engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    for table in (
        "job",
        "audit_log",
        "repository",
        "repository_snapshot",
        "repository_file",
        "artifact",
        "repository_symbol",
        "dependency",
        "repository_analysis",
        "graph_node",
        "graph_edge",
        "issue",
        "task",
        "task_step",
        "code_mapping",
        "impact_analysis",
        "engineering_plan",
        "implementation",
        "patch",
        "test_case",
        "test_execution",
        "failure",
        "investigation",
        "repair_attempt",
        "regression_plan",
    ):
        assert table not in tables
    engine.dispose()

    get_settings.cache_clear()
