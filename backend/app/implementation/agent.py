"""Implementation agent (docs/AI_AGENT_DESIGN.md Section 2,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18).

Pure functions over already-loaded inputs -- the service
(app/services/implementation.py) does the DB / provider / workspace wiring.

* ``propose_edit_ops`` -- ask the configured provider to fill the EditOpsAI
                          schema from the approved EngineeringPlan.
* ``apply_and_diff``   -- apply the proposed ops to an RW workspace, compute
                          touched paths and the unified diff, and flag any
                          out-of-scope write. Never raises EditorError past
                          this boundary -- a failed op sequence is reported
                          as zero touched paths, not a crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.implementation.editor import EditorError, apply_edit_op
from app.implementation.patcher import touched_paths, unified_diff
from app.implementation.scope_tracker import unplanned_files
from app.implementation.workspace_rw import RWWorkspace
from app.schemas.implementation import EditOp, EditOpsAI

_IMPLEMENTATION_TEMPLATE = "implementation"


def propose_edit_ops(
    *,
    task_key: str,
    plan_steps: list[dict],
    files_to_modify: list[str],
    symbols_to_modify: list[str],
    problem_interpretation: str,
    provider: AIProvider,
    timeout_s: float,
    max_tokens: int,
) -> list[EditOp]:
    variables: dict[str, Any] = {
        "task_key": task_key,
        "problem_interpretation": problem_interpretation,
        "files_to_modify": "\n".join(files_to_modify) or "(none)",
        "symbols_to_modify": "\n".join(symbols_to_modify) or "(none)",
        "steps": "\n".join(
            f"- {s.get('id')}: {s.get('description')} (test_intent: {s.get('test_intent')})"
            for s in plan_steps
        )
        or "(none)",
    }
    result = provider.complete(
        template=_IMPLEMENTATION_TEMPLATE,
        variables=variables,
        schema=EditOpsAI,
        tier=tier_for("implementation"),
        timeout_s=timeout_s,
        max_tokens=max_tokens,
    )
    assert isinstance(result, EditOpsAI)
    return result.edit_ops


class ApplyResult:
    def __init__(
        self,
        *,
        applied_ops: list[EditOp],
        diff_text: str,
        touched: set[str],
        scope_violations: set[str],
        failed_op_error: str | None,
    ) -> None:
        self.applied_ops = applied_ops
        self.diff_text = diff_text
        self.touched = touched
        self.scope_violations = scope_violations
        self.failed_op_error = failed_op_error


def apply_and_diff(
    ws: RWWorkspace,
    source_workspace: Path,
    ops: list[EditOp],
    *,
    allowed_scope: set[str],
) -> ApplyResult:
    """Apply ``ops`` in order to ``ws``. Stops (and records) at the first
    ``EditorError`` -- an ambiguous or missing anchor fails loudly rather than
    guessing (ADR-0008); it never silently skips an op."""
    applied: list[EditOp] = []
    failed_op_error: str | None = None
    for op in ops:
        try:
            apply_edit_op(ws, op)
            applied.append(op)
        except EditorError as exc:
            failed_op_error = str(exc)
            break

    touched = touched_paths(source_workspace, ws)
    diff_text = unified_diff(source_workspace, ws)
    scope_violations = unplanned_files(source_workspace, ws, list(allowed_scope))

    return ApplyResult(
        applied_ops=applied,
        diff_text=diff_text,
        touched=touched,
        scope_violations=scope_violations,
        failed_op_error=failed_op_error,
    )
