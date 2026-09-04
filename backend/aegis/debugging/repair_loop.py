"""Bounded repair loop (reduced to 2 iterations). See
docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 14 (full system, 4-iteration budget)
and Phase 1's reduced version. Never exceeds its bound; never crashes on a
bad edit-op or an invalid AI response -- both simply end the loop early.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from aegis.ai.provider import AIProvider
from aegis.ai.schema_guard import AIOutputInvalid
from aegis.implementation.editor import EditorError, apply_edit_op
from aegis.repository.workspace import RWWorkspace
from aegis.sandbox.runner import SandboxRunner
from aegis.schemas.implementation import EditOp, ImplementationResult
from aegis.schemas.testing import TestExecutionResult

MAX_REPAIR_ITERATIONS = 2

RepairOutcome = Literal["IMPROVED", "NO_CHANGE", "WORSENED", "GREEN"]


@dataclass(frozen=True)
class RepairAttempt:
    iteration: int
    edit_ops: list[EditOp]
    exec_result: TestExecutionResult
    outcome: RepairOutcome


@dataclass(frozen=True)
class RepairLoopResult:
    final_exec_result: TestExecutionResult
    attempts: list[RepairAttempt] = field(default_factory=list)
    applied_ops: list[EditOp] = field(default_factory=list)


def run_repair_loop(
    *,
    ws: RWWorkspace,
    provider: AIProvider,
    sandbox: SandboxRunner,
    test_command: list[str],
    initial_exec_result: TestExecutionResult,
    task_key: str,
    target_file: str | None,
    target_file_head: str,
    plan_step_id: str,
) -> RepairLoopResult:
    """Run up to MAX_REPAIR_ITERATIONS repair attempts. Stops as soon as the
    sandbox reports PASS, when the provider cannot produce a schema-valid
    repair proposal, or when the proposed edit cannot be applied -- never
    silently loops forever and never exceeds the bound (see
    tests/unit/test_repair_loop.py for the property test)."""
    attempts: list[RepairAttempt] = []
    applied_ops: list[EditOp] = []
    exec_result = initial_exec_result
    prev_failed = len(exec_result.failed_ids())

    for i in range(1, MAX_REPAIR_ITERATIONS + 1):
        if exec_result.outcome == "PASS":
            break

        variables = {
            "task_key": task_key,
            "target_file": target_file,
            "target_file_head": target_file_head,
            "plan_step_id": plan_step_id,
        }
        try:
            proposal = provider.complete(
                template="repair", variables=variables, schema=ImplementationResult
            )
            assert isinstance(proposal, ImplementationResult)
        except AIOutputInvalid:
            break  # no usable repair proposal -- stop, do not guess further

        ops_this_attempt: list[EditOp] = []
        try:
            for op in proposal.edit_ops:
                apply_edit_op(ws, op)
                ops_this_attempt.append(op)
        except EditorError:
            attempts.append(
                RepairAttempt(
                    iteration=i,
                    edit_ops=ops_this_attempt,
                    exec_result=exec_result,
                    outcome="NO_CHANGE",
                )
            )
            break  # the proposal could not even be applied -- stop

        applied_ops.extend(ops_this_attempt)
        new_result = sandbox.run_tests(ws, test_command)
        new_failed = len(new_result.failed_ids())

        if new_result.outcome == "PASS":
            outcome: RepairOutcome = "GREEN"
        elif new_failed < prev_failed:
            outcome = "IMPROVED"
        elif new_failed > prev_failed:
            outcome = "WORSENED"
        else:
            outcome = "NO_CHANGE"

        attempts.append(
            RepairAttempt(
                iteration=i,
                edit_ops=ops_this_attempt,
                exec_result=new_result,
                outcome=outcome,
            )
        )
        exec_result = new_result
        prev_failed = new_failed

    return RepairLoopResult(
        final_exec_result=exec_result, attempts=attempts, applied_ops=applied_ops
    )
