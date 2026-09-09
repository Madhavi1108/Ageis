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

from app.ai.context import ContextSection, fit_context
from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.implementation.editor import EditorError, apply_edit_op
from app.implementation.patcher import touched_paths, unified_diff
from app.implementation.scope_tracker import unplanned_files
from app.implementation.workspace_rw import RWWorkspace
from app.schemas.implementation import EditOp, EditOpsAI

_IMPLEMENTATION_TEMPLATE = "implementation"
#: effectively unbounded -- callers that care pass limits.ai_context_tokens(...)
_DEFAULT_CONTEXT_BUDGET = 1_000_000


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
    context_budget_tokens: int = _DEFAULT_CONTEXT_BUDGET,
    context_provenance: list[str] | None = None,
) -> list[EditOp]:
    steps_text = (
        "\n".join(
            f"- {s.get('id')}: {s.get('description')} (test_intent: {s.get('test_intent')})"
            for s in plan_steps
        )
        or "(none)"
    )
    # Phase 27: bound the context. problem_interpretation + the modify lists are
    # priority 0 (the model needs them to produce a correct patch); step detail
    # is trimmed first if the plan is huge.
    fitted = fit_context(
        [
            ContextSection("problem_interpretation", problem_interpretation, priority=0),
            ContextSection("files_to_modify", "\n".join(files_to_modify) or "(none)", priority=0),
            ContextSection("symbols_to_modify", "\n".join(symbols_to_modify) or "(none)", priority=0),
            ContextSection("steps", steps_text, priority=2),
        ],
        context_budget_tokens,
    )
    if fitted.changed and context_provenance is not None:
        context_provenance.append(fitted.note())

    variables: dict[str, Any] = {
        "task_key": task_key,
        "problem_interpretation": fitted.kept["problem_interpretation"],
        "files_to_modify": fitted.kept["files_to_modify"],
        "symbols_to_modify": fitted.kept["symbols_to_modify"],
        "steps": fitted.kept["steps"],
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
