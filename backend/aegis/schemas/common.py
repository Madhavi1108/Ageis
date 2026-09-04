"""Shared schema primitives. See docs/AI_AGENT_DESIGN.md Section 6.

Every AI-influenced output in AEGIS carries evidence and a confidence label so
conclusions can be independently re-checked and hallucination is structurally
discouraged (docs/AI_AGENT_DESIGN.md Section 5, Specification Section 21).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceKind = Literal[
    "file", "symbol", "line_range", "test", "commit", "dependency", "execution"
]

ConfidenceBasis = Literal[
    "FACT", "INFERENCE", "HYPOTHESIS", "RECOMMENDATION", "UNKNOWN"
]


class Evidence(BaseModel):
    """One concrete, re-checkable fact backing a conclusion."""

    kind: EvidenceKind
    ref: str = Field(
        ..., description="path, symbol_id, 'path:start-end', test id, etc."
    )
    detail: str = Field(..., description="one line: what this evidence shows")


class Confidence(BaseModel):
    """A confidence value plus the epistemic basis for it.

    A FACT must be backed by at least one Evidence item (enforced at the call
    sites that construct plans/conclusions, not here -- this model is the
    shared value type).
    """

    value: float = Field(..., ge=0.0, le=1.0)
    basis: ConfidenceBasis


class AgentError(BaseModel):
    code: str
    message: str
    recoverable: bool
    evidence: list[Evidence] = Field(default_factory=list)
