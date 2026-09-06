"""TestCase -- one generated test (docs/AEGIS_IMPLEMENTATION_PLAN.md Section
19). Denormalized (task_id/snapshot_id/implementation_id/version live
directly on each row, no separate "generation run" parent table) since the
plan names a single Model: TestCase; ``version`` groups the rows created by
one generation run for a task, the same versioning pattern as
EngineeringPlan/Implementation, computed as ``max(version) + 1`` per task.
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


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_case"

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

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_symbol: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    invalid_reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "task_id", "version", "name", name="uq_test_case_task_version_name"
        ),
        Index("ix_test_case_task_id", "task_id"),
        Index("ix_test_case_task_version", "task_id", "version"),
    )
