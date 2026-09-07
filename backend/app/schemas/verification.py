"""Verification schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26,
docs/DATA_MODEL.md Section 2.4 "Verification").

Plain Pydantic v2, matching app/schemas/scoring.py's style. ``VerificationResult``
is the persisted / API shape: the per-criterion verdicts, the overall
``VERIFIED`` / ``NOT_VERIFIED`` / ``PARTIAL``, the plan-alignment breakdown, the
explainability trace, and (once a human resolves an ``AWAITING_APPROVAL`` task)
the recorded decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence

CriterionVerdict = Literal["PASS", "FAIL", "UNKNOWN"]
OverallVerdict = Literal["VERIFIED", "NOT_VERIFIED", "PARTIAL"]
DecisionKind = Literal["APPROVE", "REJECT"]


class CriterionResult(BaseModel):
    name: str
    verdict: CriterionVerdict
    mandatory: bool
    detail: str = ""
    evidence: list[Evidence] = Field(default_factory=list)


class PlanAlignment(BaseModel):
    steps_total: int
    steps_implemented: int
    unimplemented_steps: list[str] = Field(default_factory=list)
    unplanned_files: list[str] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)


class ExplainabilityTrace(BaseModel):
    why_file: list[str] = Field(default_factory=list)
    why_change: str = ""
    why_test: list[str] = Field(default_factory=list)
    why_safe: str = ""


class VerificationDecision(BaseModel):
    decision: DecisionKind
    reason: str
    actor: str
    decided_at: datetime


class VerificationDecisionRequest(BaseModel):
    decision: DecisionKind
    reason: str = Field(..., min_length=1, max_length=2000)
    actor: str = Field(..., min_length=1, max_length=255)


class VerificationResult(BaseModel):
    task_id: str
    implementation_version: int
    verdict: OverallVerdict
    criteria: list[CriterionResult]
    plan_alignment: PlanAlignment
    trace: ExplainabilityTrace
    trace_artifact_id: str | None = None
    replay_fidelity: float | None = None
    confidence: Confidence
    resulting_state: str
    decision: VerificationDecision | None = None
    model_version: str
    created_at: datetime
