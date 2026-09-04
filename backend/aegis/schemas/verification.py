"""VerificationResult -- the three mandatory criteria for the walking skeleton.
See docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 18 (full system) and Phase 1's
reduced three-criteria version.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Confidence, Evidence


class Criterion(BaseModel):
    name: str
    verdict: Literal["PASS", "FAIL"]
    evidence: list[Evidence] = Field(default_factory=list)
    detail: str = ""


class VerificationResult(BaseModel):
    verdict: Literal["VERIFIED", "NOT_VERIFIED", "PARTIAL"]
    criteria: list[Criterion]
    plan_alignment: dict = Field(default_factory=dict)
    confidence: Confidence

    def all_pass(self) -> bool:
        return all(c.verdict == "PASS" for c in self.criteria)
