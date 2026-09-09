"""Job queue primitives for the Phase 21 worker
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29; hardened in Phase 27).

The worker is a single sequential asyncio process -> a single SQLite writer, so
a plain ``SELECT ... LIMIT 1`` + update is a safe claim (ADR-0003). The functions
are the abstraction seam if a distributed queue (RQ/Celery/arq) is swapped in
later.

Phase 27 adds: real not-before backoff on retry (``Job.run_after``), a
liveness heartbeat so a legitimately long job is not reclaimed as an orphan,
queue-depth admission control, and a periodic ``GC`` job.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.job import Job, JobState, JobType
from app.repository.jobs import JobRepository
from app.repository.tasks import TaskRepository

_ACTIVE_JOB_STATES = (JobState.QUEUED.value, JobState.PENDING.value)
_DEFAULT_CLAIM_TYPES = (JobType.RUN_TASK.value, JobType.GC.value)

# non-retryable failure codes -- a retry cannot help, fail immediately
_TERMINAL_ERROR_CODES = frozenset(
    {
        "PLAN_GENERATION_FAILED",
        "IMPLEMENTATION_FAILED",
        "TEST_GENERATION_FAILED",
        "GENERATED_CODE_UNSAFE",
        "TASK_INVALID_STATE",
        "VALIDATION_ERROR",
    }
)


class QueueFullError(AppError):
    """The job queue is at its configured depth -- reject with a 429."""

    def __init__(self, depth: int, limit: int) -> None:
        super().__init__(
            "JOB_QUEUE_FULL",
            f"job queue is full ({depth} >= {limit}); retry shortly",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"queue_depth": depth, "limit": limit},
        )
        self.depth = depth
        self.limit = limit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def queue_depth(db: Session) -> int:
    jobs = JobRepository(db)
    return sum(jobs.count(state=s) for s in _ACTIVE_JOB_STATES)


def enqueue_run(db: Session, task_id: str, *, settings: Settings | None = None) -> Job:
    """Idempotent enqueue for ``POST /tasks/{id}/run``: a stable ``run:{task_id}``
    key + a content ``dedupe_key``. A second call while the first run is live
    returns the existing job. Raises ``QueueFullError`` when the queue is at
    ``settings.job_max_queue_depth``."""
    settings = settings or get_settings()
    jobs = JobRepository(db)
    key = f"run:{task_id}"
    existing = jobs.get_by_idempotency_key(key)
    if existing is not None:
        return existing

    depth = queue_depth(db)
    if depth >= settings.job_max_queue_depth:
        raise QueueFullError(depth, settings.job_max_queue_depth)

    task = TaskRepository(db).get(task_id)
    assert task is not None
    job = jobs.create(
        type=JobType.RUN_TASK.value,
        idempotency_key=key,
        task_id=task_id,
        dedupe_key=task.idempotency_key,
        max_attempts=settings.job_max_attempts,
    )
    return jobs.mark_queued(job.id)


def enqueue_gc(db: Session, *, bucket: str) -> Job | None:
    """Enqueue one ``GC`` job for the given time bucket (e.g. an hour stamp);
    a duplicate bucket returns None so a worker restart doesn't pile them up."""
    jobs = JobRepository(db)
    key = f"gc:{bucket}"
    if jobs.get_by_idempotency_key(key) is not None:
        return None
    job = jobs.create(type=JobType.GC.value, idempotency_key=key, max_attempts=1)
    return jobs.mark_queued(job.id)


def claim_next(
    db: Session,
    *,
    worker_id: str,
    types: tuple[str, ...] = _DEFAULT_CLAIM_TYPES,
) -> Job | None:
    """The oldest eligible ``QUEUED`` job of ``types`` -- skipping any whose
    ``dedupe_key`` already has another active job, and any whose ``run_after``
    is still in the future (retry backoff). Sets ``worker_id`` and marks it
    RUNNING."""
    jobs = JobRepository(db)
    now = _now()
    active_dedupe = {
        j.dedupe_key
        for j in jobs.list_by_state(JobState.RUNNING.value)
        if j.dedupe_key is not None
    }
    for job in jobs.list_by_state(JobState.QUEUED.value, types=types):
        if job.dedupe_key is not None and job.dedupe_key in active_dedupe:
            continue
        run_after = _aware(job.run_after)
        if run_after is not None and run_after > now:
            continue
        jobs.set_worker(job.id, worker_id)
        running = jobs.mark_running(job.id)
        jobs.heartbeat(running.id)
        return jobs.get(running.id)
    return None


def reclaim_orphans(db: Session, *, stale_after_s: int) -> list[str]:
    """RUNNING jobs with no heartbeat (or start) newer than ``stale_after_s``
    (their worker died) are re-queued for resume. A live job that heartbeats at
    each stage is never reclaimed, however long it legitimately runs."""
    cutoff = _now() - timedelta(seconds=stale_after_s)
    jobs = JobRepository(db)
    reclaimed: list[str] = []
    for job in jobs.list_by_state(JobState.RUNNING.value):
        last = _aware(job.heartbeat_at) or _aware(job.started_at)
        if last is None:
            continue
        if last <= cutoff:
            jobs.set_worker(job.id, None)
            jobs.mark_queued(job.id)
            reclaimed.append(job.id)
    return reclaimed


def retry_or_fail(
    db: Session, job_id: str, *, error: dict, backoff_base_s: float
) -> float | None:
    """Retryable + attempts remain -> re-queue with a real ``run_after`` and
    return the backoff delay; otherwise mark FAILED and return ``None``."""
    jobs = JobRepository(db)
    job = jobs.get(job_id)
    assert job is not None
    retryable = (error.get("code") or "") not in _TERMINAL_ERROR_CODES
    if retryable and job.attempts < job.max_attempts:
        delay = backoff_base_s * (2 ** max(0, job.attempts - 1))
        jobs.mark_queued(job_id, run_after=_now() + timedelta(seconds=delay))
        return delay
    jobs.mark_failed(job_id, error=error)
    return None


def heartbeat(db: Session, job_id: str | None) -> None:
    JobRepository(db).heartbeat(job_id)


def set_checkpoint(db: Session, job_id: str | None, checkpoint: dict) -> None:
    if job_id is None:
        return
    repo = JobRepository(db)
    repo.set_checkpoint(job_id, checkpoint)
    repo.heartbeat(job_id)


def resume_stage(job: Job | None) -> str | None:
    if job is None or not job.last_checkpoint:
        return None
    return job.last_checkpoint.get("stage")


def is_job_cancelled(db: Session, job_id: str | None) -> bool:
    if job_id is None:
        return False
    job = JobRepository(db).get(job_id)
    return job is not None and job.state == JobState.CANCELLED.value
