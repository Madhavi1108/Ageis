"""Repository pattern for TestCase data access.

Versioned like EngineeringPlan/Implementation, but a batch of rows per
version (one generation run proposes several cases at once).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.test_case import TestCase


class TestCaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _next_version(self, task_id: str) -> int:
        current = self._session.execute(
            select(func.coalesce(func.max(TestCase.version), 0)).where(
                TestCase.task_id == task_id
            )
        ).scalar_one()
        return int(current) + 1

    def create_version(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        implementation_id: str,
        cases: list[dict],
    ) -> list[TestCase]:
        version = self._next_version(task_id)
        rows = [
            TestCase(
                task_id=task_id,
                snapshot_id=snapshot_id,
                implementation_id=implementation_id,
                version=version,
                name=c["name"],
                path=c["path"],
                target_symbol=c["target_symbol"],
                kind=c["kind"],
                rationale=c["rationale"],
                code=c["code"],
                evidence=c["evidence"],
                status=c["status"],
                invalid_reason=c.get("invalid_reason"),
            )
            for c in cases
        ]
        self._session.add_all(rows)
        self._session.commit()
        for row in rows:
            self._session.refresh(row)
        return rows

    def list_latest_by_task(self, task_id: str) -> list[TestCase]:
        latest = self._session.execute(
            select(func.max(TestCase.version)).where(TestCase.task_id == task_id)
        ).scalar_one()
        if latest is None:
            return []
        return self.list_by_task_version(task_id, latest)

    def list_by_task_version(self, task_id: str, version: int) -> list[TestCase]:
        stmt = (
            select(TestCase)
            .where(TestCase.task_id == task_id, TestCase.version == version)
            .order_by(TestCase.name)
        )
        return list(self._session.execute(stmt).scalars().all())

    def latest_version(self, task_id: str) -> int | None:
        return self._session.execute(
            select(func.max(TestCase.version)).where(TestCase.task_id == task_id)
        ).scalar_one()
