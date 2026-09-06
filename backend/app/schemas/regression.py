"""Regression-selection schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23).

Plain Pydantic v2, matching app/schemas/execution.py. No AI: the classification
is deterministic (graph + naming + centrality + prior failures).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TestClass = Literal["TARGETED", "RELATED", "REGRESSION", "FULL"]
SelectionMode = Literal["smart", "full"]


class ClassifiedTest(BaseModel):
    test_id: str
    path: str
    classification: TestClass
    rationale: str
    covers_symbol: str | None = None
    hops: int | None = None


class RegressionPlan(BaseModel):
    task_id: str
    snapshot_id: str
    mode: SelectionMode
    changed_files: list[str]
    changed_symbols: list[str]
    tests: list[ClassifiedTest]
    selection: dict[str, list[str]]
    full_suite_count: int
    subset_justification: str | None = None
    subset_risk_note: str | None = None
    created_at: datetime


class RegressionResult(BaseModel):
    plan: RegressionPlan
    executed: bool
    execution_id: str | None = None
    baseline_execution_id: str | None = None
    new_failures: list[str] = Field(default_factory=list)
    reason: str | None = None
