"""API schemas for impact analysis. See docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 16 and docs/DATA_MODEL.md Section 2.2 ("ImpactAnalysis").

Plain Pydantic v2, matching app/schemas/mapping.py's style.

``report`` is a rendered human-readable summary (the Specification's worked-
example shape); it is derived from the structured fields on read and never
persisted, so it cannot drift from the machine bundle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RefBasis = Literal["FACT", "INFERENCE"]


class ChangedSet(BaseModel):
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class CallerRef(BaseModel):
    ref: str
    hop: int
    edge_confidence: str | None = None


class SymbolCallers(BaseModel):
    symbol: str
    callers: list[CallerRef] = Field(default_factory=list)


class PublicApiRef(BaseModel):
    symbol_id: str
    # "route" (FastAPI/Starlette route decorator) | "exported" (in __all__ or a
    # public top-level symbol). Phase 4's is_exported flag folds the last two, so
    # the finer __all__-vs-top-level split isn't recoverable here.
    reason: str


class HeuristicRef(BaseModel):
    ref: str
    detail: str
    basis: RefBasis = "INFERENCE"


class RegressionArea(BaseModel):
    path: str
    score: float
    reason: str


class RiskSignal(BaseModel):
    value: float | None
    normalized: float | None
    basis: RefBasis
    unavailable_reason: str | None = None


class ImpactAnalysis(BaseModel):
    task_id: str
    snapshot_id: str
    changed_set: ChangedSet
    blast_radius: dict[str, list[str]]
    callers: list[SymbolCallers]
    related_tests: list[str]
    public_api_touched: list[PublicApiRef]
    config_refs: list[HeuristicRef]
    db_refs: list[HeuristicRef]
    regression_areas: list[RegressionArea]
    risk_signal_bundle: dict[str, RiskSignal]
    report: str
    created_at: datetime
