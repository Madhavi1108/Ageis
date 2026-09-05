"""Repository pattern for Job data access.

Establishes the convention (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10:
"repository pattern for data access"); deliberately minimal -- create/get/list
only. Business logic that drives job state transitions belongs to a later
phase's orchestration layer, not here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job, JobState


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        type: str,
        idempotency_key: str,
        task_id: str | None = None,
        dedupe_key: str | None = None,
    ) -> Job:
        job = Job(
            type=type,
            idempotency_key=idempotency_key,
            task_id=task_id,
            dedupe_key=dedupe_key,
            state=JobState.PENDING.value,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._session.get(Job, job_id)

    def list(self, *, limit: int = 100) -> list[Job]:
        stmt = select(Job).order_by(Job.id.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def list_for_task(self, task_id: str) -> list[Job]:
        stmt = (
            select(Job).where(Job.task_id == task_id).order_by(Job.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    # Thin state + timestamp transitions -- still no business logic (no retry/backoff/
    # dedupe decisions here, that's a later orchestration-layer concern).

    def mark_queued(self, job_id: str) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.state = JobState.QUEUED.value
        job.queued_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_cancelled(self, job_id: str) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.state = JobState.CANCELLED.value
        job.finished_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_running(self, job_id: str) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.state = JobState.RUNNING.value
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_succeeded(self, job_id: str) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.state = JobState.SUCCEEDED.value
        job.progress = 1.0
        job.finished_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_failed(self, job_id: str, *, error: dict) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.state = JobState.FAILED.value
        job.error = error
        job.finished_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job
