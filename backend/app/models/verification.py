"""Verification -- the completion verdict for a task
(docs/DATA_MODEL.md Section 2.4, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26).

Unlike Phase 16's Review / Phase 17's RiskAssessment (one upserted row per
task), Verification keeps a **history chain** per DATA_MODEL.md Section 2.4:
each recompute (or a human decision on an AWAITING_APPROVAL task) inserts a new
row and links the previous live row via ``superseded_by``. The live row is the
one with ``superseded_by IS NULL`` -- the same append-or-supersede shape
Phase 10's versioned ``implementation`` rows use, so nothing is ever mutated in
place or deleted.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class Verification(Base, TimestampMixin):
    __tablename__ = "verification"

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

    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    # [{name, verdict, mandatory, detail, evidence}]
    criteria: Mapped[list] = mapped_column(JSON, nullable=False)
    plan_alignment: Mapped[dict] = mapped_column(JSON, nullable=False)
    # {why_file, why_change, why_test, why_safe}
    trace: Mapped[dict] = mapped_column(JSON, nullable=False)
    trace_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="RESTRICT"), nullable=True
    )
    # 1.0 = edit-ops re-derive the workspace; 0.0 = they don't; null = none to replay
    replay_fidelity: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(24), nullable=False)
    # {decision, reason, actor, decided_at} -- set only by resolve_decision
    decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    superseded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("verification.id", ondelete="SET NULL"), nullable=True
    )

    # No UniqueConstraint(task_id): the table is a history chain. The
    # "at most one live row per task" invariant is maintained by
    # VerificationRepository.create_version (single-writer per task, like
    # TaskStepRepository) -- a partial unique index would need NULLS NOT
    # DISTINCT, which SQLite (the test DB) does not support.
    __table_args__ = (
        Index("ix_verification_task_id", "task_id"),
        Index("ix_verification_superseded_by", "superseded_by"),
    )
