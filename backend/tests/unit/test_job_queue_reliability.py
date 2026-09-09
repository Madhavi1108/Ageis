"""Phase 27 unit: job-queue reliability -- backpressure, real not-before
backoff, non-retryable failure codes, heartbeat-aware orphan reclaim."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base
from app.models.job import JobState, JobType
from app.models.task import Task, TaskState
from app.orchestration import job_queue
from app.orchestration.job_queue import QueueFullError
from app.repository.jobs import JobRepository


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _task(db, key: str) -> Task:
    t = Task(
        repository_id="r1",
        task_type="BUG",
        title="t",
        description_sanitized="d",
        idempotency_key=key,
        state=TaskState.PENDING.value,
    )
    db.add(t)
    db.commit()
    return t


def test_enqueue_run_rejects_when_queue_is_full():
    db = _db()
    settings = Settings(job_max_queue_depth=2, _env_file=None)
    for i in range(2):
        job_queue.enqueue_run(db, _task(db, f"k{i}").id, settings=settings)
    assert job_queue.queue_depth(db) == 2

    with pytest.raises(QueueFullError) as ei:
        job_queue.enqueue_run(db, _task(db, "k-overflow").id, settings=settings)
    assert ei.value.status_code == 429
    assert ei.value.details["queue_depth"] == 2
    assert ei.value.details["limit"] == 2


def test_retry_sets_a_future_run_after_and_claim_skips_it():
    db = _db()
    job = job_queue.enqueue_run(db, _task(db, "k").id, settings=Settings(_env_file=None))
    JobRepository(db).get(job.id)
    job.max_attempts = 3
    job.attempts = 1
    db.commit()

    delay = job_queue.retry_or_fail(
        db, job.id, error={"code": "ORCHESTRATION_FAILED"}, backoff_base_s=5.0
    )
    assert delay == 5.0
    row = JobRepository(db).get(job.id)
    assert row.state == JobState.QUEUED.value
    assert row.run_after is not None
    # not claimable yet -- run_after is in the future
    assert job_queue.claim_next(db, worker_id="w1") is None

    # once run_after passes, it is claimable again
    row.run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    claimed = job_queue.claim_next(db, worker_id="w1")
    assert claimed is not None and claimed.id == job.id


def test_non_retryable_error_code_fails_immediately():
    db = _db()
    job = job_queue.enqueue_run(db, _task(db, "k").id, settings=Settings(_env_file=None))
    JobRepository(db).get(job.id)
    job.max_attempts = 5
    job.attempts = 1
    db.commit()

    delay = job_queue.retry_or_fail(
        db, job.id, error={"code": "IMPLEMENTATION_FAILED"}, backoff_base_s=2.0
    )
    assert delay is None
    assert JobRepository(db).get(job.id).state == JobState.FAILED.value


def test_heartbeat_keeps_a_long_running_job_from_being_reclaimed():
    db = _db()
    job = job_queue.enqueue_run(db, _task(db, "k").id, settings=Settings(_env_file=None))
    jobs = JobRepository(db)
    jobs.mark_running(job.id)

    # started long ago, but a recent heartbeat -> still alive
    row = jobs.get(job.id)
    row.started_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db.commit()
    jobs.heartbeat(job.id)

    assert job_queue.reclaim_orphans(db, stale_after_s=900) == []
    assert jobs.get(job.id).state == JobState.RUNNING.value

    # stale heartbeat -> reclaimed
    row = jobs.get(job.id)
    row.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert job_queue.reclaim_orphans(db, stale_after_s=900) == [job.id]
    assert jobs.get(job.id).state == JobState.QUEUED.value


def test_enqueue_gc_dedupes_on_bucket():
    db = _db()
    first = job_queue.enqueue_gc(db, bucket="2026090912")
    assert first is not None and first.type == JobType.GC.value
    assert job_queue.enqueue_gc(db, bucket="2026090912") is None
    assert job_queue.enqueue_gc(db, bucket="2026090913") is not None
