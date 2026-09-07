"""Phase 21 unit: job-queue primitives (claim, dedup, retry/backoff, reclaim)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.job import Job, JobState, JobType
from app.models.task import Task, TaskState
from app.orchestration import job_queue
from app.repository.jobs import JobRepository


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _task(db, key="k1") -> Task:
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


def test_enqueue_run_is_idempotent():
    db = _db()
    t = _task(db)
    j1 = job_queue.enqueue_run(db, t.id)
    j2 = job_queue.enqueue_run(db, t.id)
    assert j1.id == j2.id
    assert j1.state == JobState.QUEUED.value
    assert j1.dedupe_key == t.idempotency_key


def test_claim_next_fifo_and_dedup():
    db = _db()
    ta, tb = _task(db, "ka"), _task(db, "kb")
    job_queue.enqueue_run(db, ta.id)
    job_queue.enqueue_run(db, tb.id)

    first = job_queue.claim_next(db, worker_id="w1")
    assert first.task_id == ta.id
    assert first.state == JobState.RUNNING.value and first.worker_id == "w1"

    # a second QUEUED job with a *different* dedupe_key is claimable
    second = job_queue.claim_next(db, worker_id="w1")
    assert second.task_id == tb.id

    # nothing left
    assert job_queue.claim_next(db, worker_id="w1") is None


def test_claim_skips_dedupe_collision_with_running():
    db = _db()
    t = _task(db, "kx")
    running = Job(
        type=JobType.RUN_TASK.value,
        idempotency_key="run:old",
        task_id=t.id,
        dedupe_key=t.idempotency_key,
        state=JobState.RUNNING.value,
    )
    queued = Job(
        type=JobType.RUN_TASK.value,
        idempotency_key="run:new",
        task_id=t.id,
        dedupe_key=t.idempotency_key,
        state=JobState.QUEUED.value,
    )
    db.add_all([running, queued])
    db.commit()
    assert job_queue.claim_next(db, worker_id="w1") is None  # collision -> skipped


def test_retry_or_fail_backoff_then_fail():
    db = _db()
    t = _task(db)
    job = job_queue.enqueue_run(db, t.id)
    JobRepository(db).get(job.id)
    job.max_attempts = 2
    job.attempts = 1
    db.commit()

    delay = job_queue.retry_or_fail(db, job.id, error={"m": "x"}, backoff_base_s=2.0)
    assert delay == 2.0
    assert JobRepository(db).get(job.id).state == JobState.QUEUED.value

    JobRepository(db).get(job.id)
    job.attempts = 2
    db.commit()
    delay = job_queue.retry_or_fail(db, job.id, error={"m": "x"}, backoff_base_s=2.0)
    assert delay is None
    assert JobRepository(db).get(job.id).state == JobState.FAILED.value


def test_reclaim_orphans():
    db = _db()
    t = _task(db)
    job = job_queue.enqueue_run(db, t.id)
    JobRepository(db).mark_running(job.id)
    orphan = JobRepository(db).get(job.id)
    orphan.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    reclaimed = job_queue.reclaim_orphans(db, stale_after_s=900)
    assert reclaimed == [job.id]
    assert JobRepository(db).get(job.id).state == JobState.QUEUED.value
    assert JobRepository(db).get(job.id).worker_id is None
