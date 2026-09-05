"""Repository pattern for ImpactAnalysis data access.

One row per task, rewritten in place on recompute -- upsert (mirrors
CodeMappingRepository / AnalysisRepository).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.impact_analysis import ImpactAnalysis


class ImpactAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> ImpactAnalysis | None:
        stmt = select(ImpactAnalysis).where(ImpactAnalysis.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        changed_set: dict,
        blast_radius: dict,
        callers: list,
        related_tests: list,
        public_api_touched: list,
        config_refs: list,
        db_refs: list,
        regression_areas: list,
        risk_signal_bundle: dict,
    ) -> ImpactAnalysis:
        row = self.get_by_task(task_id)
        if row is None:
            row = ImpactAnalysis(task_id=task_id)
            self._session.add(row)
        row.snapshot_id = snapshot_id
        row.changed_set = changed_set
        row.blast_radius = blast_radius
        row.callers = callers
        row.related_tests = related_tests
        row.public_api_touched = public_api_touched
        row.config_refs = config_refs
        row.db_refs = db_refs
        row.regression_areas = regression_areas
        row.risk_signal_bundle = risk_signal_bundle
        self._session.commit()
        self._session.refresh(row)
        return row
