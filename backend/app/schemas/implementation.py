"""EditOp + Implementation/Patch schemas (docs/DECISIONS/ADR-0008-patch-representation.md,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18).

Ported and extended from backend/aegis/schemas/implementation.py. ``EditOp`` is the
AI output contract (a list of these is what the Implementation agent asks the
provider to fill); ``Implementation`` is the persisted / API shape -- the applied
edit-ops plus their generated diff, scope violations, and version/task binding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Evidence

EditOpKind = Literal["create", "replace", "insert", "delete"]
ImplementationSource = Literal["AI"]


class EditOp(BaseModel):
    """A structured edit operation -- never a raw file overwrite (ADR-0008)."""

    path: str
    op: EditOpKind
    anchor: str | None = Field(
        default=None,
        description="exact text the edit targets; required for replace/insert/delete",
    )
    old: str | None = None
    new: str | None = None
    plan_step_id: str
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class EditOpsAI(BaseModel):
    """The AI output contract for the Implementation agent."""

    edit_ops: list[EditOp] = Field(..., min_length=1)


class PatchSummary(BaseModel):
    diff_text: str
    touched_paths: list[str]
    diff_size: int


class ImplementationResult(BaseModel):
    """Persisted implementation + its lifecycle metadata (the API response shape)."""

    task_id: str
    snapshot_id: str
    version: int
    edit_ops: list[EditOp]
    scope_violations: list[str]
    traceability: dict[str, list[str]] = Field(
        default_factory=dict,
        description="plan_step_id -> [touched paths from ops carrying that step id]",
    )
    source: ImplementationSource
    patch: PatchSummary
    created_at: datetime
