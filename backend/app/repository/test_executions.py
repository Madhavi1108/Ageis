"""Repository pattern for TestExecution data access. Versioned like
EngineeringPlan/Implementation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.test_execution import TestExecution


class TestExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, execution_id: str) -> TestExecution | None:
        return self._session.get(TestExecution, execution_id)

    def _next_version(self, task_id: str) -> int:
        current = self._session.execute(
            select(func.coalesce(func.max(TestExecution.version), 0)).where(
                TestExecution.task_id == task_id
            )
        ).scalar_one()
        return int(current) + 1

    def create_version(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        implementation_id: str,
        command: str,
        exit_code: int,
        outcome: str,
        results: list,
        reason: str | None,
        duration_ms: int,
        stdout_artifact_id: str | None,
        stderr_artifact_id: str | None,
    ) -> TestExecution:
        row = TestExecution(
            task_id=task_id,
            snapshot_id=snapshot_id,
            implementation_id=implementation_id,
            version=self._next_version(task_id),
            command=command,
            exit_code=exit_code,
            outcome=outcome,
            results=results,
            reason=reason,
            duration_ms=duration_ms,
            stdout_artifact_id=stdout_artifact_id,
            stderr_artifact_id=stderr_artifact_id,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def list_for_task(self, task_id: str) -> list[TestExecution]:
        stmt = (
            select(TestExecution)
            .where(TestExecution.task_id == task_id)
            .order_by(TestExecution.version.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_task_version(
        self, task_id: str, version: int
    ) -> TestExecution | None:
        stmt = select(TestExecution).where(
            TestExecution.task_id == task_id, TestExecution.version == version
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_latest_by_task(self, task_id: str) -> TestExecution | None:
        stmt = (
            select(TestExecution)
            .where(TestExecution.task_id == task_id)
            .order_by(TestExecution.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()
