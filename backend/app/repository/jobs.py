"""Repository pattern for Job data access.

Establishes the convention (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10:
"repository pattern for data access"); deliberately minimal -- create/get/list
only. Business logic that drives job state transitions belongs to a later
phase's orchestration layer, not here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
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

    def get_by_idempotency_key(self, key: str) -> Job | None:
        stmt = select(Job).where(Job.idempotency_key == key)
        return self._session.execute(stmt).scalar_one_or_none()

    def _filtered(
        self,
        *,
        state: str | None,
        type: str | None,
        task_id: str | None,
    ):
        stmt = select(Job)
        if state is not None:
            stmt = stmt.where(Job.state == state)
        if type is not None:
            stmt = stmt.where(Job.type == type)
        if task_id is not None:
            stmt = stmt.where(Job.task_id == task_id)
        return stmt

    def list(
        self,
        *,
        state: str | None = None,
        type: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        stmt = (
            self._filtered(state=state, type=type, task_id=task_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(stmt).scalars().all())

    def count(
        self,
        *,
        state: str | None = None,
        type: str | None = None,
        task_id: str | None = None,
    ) -> int:
        inner = self._filtered(state=state, type=type, task_id=task_id).subquery()
        return int(
            self._session.execute(
                select(func.count()).select_from(inner)
            ).scalar_one()
        )

    def list_for_task(self, task_id: str) -> list[Job]:
        stmt = (
            select(Job).where(Job.task_id == task_id).order_by(Job.id.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_by_state(self, state: str, *, types: tuple[str, ...] | None = None) -> list[Job]:
        stmt = select(Job).where(Job.state == state)
        if types is not None:
            stmt = stmt.where(Job.type.in_(types))
        stmt = stmt.order_by(Job.queued_at.asc().nullsfirst(), Job.id.asc())
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

    def set_checkpoint(self, job_id: str, checkpoint: dict) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.last_checkpoint = checkpoint
        self._session.commit()
        self._session.refresh(job)
        return job

    def set_progress(self, job_id: str, progress: float) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.progress = max(0.0, min(1.0, progress))
        self._session.commit()
        self._session.refresh(job)
        return job

    def set_worker(self, job_id: str, worker_id: str | None) -> Job:
        job = self._session.get(Job, job_id)
        assert job is not None
        job.worker_id = worker_id
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
