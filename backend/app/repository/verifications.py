"""Repository pattern for Verification data access.

A history chain, not an upsert (docs/DATA_MODEL.md Section 2.4): ``create_version``
inserts a new row and links the previous live row's ``superseded_by`` to it.
``get_by_task`` returns the single live row (``superseded_by IS NULL``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.verification import Verification


class VerificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> Verification | None:
        stmt = (
            select(Verification)
            .where(
                Verification.task_id == task_id,
                Verification.superseded_by.is_(None),
            )
            .order_by(Verification.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_task(self, task_id: str) -> list[Verification]:
        stmt = (
            select(Verification)
            .where(Verification.task_id == task_id)
            .order_by(Verification.created_at.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def create_version(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        implementation_version: int,
        verdict: str,
        criteria: list,
        plan_alignment: dict,
        trace: dict,
        trace_artifact_id: str | None,
        replay_fidelity: float | None,
        confidence: dict,
        resulting_state: str,
        model_version: str,
        decision: dict | None = None,
    ) -> Verification:
        previous = self.get_by_task(task_id)
        row = Verification(
            task_id=task_id,
            snapshot_id=snapshot_id,
            implementation_version=implementation_version,
            verdict=verdict,
            criteria=criteria,
            plan_alignment=plan_alignment,
            trace=trace,
            trace_artifact_id=trace_artifact_id,
            replay_fidelity=replay_fidelity,
            confidence=confidence,
            resulting_state=resulting_state,
            decision=decision,
            model_version=model_version,
        )
        self._session.add(row)
        self._session.flush()  # assign row.id before linking the supersede chain
        if previous is not None:
            previous.superseded_by = row.id
        self._session.commit()
        self._session.refresh(row)
        return row
