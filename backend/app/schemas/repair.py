"""RootCauseAnalysis + RepairProposal + repair-ledger schemas
(docs/AI_AGENT_DESIGN.md Section 7, docs/DATA_MODEL.md Section 2.3,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 22).

``RootCauseAnalysis`` / ``RepairProposal`` are AI-output contracts. The rest is
the persisted / API ledger shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence
from app.schemas.implementation import EditOp

HypothesisLabel = Literal["FACT", "INFERENCE", "HYPOTHESIS"]
AttemptOutcome = Literal["IMPROVED", "NO_CHANGE", "WORSENED", "GREEN", "REVERTED"]
RepairOutcome = Literal["REPAIRED", "SAFE_STOP"]


class Hypothesis(BaseModel):
    statement: str
    label: HypothesisLabel
    evidence: list[Evidence] = Field(default_factory=list)
    rank: int = 0


class RootCauseAnalysis(BaseModel):
    hypotheses: list[Hypothesis] = Field(..., min_length=1)
    most_likely_index: int = 0
    open_questions: list[str] = Field(default_factory=list)
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)


class RepairProposal(BaseModel):
    target_hypothesis: str
    edit_ops: list[EditOp] = Field(..., min_length=1)
    expected_effect: str
    risk_notes: list[str] = Field(default_factory=list)
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)


class RepairAttemptView(BaseModel):
    iteration: int
    outcome: AttemptOutcome
    hypothesis: str
    edit_ops: list[EditOp]
    failing_before: int
    failing_after: int
    regression_failures: int
    diff_size: int
    score: list[int]
    targeted_execution_id: str | None = None
    created_at: datetime


class SafeStop(BaseModel):
    reason: str
    failure_summary: str
    evidence: dict
    attempted_fixes: list[dict]
    remaining_uncertainty: list[str]
    recommended_human_action: str


class RepairResult(BaseModel):
    task_id: str
    investigation_execution_id: str
    outcome: RepairOutcome
    best_iteration: int | None
    attempts: list[RepairAttemptView]
    final_edit_ops: list[EditOp]
    safe_stop: SafeStop | None
    created_at: datetime
