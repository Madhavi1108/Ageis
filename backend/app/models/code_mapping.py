"""CodeMapping -- the persisted ``IssueCodeMapping`` result for a task. See
docs/DATA_MODEL.md Section 2.2 ("CodeMapping") and
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15.

One row per task (``UniqueConstraint(task_id)``), rewritten in place when a
mapping is recomputed -- upsert, not delete-then-recreate, same rationale as
RepositoryAnalysis. The ranked candidates, related tests, and dependencies are
stored as JSON blobs rather than child tables: they are always read and written
as a whole document, never queried field-by-field (docs/DATA_MODEL.md Section 4
"small fields in the DB, structured documents as JSON").

``semantic_available`` records whether an embeddings retriever contributed:
Phase 7 has no ``AIProvider`` in ``app/`` so it is always ``False`` for now, and
``overall_confidence`` is scaled down accordingly (docs/METRICS.md Section 4).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class CodeMapping(Base, TimestampMixin):
    __tablename__ = "code_mapping"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # [{path, symbols[], score, confidence, labels[], evidence[]}], rank order.
    candidates: Mapped[list] = mapped_column(JSON, nullable=False)
    related_tests: Mapped[list] = mapped_column(JSON, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSON, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_code_mapping_task"),
        Index("ix_code_mapping_task_id", "task_id"),
        Index("ix_code_mapping_snapshot_id", "snapshot_id"),
    )
