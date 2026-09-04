import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.job import JobState
from app.repository.jobs import JobRepository


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    yield db
    db.close()


def test_create_and_get_roundtrip(session):
    repo = JobRepository(session)
    created = repo.create(type="INGEST", idempotency_key="key-1")

    assert created.id
    assert created.state == JobState.PENDING.value

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.idempotency_key == "key-1"


def test_get_missing_returns_none(session):
    repo = JobRepository(session)
    assert repo.get("does-not-exist") is None


def test_list_returns_created_jobs(session):
    repo = JobRepository(session)
    repo.create(type="INGEST", idempotency_key="a")
    repo.create(type="RUN_TASK", idempotency_key="b")

    jobs = repo.list()
    assert len(jobs) == 2
