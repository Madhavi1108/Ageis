"""Verification Agent (reduced to the three mandatory criteria). See
docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 1 deliverables and Phase 18 (full
system). A task is never VERIFIED merely because code was generated
(Specification Rule: "never mark a task complete merely because code was
generated") -- every criterion here is independently, mechanically checked.
"""

from __future__ import annotations

from aegis.implementation.patcher import check_reapplies
from aegis.implementation.scope_tracker import unplanned_files
from aegis.repository.ingest import Snapshot
from aegis.repository.workspace import RWWorkspace
from aegis.schemas.common import Confidence, Evidence
from aegis.schemas.implementation import EditOp
from aegis.schemas.plan import EngineeringPlan
from aegis.schemas.testing import TestExecutionResult
from aegis.schemas.verification import Criterion, VerificationResult


def verify(
    *,
    plan: EngineeringPlan,
    snapshot: Snapshot,
    ws: RWWorkspace,
    exec_result: TestExecutionResult,
    all_edit_ops: list[EditOp],
) -> VerificationResult:
    criteria: list[Criterion] = []

    # 1. issue tests pass
    if exec_result.outcome == "PASS":
        criteria.append(
            Criterion(
                name="issue_tests_pass",
                verdict="PASS",
                detail=f"all {len(exec_result.results)} executed tests passed",
                evidence=[
                    Evidence(
                        kind="execution",
                        ref=exec_result.command,
                        detail="sandbox test run",
                    )
                ],
            )
        )
    else:
        criteria.append(
            Criterion(
                name="issue_tests_pass",
                verdict="FAIL",
                detail=f"execution outcome={exec_result.outcome}; failing={sorted(exec_result.failed_ids())}",
            )
        )

    # 2. no unplanned files
    unplanned = unplanned_files(snapshot, ws, plan.files_to_modify)
    criteria.append(
        Criterion(
            name="no_unplanned_files",
            verdict="PASS" if not unplanned else "FAIL",
            detail=(
                f"unplanned files: {sorted(unplanned)}" if unplanned else "scope clean"
            ),
        )
    )

    # 3. patch re-applies to a fresh clone of the original snapshot
    reapplies = check_reapplies(snapshot, all_edit_ops, ws)
    criteria.append(
        Criterion(
            name="patch_reapplies",
            verdict="PASS" if reapplies else "FAIL",
            detail=(
                "recorded edit-ops reproduce the final workspace from the original snapshot"
                if reapplies
                else "recorded edit-ops did not reproduce the final workspace"
            ),
        )
    )

    all_pass = all(c.verdict == "PASS" for c in criteria)
    verdict = "VERIFIED" if all_pass else "NOT_VERIFIED"
    confidence = Confidence(value=1.0 if all_pass else 0.0, basis="FACT")

    return VerificationResult(
        verdict=verdict,
        criteria=criteria,
        plan_alignment={
            "files_to_modify": plan.files_to_modify,
            "files_touched": sorted({op.path for op in all_edit_ops}),
        },
        confidence=confidence,
    )
