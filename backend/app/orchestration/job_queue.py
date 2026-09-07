"""Job queue primitives for the Phase 21 worker
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

The default worker is a single asyncio process -> a single SQLite writer, so a
plain ``SELECT ... LIMIT 1`` + update is a safe claim. The functions are the
abstraction seam if a distributed queue (RQ/Celery/arq) is swapped in later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.job import Job, JobState, JobType
from app.repository.jobs import JobRepository
from app.repository.tasks import TaskRepository

_ACTIVE_JOB_STATES = (JobState.QUEUED.value, JobState.RUNNING.value)


def enqueue_run(db: Session, task_id: str) -> Job:
    """Idempotent enqueue for ``POST /tasks/{id}/run``: a stable
    ``run:{task_id}`` key + a content ``dedupe_key``. A second call while the
    first run is live returns the existing job rather than raising on the
    unique constraint."""
    jobs = JobRepository(db)
    key = f"run:{task_id}"
    existing = jobs.get_by_idempotency_key(key)
    if existing is not None:
        return existing
    task = TaskRepository(db).get(task_id)
    assert task is not None
    job = jobs.create(
        type=JobType.RUN_TASK.value,
        idempotency_key=key,
        task_id=task_id,
        dedupe_key=task.idempotency_key,
    )
    return jobs.mark_queued(job.id)


def claim_next(
    db: Session,
    *,
    worker_id: str,
    types: tuple[str, ...] = (JobType.RUN_TASK.value,),
) -> Job | None:
    """The oldest ``QUEUED`` job of ``types``, skipping any whose ``dedupe_key``
    already has another active job. Sets ``worker_id`` and marks it RUNNING."""
    jobs = JobRepository(db)
    active_dedupe = {
        j.dedupe_key
        for j in jobs.list_by_state(JobState.RUNNING.value)
        if j.dedupe_key is not None
    }
    for job in jobs.list_by_state(JobState.QUEUED.value, types=types):
        if job.dedupe_key is not None and job.dedupe_key in active_dedupe:
            continue
        jobs.set_worker(job.id, worker_id)
        return jobs.mark_running(job.id)
    return None


def reclaim_orphans(db: Session, *, stale_after_s: int) -> list[str]:
    """RUNNING jobs whose ``started_at`` is older than ``stale_after_s`` (their
    worker died) are re-queued for resume. Returns the reclaimed ids."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_s)
    jobs = JobRepository(db)
    reclaimed: list[str] = []
    for job in jobs.list_by_state(JobState.RUNNING.value):
        started = job.started_at
        if started is None:
            continue
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started <= cutoff:
            jobs.set_worker(job.id, None)
            jobs.mark_queued(job.id)
            reclaimed.append(job.id)
    return reclaimed


def retry_or_fail(
    db: Session, job_id: str, *, error: dict, backoff_base_s: float
) -> float | None:
    """If retries remain, re-queue the job and return the backoff delay;
    otherwise mark it FAILED and return ``None``."""
    jobs = JobRepository(db)
    job = jobs.get(job_id)
    assert job is not None
    if job.attempts < job.max_attempts:
        jobs.mark_queued(job_id)
        return backoff_base_s * (2 ** max(0, job.attempts - 1))
    jobs.mark_failed(job_id, error=error)
    return None


def set_checkpoint(db: Session, job_id: str | None, checkpoint: dict) -> None:
    if job_id is None:
        return
    JobRepository(db).set_checkpoint(job_id, checkpoint)


def resume_stage(job: Job | None) -> str | None:
    if job is None or not job.last_checkpoint:
        return None
    return job.last_checkpoint.get("stage")


def is_job_cancelled(db: Session, job_id: str | None) -> bool:
    if job_id is None:
        return False
    job = JobRepository(db).get(job_id)
    return job is not None and job.state == JobState.CANCELLED.value
