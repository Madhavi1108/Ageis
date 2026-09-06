"""Failure + Investigation -- structured failure data captured from a failing
TestExecution (docs/DATA_MODEL.md Section 2.3, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 21).

``Failure`` is one row per failing test in an execution. ``Investigation`` is the
``FailureAnalysis`` bundle for that execution -- one row per (task, execution),
rewritten in place when recomputed (``UniqueConstraint(task_id, execution_id)``,
upsert), the same compute-once-cache shape Phase 8's ImpactAnalysis uses.

No root cause is stored here -- ``facts`` / ``inferences`` are parsed data and
hedged candidate signals only. Root-cause analysis is Phase 14.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class Failure(Base):
    __tablename__ = "failure"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_execution.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    test_name: Mapped[str] = mapped_column(String(512), nullable=False)
    failure_type: Mapped[str] = mapped_column(String(24), nullable=False)
    traceback_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="SET NULL"), nullable=True
    )
    # [{file, lineno, symbol_id, in_diff}]
    frames: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_failure_task_id", "task_id"),
        Index("ix_failure_execution_id", "execution_id"),
    )


class Investigation(Base, TimestampMixin):
    __tablename__ = "investigation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_execution.id", ondelete="RESTRICT"),
        nullable=False,
    )
    failure_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    # {code_slices, diff_hunks, related_tests, recent_commits}
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    facts: Mapped[list] = mapped_column(JSON, nullable=False)
    inferences: Mapped[list] = mapped_column(JSON, nullable=False)
    classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Denormalised copy of the analysed failure records, so the API response can
    # be rebuilt without re-reading every Failure row.
    failures: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "task_id", "execution_id", name="uq_investigation_task_execution"
        ),
        Index("ix_investigation_task_id", "task_id"),
    )
