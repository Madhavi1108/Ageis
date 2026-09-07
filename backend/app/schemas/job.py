"""Job API schemas (Phase 21, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobView(BaseModel):
    id: str
    task_id: str | None = None
    type: str
    state: str
    progress: float
    attempts: int
    max_attempts: int
    idempotency_key: str
    dedupe_key: str | None = None
    last_checkpoint: dict | None = None
    worker_id: str | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: dict | None = None
    created_at: datetime


class JobList(BaseModel):
    items: list[JobView]
    limit: int
    offset: int
    total: int
