"""Fixtures for the Phase 24 end-to-end pipeline tests.

Mirrors ``tests/integration/conftest.py`` (SQLite + ``Base.metadata.create_all``,
``expire_on_commit=False``); adds a source-tree fixture for the acceptance repos.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base

REPO_ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_SRC = REPO_ROOT / "test-repositories" / "aegis-acceptance"
UNFIXABLE_SRC = REPO_ROOT / "test-repositories" / "aegis-acceptance-unfixable"


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'e2e.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def acceptance_src() -> Path:
    return ACCEPTANCE_SRC


@pytest.fixture
def unfixable_src() -> Path:
    return UNFIXABLE_SRC
