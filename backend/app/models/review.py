"""Review + ReviewFinding -- the code-review report and its findings
(docs/DATA_MODEL.md Section 2.4, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24).

Same shape as Phase 13's investigation + failure pair: ``Review`` is the
per-task aggregate (upsert, ``UniqueConstraint(task_id)``) with a denormalised
``findings`` copy; ``ReviewFinding`` rows are replace-for-task so downstream
(Phase 17 PCS/CRS, the scope guard) can query by severity / category / status.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
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
from app.models.base import Base, TimestampMixin


class Review(Base, TimestampMixin):
    __tablename__ = "review"

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
    findings: Mapped[list] = mapped_column(JSON, nullable=False)
    static_tools_run: Mapped[list] = mapped_column(JSON, nullable=False)
    policy_gaps: Mapped[list] = mapped_column(JSON, nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_review_task"),
        Index("ix_review_task_id", "task_id"),
    )


class ReviewFinding(Base):
    __tablename__ = "review_finding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    file: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_review_finding_task_severity", "task_id", "severity"),
        Index("ix_review_finding_task_category", "task_id", "category"),
        Index("ix_review_finding_task_status", "task_id", "status"),
    )
