"""Implementation + Patch -- the applied edit-ops and their generated diff for
a task. See docs/DECISIONS/ADR-0008-patch-representation.md and
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18.

``Implementation`` is versioned like ``EngineeringPlan`` (a re-run produces a
new version, auditable history of what was attempted). ``Patch`` is a
separate row (not folded into ``Implementation``) because ADR-0008 anticipates
multiple candidate patches per implementation once the Phase 14 repair loop
lands (``is_candidate=true`` rows, kept by (failing_count, regression_failures,
diff_size)); today exactly one non-candidate Patch is created per
Implementation. The diff text itself lives in an ``Artifact`` row
(``kind=DIFF``), not a DB TEXT column (ADR-0008's "alternatives considered").
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class Implementation(Base, TimestampMixin):
    __tablename__ = "implementation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    edit_ops: Mapped[list] = mapped_column(JSON, nullable=False)
    scope_violations: Mapped[list] = mapped_column(JSON, nullable=False)
    traceability: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_implementation_task_version"),
        Index("ix_implementation_task_id", "task_id"),
        Index("ix_implementation_snapshot_id", "snapshot_id"),
        Index("ix_implementation_plan_id", "plan_id"),
    )


class Patch(Base, TimestampMixin):
    __tablename__ = "patch"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    implementation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("implementation.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="RESTRICT"), nullable=False
    )
    touched_paths: Mapped[list] = mapped_column(JSON, nullable=False)
    diff_size: Mapped[int] = mapped_column(Integer, nullable=False)
    is_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_patch_implementation_id", "implementation_id"),
    )
