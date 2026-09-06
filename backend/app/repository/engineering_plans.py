"""Repository pattern for EngineeringPlan data access.

Versioned, not upsert: ``create_version`` always writes a new row with
``version = max(version) + 1`` for the task. ``set_validation`` is the only
in-place mutation (recording the validate endpoint's verdict).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.engineering_plan import EngineeringPlan


class EngineeringPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, plan_id: str) -> EngineeringPlan | None:
        return self._session.get(EngineeringPlan, plan_id)

    def get_latest_by_task(self, task_id: str) -> EngineeringPlan | None:
        stmt = (
            select(EngineeringPlan)
            .where(EngineeringPlan.task_id == task_id)
            .order_by(EngineeringPlan.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_task_version(self, task_id: str, version: int) -> EngineeringPlan | None:
        stmt = select(EngineeringPlan).where(
            EngineeringPlan.task_id == task_id,
            EngineeringPlan.version == version,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _next_version(self, task_id: str) -> int:
        current = self._session.execute(
            select(func.coalesce(func.max(EngineeringPlan.version), 0)).where(
                EngineeringPlan.task_id == task_id
            )
        ).scalar_one()
        return int(current) + 1

    def create_version(
        self,
        task_id: str,
        *,
        snapshot_id: str,
        plan: dict,
    ) -> EngineeringPlan:
        row = EngineeringPlan(
            task_id=task_id,
            snapshot_id=snapshot_id,
            version=self._next_version(task_id),
            problem_interpretation=plan["problem_interpretation"],
            assumptions=plan["assumptions"],
            files_to_inspect=plan["files_to_inspect"],
            files_to_modify=plan["files_to_modify"],
            symbols_to_modify=plan["symbols_to_modify"],
            dependencies=plan["dependencies"],
            steps=plan["steps"],
            test_strategy=plan["test_strategy"],
            expected_behavior=plan["expected_behavior"],
            regression_risks=plan["regression_risks"],
            rollback_strategy=plan["rollback_strategy"],
            source=plan["source"],
            confidence=plan["confidence"],
            evidence=plan["evidence"],
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def set_validation(
        self, plan_id: str, *, validation: dict, verdict: str
    ) -> EngineeringPlan:
        row = self._session.get(EngineeringPlan, plan_id)
        assert row is not None
        row.validation = validation
        row.validation_verdict = verdict
        self._session.commit()
        self._session.refresh(row)
        return row
