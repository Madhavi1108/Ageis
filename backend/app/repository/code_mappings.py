"""Repository pattern for CodeMapping data access.

One row per task, rewritten in place on recompute -- upsert, not
delete-then-recreate (same shape as AnalysisRepository).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_mapping import CodeMapping


class CodeMappingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> CodeMapping | None:
        stmt = select(CodeMapping).where(CodeMapping.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        candidates: list,
        related_tests: list,
        dependencies: list,
        overall_confidence: float,
        semantic_available: bool,
        model_version: str,
    ) -> CodeMapping:
        row = self.get_by_task(task_id)
        if row is None:
            row = CodeMapping(task_id=task_id)
            self._session.add(row)
        row.snapshot_id = snapshot_id
        row.candidates = candidates
        row.related_tests = related_tests
        row.dependencies = dependencies
        row.overall_confidence = overall_confidence
        row.semantic_available = semantic_available
        row.model_version = model_version
        self._session.commit()
        self._session.refresh(row)
        return row
