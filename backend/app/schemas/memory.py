"""Engineering-memory schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28,
docs/DATA_MODEL.md Section 2.4, ADR-0016). Plain Pydantic v2.

``MemoryHit`` always carries ``label`` (the "historical -- verify" marker) and
``provenance`` so a consumer can present it as non-authoritative evidence.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EngineeringMemoryOut(BaseModel):
    id: str
    repository_id: str
    task_id: str
    issue_text_sanitized: str
    touched_symbols: list[str] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    failure_signatures: list[str] = Field(default_factory=list)
    fix_summary: str
    plan_ref: dict = Field(default_factory=dict)
    patch_ref: str | None = None
    review_summary: dict = Field(default_factory=dict)
    verification_verdict: str | None = None
    outcome: str
    embedding_ref: str | None = None
    created_at: datetime


class MemoryHit(BaseModel):
    task_id: str
    repository_id: str
    outcome: str
    verification_verdict: str | None = None
    issue_summary: str
    fix_summary: str
    touched_symbols: list[str] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    similarity: float
    same_repository: bool
    provenance: str
    label: str
    created_at: datetime


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=20_000)
    repository_id: str | None = None
    top_k: int | None = Field(default=None, gt=0, le=50)
