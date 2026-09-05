"""Task -- a unit of engineering work. See docs/DATA_MODEL.md Section 2.2.

``state`` holds a value from the full workflow state machine
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.3). Phase 6 only ever writes
``PENDING`` / ``QUEUED`` / ``CANCELLED``; every other member is declared so later
phases (the orchestrator lands in Phase 21) fill the same column without a
migration -- the same forward-declaration pattern Phase 5 used for its
later-phase graph edge types.

``description_sanitized`` has already been through
app/services/tasks.py::normalize_text: control characters stripped, length capped
with provenance recorded on the create response. Raw issue text is never stored
and never interpolated into a prompt -- only structured fields are
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14 security model).

``task_id`` on app/models/job.py stays a plain indexed column (no FK) until the
Phase 21 orchestration migration; see that model's note.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class TaskType(str, enum.Enum):
    BUG = "BUG"
    FEATURE = "FEATURE"
    REFACTOR = "REFACTOR"
    REQUIREMENT = "REQUIREMENT"
    QUESTION = "QUESTION"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class TaskState(str, enum.Enum):
    """The full workflow state machine (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.3).

    Phase 6 exercises only PENDING -> {QUEUED, CANCELLED} and QUEUED -> CANCELLED.
    The remaining members are forward-declared for Phase 21's orchestrator.
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    PLAN_VALIDATION = "PLAN_VALIDATION"
    IMPLEMENTING = "IMPLEMENTING"
    GENERATING_TESTS = "GENERATING_TESTS"
    EXECUTING_TESTS = "EXECUTING_TESTS"
    INVESTIGATING = "INVESTIGATING"
    REPAIRING = "REPAIRING"
    REGRESSION_TESTING = "REGRESSION_TESTING"
    REVIEWING = "REVIEWING"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"


#: States from which no further progression is possible.
TERMINAL_TASK_STATES = frozenset(
    {TaskState.COMPLETED.value, TaskState.FAILED.value, TaskState.CANCELLED.value}
)


class Task(Base, TimestampMixin):
    __tablename__ = "task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issue_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("issue.id", ondelete="SET NULL"), nullable=True
    )
    # Set when a snapshot is bound at ingestion (Phase 7+); null in Phase 6.
    snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=True,
    )
    task_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description_sanitized: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(8), nullable=False, default=TaskPriority.NORMAL.value
    )
    # Scope allowlist (glob paths); null means "no explicit restriction".
    allowed_paths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default=TaskState.PENDING.value
    )
    terminal_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(255), nullable=False, default="api"
    )

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "idempotency_key", name="uq_task_repo_idempotency"
        ),
        Index("ix_task_state", "state"),
        Index("ix_task_repository_id", "repository_id"),
        Index("ix_task_created_at", "created_at"),
    )
