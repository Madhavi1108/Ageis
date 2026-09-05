"""API schemas for task / issue ingestion. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14.

The raw free-text ``text`` (or the structured ``issue``) is the only untrusted
input; it is normalized by app/services/tasks.py before anything is persisted and
is never echoed into a prompt -- downstream phases read the structured
``description`` field only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskTypeLiteral = Literal["BUG", "FEATURE", "REFACTOR", "REQUIREMENT", "QUESTION"]
PriorityLiteral = Literal["LOW", "NORMAL", "HIGH"]


class IssueAnalysisInput(BaseModel):
    """A pre-structured issue supplied by the caller or a future import adapter.

    Phase 6 accepts this shape directly; a live GitHub fetch that produces it is
    Phase 19. Fields are treated as untrusted and normalized like free text.
    """

    source: Literal["API", "GITHUB", "EXCEL"] = "API"
    external_ref: str | None = Field(
        default=None, description="e.g. a GitHub issue number"
    )
    title: str
    body: str


class TaskCreate(BaseModel):
    repository_id: str
    text: str | None = Field(
        default=None, description="Free-text issue / bug / feature / requirement body"
    )
    issue: IssueAnalysisInput | None = Field(
        default=None, description="A pre-structured issue instead of free text"
    )
    title: str | None = Field(
        default=None, description="Derived from the first line of the body if omitted"
    )
    task_type: TaskTypeLiteral | None = Field(
        default=None, description="Inferred from the text by deterministic rules if omitted"
    )
    priority: PriorityLiteral = "NORMAL"
    constraints: dict | None = None
    allowed_paths: list[str] | None = Field(
        default=None, description="Scope allowlist (glob paths)"
    )
    created_by: str | None = None
    # Exactly one of `text` / `issue` must be set; enforced in
    # app/services/tasks.py::create_task so the failure is a typed AppError
    # envelope rather than a raw validator error.


class NormalizationInfo(BaseModel):
    truncated: bool
    original_bytes: int
    stored_bytes: int


class Task(BaseModel):
    id: str
    repository_id: str
    issue_id: str | None = None
    snapshot_id: str | None = None
    task_type: TaskTypeLiteral
    title: str
    description: str
    constraints: dict | None = None
    priority: PriorityLiteral
    allowed_paths: list[str] | None = None
    idempotency_key: str
    state: str
    terminal_reason: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskCreateResponse(BaseModel):
    task: Task
    normalization: NormalizationInfo


class TaskList(BaseModel):
    items: list[Task]
    limit: int
    offset: int
    total: int


class TaskStepView(BaseModel):
    seq: int
    state: str
    entered_at: datetime
    exited_at: datetime | None = None
    agent: str | None = None
    duration_ms: int | None = None
    error: dict | None = None


class TimelineEntry(BaseModel):
    kind: Literal["STEP", "JOB"]
    seq: int | None = None
    state: str
    at: datetime
    detail: str | None = None


class TaskTimeline(BaseModel):
    task_id: str
    state: str
    entries: list[TimelineEntry]


class TaskCancelRequest(BaseModel):
    reason: str | None = None
