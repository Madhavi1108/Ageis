"""Repository pattern for Failure + Investigation data access.

``Failure`` rows are write-once per investigation run (deleted + recreated when
an investigation is recomputed). ``Investigation`` is upsert-per-(task,
execution) -- the compute-once cache.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.failure import Failure, Investigation


class FailureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_execution(
        self, task_id: str, execution_id: str, rows: list[dict]
    ) -> list[Failure]:
        self._session.execute(
            delete(Failure).where(
                Failure.task_id == task_id, Failure.execution_id == execution_id
            )
        )
        created = [
            Failure(
                task_id=task_id,
                execution_id=execution_id,
                test_name=r["test_name"],
                failure_type=r["failure_type"],
                traceback_artifact_id=r.get("traceback_artifact_id"),
                frames=r["frames"],
            )
            for r in rows
        ]
        self._session.add_all(created)
        self._session.commit()
        return created

    def list_for_execution(self, execution_id: str) -> list[Failure]:
        stmt = select(Failure).where(Failure.execution_id == execution_id)
        return list(self._session.execute(stmt).scalars().all())


class InvestigationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task_execution(
        self, task_id: str, execution_id: str
    ) -> Investigation | None:
        stmt = select(Investigation).where(
            Investigation.task_id == task_id,
            Investigation.execution_id == execution_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_latest_by_task(self, task_id: str) -> Investigation | None:
        stmt = (
            select(Investigation)
            .where(Investigation.task_id == task_id)
            .order_by(Investigation.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        execution_id: str,
        *,
        failure_ids: list,
        evidence: dict,
        facts: list,
        inferences: list,
        classification: dict,
        failures: list,
        summary: str,
    ) -> Investigation:
        row = self.get_by_task_execution(task_id, execution_id)
        if row is None:
            row = Investigation(task_id=task_id, execution_id=execution_id)
            self._session.add(row)
        row.failure_ids = failure_ids
        row.evidence = evidence
        row.facts = facts
        row.inferences = inferences
        row.classification = classification
        row.failures = failures
        row.summary = summary
        self._session.commit()
        self._session.refresh(row)
        return row
