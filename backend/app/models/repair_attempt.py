"""RepairAttempt -- one bounded repair iteration (docs/DATA_MODEL.md Section 2.3,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 22).

One row per iteration, ``UniqueConstraint(task_id, iteration)``. The run-level
result (REPAIRED / SAFE_STOP, the surviving edit-ops, the SAFE_STOP payload) is
derived from these rows + a SAFE_STOP-kind Artifact -- there is no separate
"repair run" table (matches DATA_MODEL).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class RepairAttempt(Base):
    __tablename__ = "repair_attempt"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposal: Mapped[dict] = mapped_column(JSON, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    edit_ops: Mapped[list] = mapped_column(JSON, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    # {failing_count, regression_failures, diff_size}
    score: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate_patch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patch.id", ondelete="SET NULL"), nullable=True
    )
    targeted_execution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("test_execution.id", ondelete="SET NULL"), nullable=True
    )
    regression_execution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("test_execution.id", ondelete="SET NULL"), nullable=True
    )
    # Set only on the terminal row of a run: {outcome, best_iteration,
    # final_edit_ops, safe_stop}. Lets GET /tasks/{id}/repairs serve the cached
    # aggregate without a separate "repair run" table.
    run_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id", "iteration", name="uq_repair_attempt_task_iteration"
        ),
        Index("ix_repair_attempt_task_id", "task_id"),
    )
