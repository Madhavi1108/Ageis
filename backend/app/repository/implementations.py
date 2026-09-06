"""Repository pattern for Implementation data access.

Versioned, not upsert (mirrors EngineeringPlanRepository): each generation
run writes a new row with ``version = max(version) + 1`` for the task.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.implementation import Implementation


class ImplementationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, implementation_id: str) -> Implementation | None:
        return self._session.get(Implementation, implementation_id)

    def get_latest_by_task(self, task_id: str) -> Implementation | None:
        stmt = (
            select(Implementation)
            .where(Implementation.task_id == task_id)
            .order_by(Implementation.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_task_version(
        self, task_id: str, version: int
    ) -> Implementation | None:
        stmt = select(Implementation).where(
            Implementation.task_id == task_id,
            Implementation.version == version,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _next_version(self, task_id: str) -> int:
        current = self._session.execute(
            select(func.coalesce(func.max(Implementation.version), 0)).where(
                Implementation.task_id == task_id
            )
        ).scalar_one()
        return int(current) + 1

    def create_version(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        plan_id: str,
        edit_ops: list,
        scope_violations: list,
        traceability: dict,
        source: str,
    ) -> Implementation:
        row = Implementation(
            task_id=task_id,
            snapshot_id=snapshot_id,
            plan_id=plan_id,
            version=self._next_version(task_id),
            edit_ops=edit_ops,
            scope_violations=scope_violations,
            traceability=traceability,
            source=source,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row
