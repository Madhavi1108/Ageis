from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base

REPO_ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_FIXTURE = REPO_ROOT / "test-repositories" / "aegis-acceptance"


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ingest_test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def acceptance_fixture_path() -> Path:
    return ACCEPTANCE_FIXTURE


@pytest.fixture
def ingestion_settings(tmp_path):
    return Settings(
        ingestion_local_roots=[str(REPO_ROOT / "test-repositories"), str(tmp_path)],
        artifacts_root=str(tmp_path / "artifacts"),
        _env_file=None,
    )
