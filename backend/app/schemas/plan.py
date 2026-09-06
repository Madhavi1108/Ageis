"""EngineeringPlan + PlanValidation schemas (docs/AI_AGENT_DESIGN.md Section 7,
docs/DATA_MODEL.md Section 2.2, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17).

Ported and extended from backend/aegis/schemas/plan.py. ``EngineeringPlanAI`` is
the shape the model must fill (passed as ``schema=`` to ``AIProvider.complete``);
``EngineeringPlan`` is the persisted / API shape -- the plan plus its version,
task binding, and (once validated) its ``PlanValidation``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence

PlanSource = Literal["AI", "RULE_BASED_FALLBACK"]
PlanVerdict = Literal["APPROVED", "REVISE", "REJECTED"]


class PlanStep(BaseModel):
    id: str
    description: str
    test_intent: str = Field(
        ..., description="what behaviour this step's test should cover"
    )
    evidence_refs: list[str] = Field(default_factory=list)


class EngineeringPlanAI(BaseModel):
    """The AI output contract for the Planning agent."""

    problem_interpretation: str
    assumptions: list[str] = Field(default_factory=list)
    files_to_inspect: list[str] = Field(default_factory=list)
    files_to_modify: list[str]
    symbols_to_modify: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    steps: list[PlanStep]
    test_strategy: dict = Field(default_factory=dict)
    expected_behavior: str
    regression_risks: list[str] = Field(default_factory=list)
    rollback_strategy: str
    source: PlanSource
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)


class PlanValidation(BaseModel):
    verdict: PlanVerdict
    reasons: list[str] = Field(default_factory=list)
    checked: dict[str, bool] = Field(default_factory=dict)


class EngineeringPlan(BaseModel):
    """Persisted plan + its lifecycle metadata (the API response shape)."""

    task_id: str
    snapshot_id: str
    version: int
    problem_interpretation: str
    assumptions: list[str]
    files_to_inspect: list[str]
    files_to_modify: list[str]
    symbols_to_modify: list[str]
    dependencies: list[str]
    steps: list[PlanStep]
    test_strategy: dict
    expected_behavior: str
    regression_risks: list[str]
    rollback_strategy: str
    source: PlanSource
    confidence: Confidence
    evidence: list[Evidence]
    validation: PlanValidation | None
    created_at: datetime
