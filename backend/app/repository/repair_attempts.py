"""Repository pattern for RepairAttempt data access.

Whole-ledger replace on a re-run (``refresh``): a repair loop is re-executed
from scratch, so its previous attempt rows are deleted and rewritten rather
than merged.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.repair_attempt import RepairAttempt


class RepairAttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_task(self, task_id: str) -> list[RepairAttempt]:
        stmt = (
            select(RepairAttempt)
            .where(RepairAttempt.task_id == task_id)
            .order_by(RepairAttempt.iteration)
        )
        return list(self._session.execute(stmt).scalars().all())

    def replace_for_task(self, task_id: str, rows: list[dict]) -> list[RepairAttempt]:
        self._session.execute(
            delete(RepairAttempt).where(RepairAttempt.task_id == task_id)
        )
        created = [
            RepairAttempt(
                task_id=task_id,
                iteration=r["iteration"],
                root_cause=r["root_cause"],
                proposal=r["proposal"],
                hypothesis=r["hypothesis"],
                edit_ops=r["edit_ops"],
                outcome=r["outcome"],
                score=r["score"],
                candidate_patch_id=r.get("candidate_patch_id"),
                targeted_execution_id=r.get("targeted_execution_id"),
                regression_execution_id=r.get("regression_execution_id"),
                run_summary=r.get("run_summary"),
            )
            for r in rows
        ]
        self._session.add_all(created)
        self._session.commit()
        return created
