"""TrustReportV0 -- the walking skeleton's reduced Trust Report. See
docs/GOVERNANCE.md Section 6 for the full design; v0 here carries raw signals
rather than the calibrated PCS/CRS scores (Phase 17's job).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceTrace(BaseModel):
    why_file: list[str] = Field(default_factory=list)
    why_change: str = ""
    why_tests: list[str] = Field(default_factory=list)
    why_safe: str = ""


class TrustReportV0(BaseModel):
    task_repo: str
    task_title: str
    outcome: Literal["VERIFIED", "NOT_VERIFIED", "SAFE_STOP", "PARTIALLY_SUPPORTED"]
    evidence_trace: EvidenceTrace
    mapping_summary: dict = Field(default_factory=dict)
    diff_text: str = ""
    plan_alignment: dict = Field(default_factory=dict)
    tests: dict = Field(default_factory=dict)
    review: dict = Field(
        default_factory=lambda: {"note": "static checks only; AI review is Phase 16"}
    )
    scores: dict = Field(
        default_factory=lambda: {"note": "raw signals only; calibrated PCS/CRS is Phase 17"}
    )
    replay: dict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
