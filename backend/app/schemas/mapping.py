"""API schemas for issue -> code mapping. See docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 15 and docs/REPOSITORY_ANALYSIS.md Section 5.

Plain Pydantic v2, matching app/schemas/graph.py's style. ``Evidence`` is
reused from aegis.schemas.common so the "what backs this conclusion" vocabulary
stays aligned with the rest of the pipeline (docs/AI_AGENT_DESIGN.md Section 6).

Hard rule enforced structurally here: a ``MappingCandidate`` cannot be
constructed with an empty ``evidence`` list -- the "no evidence-free candidate"
rule (docs/REPOSITORY_ANALYSIS.md Section 5) is a validation error, not just a
convention.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aegis.schemas.common import Evidence

ConclusionLabel = Literal["FACT", "INFERENCE"]


class MappingCandidate(BaseModel):
    path: str
    symbols: list[str] = Field(default_factory=list)
    score: float = Field(
        ..., description="fused reciprocal-rank score, higher = better"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    labels: list[ConclusionLabel] = Field(default_factory=list)
    evidence: list[Evidence] = Field(..., min_length=1)


class IssueCodeMapping(BaseModel):
    task_id: str | None
    snapshot_id: str
    candidates: list[MappingCandidate]
    related_tests: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    semantic_available: bool
    model_version: str
    created_at: datetime


class MapRequest(BaseModel):
    """Either ``task_id`` (compute + persist for that task) or
    ``snapshot_id`` + ``issue_text`` (stateless, nothing persisted)."""

    task_id: str | None = None
    snapshot_id: str | None = None
    issue_text: str | None = None
    top_k: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> "MapRequest":
        task_mode = self.task_id is not None
        stateless_mode = self.snapshot_id is not None or self.issue_text is not None
        if task_mode == stateless_mode:
            raise ValueError(
                "provide either 'task_id' or both 'snapshot_id' and 'issue_text'"
            )
        if stateless_mode and not (self.snapshot_id and self.issue_text):
            raise ValueError(
                "stateless mapping needs both 'snapshot_id' and 'issue_text'"
            )
        return self
