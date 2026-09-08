"""Reporting schemas (Phase 23, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 31).

``TaskReport`` is the structured 18-section report (Specification Section 33)
served as JSON by ``GET /reports/tasks/{id}`` and rendered to xlsx by
``GET /reports/tasks/{id}.xlsx``. ``ImportResult`` is the per-row outcome of
``POST /reports/import``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Specification Section 33 -- the canonical section order.
SECTION_NAMES: list[str] = [
    "Requirement",
    "Repository",
    "Understanding",
    "Code mapping",
    "Impact",
    "Plan",
    "Implementation",
    "Tests",
    "Failures",
    "Repairs",
    "Regression results",
    "Review",
    "Risk",
    "Confidence",
    "Verification",
    "Patch",
    "PR information",
    "Remaining limitations",
]


class ReportSection(BaseModel):
    number: int
    name: str
    present: bool
    note: str = ""
    data: Any = None


class TaskReport(BaseModel):
    task_id: str
    repository_id: str
    title: str
    outcome: str  # the task's terminal / current state
    generated_at: datetime
    sections: list[ReportSection]


class ImportRowError(BaseModel):
    sheet: str
    row: int
    code: str
    message: str
    details: dict[str, Any] | None = None


class ImportResult(BaseModel):
    repositories_created: int
    tasks_created: int
    repository_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    errors: list[ImportRowError] = Field(default_factory=list)
