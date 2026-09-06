"""Repository pattern for RegressionPlan data access. One row per task, upsert."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.regression_plan import RegressionPlan


class RegressionPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_task(self, task_id: str) -> RegressionPlan | None:
        stmt = select(RegressionPlan).where(RegressionPlan.task_id == task_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        mode: str,
        changed_set: dict,
        tests: list,
        selection: dict,
        full_suite_count: int,
        subset_justification: str | None,
        subset_risk_note: str | None,
        execution_id: str | None = None,
        baseline_execution_id: str | None = None,
        new_failures: list | None = None,
    ) -> RegressionPlan:
        row = self.get_by_task(task_id)
        if row is None:
            row = RegressionPlan(task_id=task_id)
            self._session.add(row)
        row.snapshot_id = snapshot_id
        row.mode = mode
        row.changed_set = changed_set
        row.tests = tests
        row.selection = selection
        row.full_suite_count = full_suite_count
        row.subset_justification = subset_justification
        row.subset_risk_note = subset_risk_note
        row.execution_id = execution_id
        row.baseline_execution_id = baseline_execution_id
        row.new_failures = new_failures or []
        self._session.commit()
        self._session.refresh(row)
        return row
