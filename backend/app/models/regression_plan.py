"""RegressionPlan -- the classified test set + per-stage selection for a task
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23).

One row per task (``UniqueConstraint(task_id)``), rewritten on recompute --
the same compute-once-cache shape Phase 8's ImpactAnalysis uses.

DATA_MODEL.md has no RegressionPlan entity and puts ``selection`` on
TestExecution; the implemented ``test_execution`` table has no such column, so
Phase 15 records the selection here rather than altering a committed table.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class RegressionPlan(Base, TimestampMixin):
    __tablename__ = "regression_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    changed_set: Mapped[dict] = mapped_column(JSON, nullable=False)
    # [{test_id, path, classification, rationale, covers_symbol, hops}]
    tests: Mapped[list] = mapped_column(JSON, nullable=False)
    # {stage: [test_id]}
    selection: Mapped[dict] = mapped_column(JSON, nullable=False)
    full_suite_count: Mapped[int] = mapped_column(Integer, nullable=False)
    subset_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    subset_risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("test_execution.id", ondelete="SET NULL"), nullable=True
    )
    baseline_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_failures: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_regression_plan_task"),
        Index("ix_regression_plan_task_id", "task_id"),
    )
