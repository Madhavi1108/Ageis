"""TestExecutionResult. See docs/AI_AGENT_DESIGN.md Section 7 and
docs/EXECUTION_MODEL.md Section 4 (sandbox execution flow).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TestStatus = Literal["PASS", "FAIL", "ERROR", "SKIPPED"]

ExecutionOutcome = Literal[
    "PASS", "FAIL", "ERROR", "TIMEOUT", "OOM", "INFRA_ERROR", "PARTIALLY_SUPPORTED"
]


class TestOutcome(BaseModel):
    test_id: str
    outcome: TestStatus


class TestExecutionResult(BaseModel):
    command: str
    exit_code: int
    outcome: ExecutionOutcome
    results: list[TestOutcome] = Field(default_factory=list)
    reason: str | None = Field(
        default=None, description="required when outcome == PARTIALLY_SUPPORTED"
    )
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    def passed_ids(self) -> set[str]:
        return {r.test_id for r in self.results if r.outcome == "PASS"}

    def failed_ids(self) -> set[str]:
        return {r.test_id for r in self.results if r.outcome in ("FAIL", "ERROR")}
