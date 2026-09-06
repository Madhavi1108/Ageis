"""TestExecution schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20,
docs/EXECUTION_MODEL.md Section 4). Ported and extended from
backend/aegis/schemas/testing.py's TestExecutionResult.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TestOutcomeStatus = Literal["PASS", "FAIL", "ERROR", "SKIPPED"]

ExecutionOutcome = Literal[
    "PASS", "FAIL", "ERROR", "TIMEOUT", "OOM", "INFRA_ERROR", "PARTIALLY_SUPPORTED"
]


class TestOutcome(BaseModel):
    test_id: str
    outcome: TestOutcomeStatus


class TestExecutionRun(BaseModel):
    """The sandbox runner's pure result -- no DB/Artifact concerns. The
    service (app/services/execution.py) turns this into a persisted
    TestExecution."""

    command: str
    exit_code: int
    outcome: ExecutionOutcome
    results: list[TestOutcome] = Field(default_factory=list)
    reason: str | None = Field(
        default=None, description="required when outcome != PASS/FAIL"
    )
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    def passed_ids(self) -> set[str]:
        return {r.test_id for r in self.results if r.outcome == "PASS"}

    def failed_ids(self) -> set[str]:
        return {r.test_id for r in self.results if r.outcome in ("FAIL", "ERROR")}


class TestExecution(BaseModel):
    """Persisted execution + its lifecycle metadata (the API response
    shape)."""

    id: str
    task_id: str
    snapshot_id: str
    implementation_id: str
    version: int
    command: str
    exit_code: int
    outcome: ExecutionOutcome
    results: list[TestOutcome]
    reason: str | None
    duration_ms: int
    stdout_artifact_id: str | None
    stderr_artifact_id: str | None
    created_at: datetime
