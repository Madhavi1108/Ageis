"""Assemble the reduced Trust Report (v0). See docs/GOVERNANCE.md Section 6
and docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 1 deliverables.
"""

from __future__ import annotations

from typing import Literal

from aegis.analysis.mapping import Candidate
from aegis.debugging.repair_loop import RepairAttempt
from aegis.schemas.plan import EngineeringPlan
from aegis.schemas.testing import TestExecutionResult
from aegis.schemas.trust_report import EvidenceTrace, TrustReportV0
from aegis.schemas.verification import VerificationResult


def build_trust_report(
    *,
    task_repo: str,
    task_title: str,
    outcome: Literal["VERIFIED", "NOT_VERIFIED", "SAFE_STOP", "PARTIALLY_SUPPORTED"],
    candidates: list[Candidate] | None = None,
    plan: EngineeringPlan | None = None,
    exec_result: TestExecutionResult | None = None,
    verification: VerificationResult | None = None,
    repair_attempts: list[RepairAttempt] | None = None,
    limitations: list[str] | None = None,
    diff_text: str = "",
) -> TrustReportV0:
    repair_attempts = repair_attempts or []
    limitations = list(limitations or [])

    why_file = [c.path for c in (candidates or [])[:3]]
    why_change = plan.problem_interpretation if plan else "UNKNOWN"
    why_tests = (
        [f"{r.test_id}: {r.outcome}" for r in exec_result.results]
        if exec_result
        else []
    )
    if verification and verification.verdict == "VERIFIED":
        why_safe = (
            "issue tests pass; no unplanned files touched; patch re-applies cleanly"
        )
    elif verification:
        why_safe = "NOT safe to ship: " + "; ".join(
            f"{c.name}={c.verdict}"
            for c in verification.criteria
            if c.verdict == "FAIL"
        )
    else:
        why_safe = "verification did not run"

    mapping_summary = {
        "top_candidates": [
            {
                "path": c.path,
                "score": c.score,
                "evidence": [e.detail for e in c.evidence],
            }
            for c in (candidates or [])[:5]
        ]
    }

    tests_summary: dict = {}
    if exec_result:
        tests_summary = {
            "command": exec_result.command,
            "outcome": exec_result.outcome,
            "passed": sorted(exec_result.passed_ids()),
            "failed": sorted(exec_result.failed_ids()),
            "reason": exec_result.reason,
        }

    scores = {
        "note": "raw signals only; calibrated PCS/CRS is Phase 17",
        "repair_iterations": len(repair_attempts),
        "files_touched": (
            len(verification.plan_alignment.get("files_touched", []))
            if verification
            else 0
        ),
    }

    if outcome != "VERIFIED" and not limitations:
        limitations.append(
            f"outcome is {outcome}; see evidence_trace.why_safe for detail"
        )

    return TrustReportV0(
        task_repo=task_repo,
        task_title=task_title,
        outcome=outcome,
        evidence_trace=EvidenceTrace(
            why_file=why_file,
            why_change=why_change,
            why_tests=why_tests,
            why_safe=why_safe,
        ),
        mapping_summary=mapping_summary,
        diff_text=diff_text,
        plan_alignment=verification.plan_alignment if verification else {},
        tests=tests_summary,
        scores=scores,
        replay={
            "provider": None,
            "deterministic": True,
            "note": "full replay manifest is Phase 20",
        },
        limitations=limitations,
    )
