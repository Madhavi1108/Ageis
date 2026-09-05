"""Repository pattern for TaskStep data access. Mirrors JobRepository's shape.

``append`` computes the next ``seq`` as ``max(seq) + 1`` for the task; single-writer
per task in Phase 6 (the API handler), so no locking is needed here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task_step import TaskStep


class TaskStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        *,
        task_id: str,
        state: str,
        agent: str | None = None,
        input_ref: str | None = None,
        output_ref: str | None = None,
    ) -> TaskStep:
        next_seq = (
            self._session.execute(
                select(func.coalesce(func.max(TaskStep.seq), 0)).where(
                    TaskStep.task_id == task_id
                )
            ).scalar_one()
            + 1
        )
        step = TaskStep(
            task_id=task_id,
            seq=next_seq,
            state=state,
            agent=agent,
            input_ref=input_ref,
            output_ref=output_ref,
        )
        self._session.add(step)
        self._session.commit()
        self._session.refresh(step)
        return step

    def close_current(self, task_id: str, *, error: dict | None = None) -> TaskStep | None:
        """Close the most recent still-open step for a task (set exited_at + duration_ms)."""
        stmt = (
            select(TaskStep)
            .where(TaskStep.task_id == task_id, TaskStep.exited_at.is_(None))
            .order_by(TaskStep.seq.desc())
            .limit(1)
        )
        step = self._session.execute(stmt).scalar_one_or_none()
        if step is None:
            return None
        now = datetime.now(timezone.utc)
        step.exited_at = now
        entered = step.entered_at
        if entered is not None:
            if entered.tzinfo is None:
                entered = entered.replace(tzinfo=timezone.utc)
            step.duration_ms = int((now - entered).total_seconds() * 1000)
        if error is not None:
            step.error = error
        self._session.commit()
        self._session.refresh(step)
        return step

    def list_for_task(self, task_id: str) -> list[TaskStep]:
        stmt = (
            select(TaskStep)
            .where(TaskStep.task_id == task_id)
            .order_by(TaskStep.seq.asc())
        )
        return list(self._session.execute(stmt).scalars().all())
