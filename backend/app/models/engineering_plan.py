"""EngineeringPlan -- a versioned, validated engineering plan for a task. See
docs/DATA_MODEL.md Section 2.2 and docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17.

Versioned rather than upsert (unlike CodeMapping / ImpactAnalysis): a REVISE
verdict produces a new ``version`` for the same task, so the history of what was
proposed and why it was sent back is auditable. ``UniqueConstraint(task_id,
version)``.

``PlanValidation`` is an AI-output schema, not its own DATA_MODEL entity -- it is
stored here as ``validation`` (the full object) + ``validation_verdict`` (for
cheap filtering), both null until the validate endpoint runs.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class EngineeringPlan(Base, TimestampMixin):
    __tablename__ = "engineering_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    problem_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSON, nullable=False)
    files_to_inspect: Mapped[list] = mapped_column(JSON, nullable=False)
    files_to_modify: Mapped[list] = mapped_column(JSON, nullable=False)
    symbols_to_modify: Mapped[list] = mapped_column(JSON, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSON, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False)
    test_strategy: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    regression_risks: Mapped[list] = mapped_column(JSON, nullable=False)
    rollback_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)

    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_engineering_plan_task_version"),
        Index("ix_engineering_plan_task_id", "task_id"),
        Index("ix_engineering_plan_snapshot_id", "snapshot_id"),
    )
