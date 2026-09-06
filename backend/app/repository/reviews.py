"""Repository pattern for Review + ReviewFinding data access."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewFinding


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> Review | None:
        stmt = select(Review).where(Review.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        implementation_version: int,
        findings: list,
        static_tools_run: list,
        policy_gaps: list,
        counts: dict,
        blocking: bool,
    ) -> Review:
        row = self.get_by_task(task_id)
        if row is None:
            row = Review(task_id=task_id)
            self._session.add(row)
        row.snapshot_id = snapshot_id
        row.implementation_version = implementation_version
        row.findings = findings
        row.static_tools_run = static_tools_run
        row.policy_gaps = policy_gaps
        row.counts = counts
        row.blocking = blocking
        self._session.commit()
        self._session.refresh(row)
        return row


class ReviewFindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_task(self, task_id: str, rows: list[dict]) -> list[ReviewFinding]:
        self._session.execute(
            delete(ReviewFinding).where(ReviewFinding.task_id == task_id)
        )
        created = [
            ReviewFinding(
                task_id=task_id,
                source=r["source"],
                category=r["category"],
                severity=r["severity"],
                file=r.get("file"),
                line_start=r.get("line_start"),
                line_end=r.get("line_end"),
                description=r["description"],
                evidence=r["evidence"],
                recommendation=r["recommendation"],
                confidence=r["confidence"],
                status=r.get("status", "OPEN"),
            )
            for r in rows
        ]
        self._session.add_all(created)
        self._session.commit()
        return created

    def list_for_task(self, task_id: str) -> list[ReviewFinding]:
        stmt = select(ReviewFinding).where(ReviewFinding.task_id == task_id)
        return list(self._session.execute(stmt).scalars().all())
