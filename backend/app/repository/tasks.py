"""Repository pattern for Task data access. Mirrors JobRepository's shape.

State transitions here are thin (``set_state`` writes the column + timestamp);
the decision of *which* transition is legal lives in app/services/tasks.py, and
the full state machine lands in Phase 21.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskState


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        repository_id: str,
        task_type: str,
        title: str,
        description_sanitized: str,
        idempotency_key: str,
        issue_id: str | None = None,
        snapshot_id: str | None = None,
        constraints: dict | None = None,
        priority: str = "NORMAL",
        allowed_paths: list | None = None,
        created_by: str = "api",
    ) -> Task:
        task = Task(
            repository_id=repository_id,
            task_type=task_type,
            title=title,
            description_sanitized=description_sanitized,
            idempotency_key=idempotency_key,
            issue_id=issue_id,
            snapshot_id=snapshot_id,
            constraints=constraints,
            priority=priority,
            allowed_paths=allowed_paths,
            created_by=created_by,
            state=TaskState.PENDING.value,
        )
        self._session.add(task)
        self._session.commit()
        self._session.refresh(task)
        return task

    def get(self, task_id: str) -> Task | None:
        return self._session.get(Task, task_id)

    def get_by_idempotency_key(
        self, repository_id: str, idempotency_key: str
    ) -> Task | None:
        stmt = select(Task).where(
            Task.repository_id == repository_id,
            Task.idempotency_key == idempotency_key,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _filtered(
        self,
        *,
        repository_id: str | None,
        state: str | None,
        task_type: str | None,
    ):
        stmt = select(Task)
        if repository_id is not None:
            stmt = stmt.where(Task.repository_id == repository_id)
        if state is not None:
            stmt = stmt.where(Task.state == state)
        if task_type is not None:
            stmt = stmt.where(Task.task_type == task_type)
        return stmt

    def list(
        self,
        *,
        repository_id: str | None = None,
        state: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            self._filtered(
                repository_id=repository_id, state=state, task_type=task_type
            )
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(stmt).scalars().all())

    def count(
        self,
        *,
        repository_id: str | None = None,
        state: str | None = None,
        task_type: str | None = None,
    ) -> int:
        inner = self._filtered(
            repository_id=repository_id, state=state, task_type=task_type
        ).subquery()
        return int(
            self._session.execute(select(func.count()).select_from(inner)).scalar_one()
        )

    def set_snapshot_id(self, task_id: str, snapshot_id: str) -> Task:
        """Bind a task to the repository snapshot a later stage will operate on.
        Phase 7 (issue -> code mapping) is the first stage to need this; the
        ``Task.snapshot_id`` column has been nullable and unused since Phase 6
        exactly for this."""
        task = self._session.get(Task, task_id)
        assert task is not None
        task.snapshot_id = snapshot_id
        self._session.commit()
        self._session.refresh(task)
        return task

    def set_state(
        self, task_id: str, state: str, *, terminal_reason: str | None = None
    ) -> Task:
        task = self._session.get(Task, task_id)
        assert task is not None
        task.state = state
        if terminal_reason is not None:
            task.terminal_reason = terminal_reason
        self._session.commit()
        self._session.refresh(task)
        return task
