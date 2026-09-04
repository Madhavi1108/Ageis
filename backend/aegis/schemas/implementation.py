"""EditOp and ImplementationResult. See docs/AI_AGENT_DESIGN.md Section 7 and
docs/DECISIONS/ADR-0008-patch-representation.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import Evidence


class EditOp(BaseModel):
    """A structured edit operation -- never a raw file overwrite (ADR-0008)."""

    path: str
    op: Literal["create", "replace", "insert", "delete"]
    anchor: str | None = Field(
        default=None,
        description="exact text the edit targets; required for replace/insert/delete",
    )
    old: str | None = None
    new: str | None = None
    plan_step_id: str
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class ImplementationResult(BaseModel):
    edit_ops: list[EditOp]
    diff_text: str = ""
    scope_violations: list[str] = Field(default_factory=list)
