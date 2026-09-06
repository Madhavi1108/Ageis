"""Job -- an async unit of work driving a task run. See docs/DATA_MODEL.md Section 2.5.

``task_id`` and ``logs_artifact_id`` are plain nullable indexed columns with
no foreign-key constraint: the ``Task`` and ``Artifact`` tables they will
reference don't exist until later phases. A follow-up migration adds the FK
once those tables land (see docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 2 plan).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class JobType(str, enum.Enum):
    INGEST = "INGEST"
    ANALYZE = "ANALYZE"
    MAP = "MAP"
    IMPACT = "IMPACT"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    GENERATE_TESTS = "GENERATE_TESTS"
    EXECUTE_TESTS = "EXECUTE_TESTS"
    INVESTIGATE = "INVESTIGATE"
    RUN_TASK = "RUN_TASK"
    BENCHMARK = "BENCHMARK"
    GC = "GC"


class JobState(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Job(Base, TimestampMixin):
    __tablename__ = "job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobState.PENDING.value, index=True
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    # TODO(later phase): partial-unique on dedupe_key where state is active, once real
    # dedupe/queueing logic lands (docs/TECH_STACK.md worker note).
    dedupe_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    last_checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logs_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
