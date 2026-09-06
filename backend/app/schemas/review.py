"""Code-review schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24,
docs/DATA_MODEL.md Section 2.4).

Plain Pydantic v2. ``ReviewFindingsAI`` is the AI output contract; the rest is
the persisted / API shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence

ReviewSource = Literal["STATIC", "RULE", "AI"]
ReviewCategory = Literal[
    "CORRECTNESS",
    "SCOPE",
    "SECURITY",
    "MAINTAINABILITY",
    "ARCHITECTURE",
    "PERFORMANCE",
    "ERROR_HANDLING",
    "TEST_QUALITY",
    "REGRESSION_RISK",
    "DEPENDENCY_IMPACT",
]
ReviewSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
ReviewStatus = Literal["OPEN", "RESOLVED", "OVERRIDDEN"]


class ReviewFinding(BaseModel):
    source: ReviewSource
    category: ReviewCategory
    severity: ReviewSeverity
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    description: str
    recommendation: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence
    status: ReviewStatus = "OPEN"


class _AIFinding(BaseModel):
    category: ReviewCategory
    severity: ReviewSeverity
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    description: str
    recommendation: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence = Confidence(value=0.5, basis="INFERENCE")


class ReviewFindingsAI(BaseModel):
    findings: list[_AIFinding] = Field(default_factory=list)


class ReviewReport(BaseModel):
    task_id: str
    implementation_version: int
    findings: list[ReviewFinding]
    counts_by_severity: dict[str, int]
    counts_by_category: dict[str, int]
    blocking: bool
    static_tools_run: list[str]
    policy_gaps: list[str]
    created_at: datetime
