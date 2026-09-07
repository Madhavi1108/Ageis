"""Repository pattern for EngineeringMemory data access. One upserted row per
task (``Task 1--1 EngineeringMemory``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.engineering_memory import EngineeringMemory


class EngineeringMemoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> EngineeringMemory | None:
        stmt = select(EngineeringMemory).where(EngineeringMemory.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list(
        self, *, repository_id: str | None = None, limit: int = 500
    ) -> list[EngineeringMemory]:
        stmt = select(EngineeringMemory)
        if repository_id is not None:
            stmt = stmt.where(EngineeringMemory.repository_id == repository_id)
        stmt = stmt.order_by(EngineeringMemory.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def upsert(
        self,
        task_id: str,
        *,
        repository_id: str,
        issue_text_sanitized: str,
        touched_symbols: list,
        touched_files: list,
        failure_signatures: list,
        fix_summary: str,
        plan_ref: dict,
        patch_ref: str | None,
        review_summary: dict,
        verification_verdict: str | None,
        outcome: str,
    ) -> EngineeringMemory:
        row = self.get_by_task(task_id)
        if row is None:
            row = EngineeringMemory(task_id=task_id)
            self._session.add(row)
        row.repository_id = repository_id
        row.issue_text_sanitized = issue_text_sanitized
        row.touched_symbols = touched_symbols
        row.touched_files = touched_files
        row.failure_signatures = failure_signatures
        row.fix_summary = fix_summary
        row.plan_ref = plan_ref
        row.patch_ref = patch_ref
        row.review_summary = review_summary
        row.verification_verdict = verification_verdict
        row.outcome = outcome
        self._session.commit()
        self._session.refresh(row)
        return row
