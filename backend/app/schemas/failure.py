"""FailureAnalysis schemas (docs/AI_AGENT_DESIGN.md Section 7,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21).

Plain Pydantic v2, matching app/schemas/execution.py. No root cause: ``facts``
are re-checkable statements, ``inferences`` are hedged candidate signals only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FailureType = Literal[
    "ASSERTION", "EXCEPTION", "COLLECTION_ERROR", "TIMEOUT", "IMPORT_ERROR", "ENV"
]


class Frame(BaseModel):
    file: str
    lineno: int
    symbol_id: str | None = None
    in_diff: bool = False
    code_slice: str | None = None


class FailureRecord(BaseModel):
    test_name: str
    failure_type: FailureType
    exception_type: str | None = None
    message: str | None = None
    frames: list[Frame] = Field(default_factory=list)
    chained: bool = False


class FailureAnalysis(BaseModel):
    task_id: str
    execution_id: str
    failures: list[FailureRecord]
    facts: list[str]
    inferences: list[str]
    classification: dict
    evidence: dict
    created_at: datetime
