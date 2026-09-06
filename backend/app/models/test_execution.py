"""TestExecution -- one sandbox run of a task's generated tests
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20, docs/EXECUTION_MODEL.md
Section 4). Versioned like EngineeringPlan/Implementation: each run writes a
new row, `version = max(version) + 1` per task.
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


class TestExecution(Base, TimestampMixin):
    __tablename__ = "test_execution"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    implementation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("implementation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    command: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    results: Mapped[list] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stdout_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="SET NULL"), nullable=True
    )
    stderr_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id", "version", name="uq_test_execution_task_version"
        ),
        Index("ix_test_execution_task_id", "task_id"),
    )
