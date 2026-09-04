"""EngineeringPlan and PlanValidation. See docs/AI_AGENT_DESIGN.md Section 7
and docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 9 (Engineering Planning + Plan
Validation).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence


class PlanStep(BaseModel):
    id: str
    description: str
    test_intent: str = Field(
        ..., description="what behaviour this step's test should cover"
    )
    evidence_refs: list[str] = Field(default_factory=list)


class EngineeringPlan(BaseModel):
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
    source: Literal["AI", "RULE_BASED_FALLBACK"]
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)


class PlanValidation(BaseModel):
    verdict: Literal["APPROVED", "REVISE", "REJECTED"]
    reasons: list[str] = Field(default_factory=list)
    checked: dict[str, bool] = Field(default_factory=dict)
