"""TestCase / TestGeneration schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 19).

``TestCasesAI`` is the AI output contract for the Testing agent (a batch of
proposed test cases); ``TestCase`` is the persisted / API shape for one test
case, including its post-hoc ``status`` (``GENERATED`` / ``INVALID`` today --
``EXECUTED`` / ``PASSED`` / ``FAILED`` / ``SKIPPED`` are written by Phase 12).
``TestGeneration`` is the API response shape for one generation run (a batch
of ``TestCase`` rows sharing a ``version``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Evidence

TestCaseKind = Literal["EDGE", "NEGATIVE", "BOUNDARY", "REGRESSION", "ISSUE_SPECIFIC"]
TestCaseStatus = Literal[
    "GENERATED", "EXECUTED", "PASSED", "FAILED", "SKIPPED", "INVALID"
]


class TestCaseAI(BaseModel):
    """One proposed test case -- always a brand-new file (Phase 11 never
    edits an existing test file's content, so "never modify unrelated
    existing tests" holds by construction)."""

    name: str = Field(..., description="the test function's name, e.g. test_foo")
    path: str = Field(..., description="a new file path, e.g. test_foo_boundary.py")
    target_symbol: str
    kind: TestCaseKind
    rationale: str
    code: str = Field(..., description="the full content of the new test file")
    evidence: list[Evidence] = Field(default_factory=list)


class TestCasesAI(BaseModel):
    test_cases: list[TestCaseAI] = Field(..., min_length=1)


class TestCase(BaseModel):
    """Persisted test case + its lifecycle metadata (the API response shape
    for one row)."""

    name: str
    path: str
    target_symbol: str
    kind: TestCaseKind
    rationale: str
    code: str
    evidence: list[Evidence]
    status: TestCaseStatus
    invalid_reason: str | None
    created_at: datetime


class TestGeneration(BaseModel):
    task_id: str
    snapshot_id: str
    implementation_id: str
    version: int
    test_cases: list[TestCase]
    targeted_set: list[str]
    policy_gaps: list[str]
    created_at: datetime
