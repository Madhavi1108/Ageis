"""TaskStep -- one workflow-state entry in a task's timeline. See docs/DATA_MODEL.md Section 2.2.

A step row is opened (``entered_at`` set) when a task enters a state and closed
(``exited_at`` + ``duration_ms`` set) when it leaves. In Phase 6 only the
PENDING / QUEUED / CANCELLED steps are written; the orchestrator (Phase 21)
appends the rest as the workflow advances.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStep(Base):
    __tablename__ = "task_step"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    exited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Nullable Artifact/row refs -- the artifact store lands per producing phase.
    input_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    output_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_task_step_task_seq"),
        Index("ix_task_step_task_seq", "task_id", "seq"),
        Index("ix_task_step_task_state", "task_id", "state"),
    )
