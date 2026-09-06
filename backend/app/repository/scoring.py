"""Repository pattern for RiskAssessment + RepositoryHealth data access.

Both are one-row-per-key upserts (rewritten on recompute), mirroring
ReviewRepository / AnalysisRepository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scoring import RepositoryHealth, RiskAssessment


class RiskAssessmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> RiskAssessment | None:
        stmt = select(RiskAssessment).where(RiskAssessment.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        implementation_version: int,
        patch_id: str | None,
        pcs_value: int,
        pcs_classification: str,
        pcs_breakdown: dict,
        crs_value: int,
        crs_classification: str,
        crs_breakdown: dict,
        task_risk_profile: dict,
        hard_gate: list | None,
        model_version: str,
    ) -> RiskAssessment:
        row = self.get_by_task(task_id)
        if row is None:
            row = RiskAssessment(task_id=task_id)
            self._session.add(row)
        row.snapshot_id = snapshot_id
        row.implementation_version = implementation_version
        row.patch_id = patch_id
        row.pcs_value = pcs_value
        row.pcs_classification = pcs_classification
        row.pcs_breakdown = pcs_breakdown
        row.crs_value = crs_value
        row.crs_classification = crs_classification
        row.crs_breakdown = crs_breakdown
        row.task_risk_profile = task_risk_profile
        row.hard_gate = hard_gate
        row.model_version = model_version
        self._session.commit()
        self._session.refresh(row)
        return row


class RepositoryHealthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_snapshot(self, snapshot_id: str) -> RepositoryHealth | None:
        stmt = select(RepositoryHealth).where(
            RepositoryHealth.snapshot_id == snapshot_id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        snapshot_id: str,
        *,
        repository_id: str,
        rhp_value: int,
        rhp_classification: str,
        subscores: list,
        risky_modules: list,
        model_version: str,
    ) -> RepositoryHealth:
        row = self.get_by_snapshot(snapshot_id)
        if row is None:
            row = RepositoryHealth(snapshot_id=snapshot_id)
            self._session.add(row)
        row.repository_id = repository_id
        row.rhp_value = rhp_value
        row.rhp_classification = rhp_classification
        row.subscores = subscores
        row.risky_modules = risky_modules
        row.model_version = model_version
        self._session.commit()
        self._session.refresh(row)
        return row
