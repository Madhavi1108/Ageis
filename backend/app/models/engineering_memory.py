"""EngineeringMemory -- a persisted completed-task record for future retrieval
(docs/DATA_MODEL.md Section 2.4, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28,
ADR-0016).

One upserted row per task (`Task 1--1 EngineeringMemory`), written by
``app/services/memory.py::record_task`` at a terminal state (``VERIFIED`` or
``SAFE_STOP``). Retrieval treats every row as *evidence, never truth* --
provenance + a "historical -- verify" label, never an auto-applied patch
(ADR-0016). ``embedding_ref`` is reserved for an optional local embedding index
and stays ``NULL`` in this phase.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class EngineeringMemory(Base, TimestampMixin):
    __tablename__ = "engineering_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repository.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="RESTRICT"), nullable=False
    )

    issue_text_sanitized: Mapped[str] = mapped_column(Text, nullable=False)
    touched_symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # extra beyond DATA_MODEL: retrieval + the regression risk hook read this
    touched_files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    failure_signatures: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fix_summary: Mapped[str] = mapped_column(Text, nullable=False)
    plan_ref: Mapped[dict] = mapped_column(JSON, nullable=False)
    patch_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    verification_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # VERIFIED | SAFE_STOP
    embedding_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_engineering_memory_task"),
        Index("ix_engineering_memory_repository_id", "repository_id"),
        Index("ix_engineering_memory_created_at", "created_at"),
    )
