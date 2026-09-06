"""RiskAssessment + RepositoryHealth -- the Phase 17 Risk & Confidence Engine
snapshots (docs/DATA_MODEL.md Section 2.4, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 25).

``RiskAssessment`` is the per-task PCS + CRS + Task-Specific Risk Profile
snapshot, matching DATA_MODEL.md Section 2.4 -- one row per task
(``UniqueConstraint(task_id)``), rewritten on recompute, the same
compute-once-cache shape Phase 8's ImpactAnalysis / Phase 16's Review use.

``RepositoryHealth`` (the Repository Health Profile) has **no DATA_MODEL
entity** -- it is a deliberate extension keyed on ``snapshot_id``, the same
precedent Phase 15 set for ``regression_plan`` (whose docstring notes
"DATA_MODEL.md has no RegressionPlan entity ... Phase 15 records ... here").
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    implementation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patch.id", ondelete="SET NULL"), nullable=True
    )

    pcs_value: Mapped[int] = mapped_column(Integer, nullable=False)
    pcs_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    pcs_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)

    crs_value: Mapped[int] = mapped_column(Integer, nullable=False)
    crs_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    crs_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)

    # RHP restricted to the current impact set
    task_risk_profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    # list of the hard gate(s) that forced PCS to BLOCKED, or [] / null
    hard_gate: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_risk_assessment_task"),
        Index("ix_risk_assessment_task_id", "task_id"),
        Index("ix_risk_assessment_patch_id", "patch_id"),
    )


class RepositoryHealth(Base, TimestampMixin):
    __tablename__ = "repository_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    # plain indexed column, no FK -- matches job.task_id's precedent
    repository_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    rhp_value: Mapped[int] = mapped_column(Integer, nullable=False)
    rhp_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    subscores: Mapped[list] = mapped_column(JSON, nullable=False)
    risky_modules: Mapped[list] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", name="uq_repository_health_snapshot"),
        Index("ix_repository_health_snapshot_id", "snapshot_id"),
    )
