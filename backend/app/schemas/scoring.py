"""Risk & Confidence Engine schemas (Phase 17,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 25, docs/METRICS.md Section 2,
docs/DATA_MODEL.md Section 2.4 "RiskAssessment").

Plain Pydantic v2, matching app/schemas/review.py's style. Every score returns
``{value, classification, per_signal_contributions, overall_confidence,
evidence_refs, model_version}`` -- the contribution breakdown sums to
``value_raw / 100`` so the number is always explained.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Evidence

PCSClassification = Literal["HIGH", "MEDIUM", "LOW", "VERY_LOW", "BLOCKED"]
CRSClassification = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RHPClassification = Literal["HIGH", "MEDIUM", "LOW", "VERY_LOW"]
SignalBasis = Literal["FACT", "INFERENCE"]


class SignalContribution(BaseModel):
    """One signal's line in a score's explanation."""

    name: str
    raw: float | None = None
    normalized: float
    weight: float
    contribution: float
    basis: SignalBasis
    unavailable_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class RiskyModule(BaseModel):
    path: str
    score: float
    centrality: float
    churn: float | None = None
    inverse_coverage: float | None = None
    complexity: float


class RepositoryHealthProfile(BaseModel):
    repository_id: str
    snapshot_id: str
    value: int
    classification: RHPClassification
    subscores: list[SignalContribution]
    risky_modules: list[RiskyModule] = Field(default_factory=list)
    # set on the Task-Specific Risk Profile (RHP restricted to the impact set)
    scope: Literal["repository", "task"] = "repository"
    model_version: str
    created_at: datetime


class PatchConfidence(BaseModel):
    task_id: str
    implementation_version: int
    value: int
    classification: PCSClassification
    pcs_raw: float
    security_gate: float
    hard_gate: list[str] = Field(default_factory=list)
    per_signal_contributions: list[SignalContribution]
    overall_confidence: float
    evidence_refs: list[Evidence] = Field(default_factory=list)
    model_version: str
    created_at: datetime


class PatchRiskAssessment(BaseModel):
    task_id: str
    implementation_version: int
    value: int
    classification: CRSClassification
    crs_raw: float
    per_signal_contributions: list[SignalContribution]
    overall_confidence: float
    task_risk_profile: RepositoryHealthProfile
    evidence_refs: list[Evidence] = Field(default_factory=list)
    model_version: str
    created_at: datetime
