"""Repository pattern for Job data access.

Establishes the convention (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10:
"repository pattern for data access"); deliberately minimal -- create/get/list
only. Business logic that drives job state transitions belongs to a later
phase's orchestration layer, not here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job, JobState


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, *, type: str, idempotency_key: str, task_id: str | None = None
    ) -> Job:
        job = Job(
            type=type,
            idempotency_key=idempotency_key,
            task_id=task_id,
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
