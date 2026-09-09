"""Phase 27 integration: the worker self-enqueues a GC job on its interval and
runs it to SUCCEEDED."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base
from app.models.job import JobState, JobType
from app.orchestration.worker import OrchestrationWorker
from app.repository.jobs import JobRepository


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_worker_runs_a_gc_job(tmp_path):
    db = _db()
    settings = Settings(
        artifacts_root=str(tmp_path / "artifacts"),
        gc_enabled=True,
        gc_interval_s=3600,
        _env_file=None,
    )
    worker = OrchestrationWorker(settings, session_factory=lambda: db)

    handled = worker.run_once(db)
    jobs = JobRepository(db)
    all_gc = [j for j in _all_jobs(db) if j.type == JobType.GC.value]
    assert len(all_gc) == 1
    assert handled == all_gc[0].id
    assert jobs.get(all_gc[0].id).state == JobState.SUCCEEDED.value

    # a second poll within the interval does not pile up another GC job
    worker.run_once(db)
    assert len([j for j in _all_jobs(db) if j.type == JobType.GC.value]) == 1


def _all_jobs(db):
    from app.models.job import Job

    return db.query(Job).all()
