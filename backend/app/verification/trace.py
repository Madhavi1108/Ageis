"""The explainability trace (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26,
step 4; docs/GOVERNANCE.md Section 6 "why file / why change / why test / why
safe").

Ported from ``aegis/verification/trust.py::build_trust_report`` -- the reduced
``EvidenceTrace`` assembly, driven off the plan, the mapping candidates, the
latest execution results, and the criteria outcomes.
"""

from __future__ import annotations

from app.schemas.verification import ExplainabilityTrace
from app.verification._criterion import CriterionOutcome, VerificationInputs


def build_trace(
    inp: VerificationInputs, criteria: list[CriterionOutcome]
) -> ExplainabilityTrace:
    why_file = list(inp.candidate_paths[:5]) or sorted(inp.touched_files)[:5]
    why_change = inp.problem_interpretation or "UNKNOWN"
    why_test = [
        f"{r.get('test_id', '?')}: {r.get('outcome', '?')}"
        for r in (inp.execution_results or [])
    ]

    failing = [c for c in criteria if c.verdict == "FAIL"]
    unknown = [c for c in criteria if c.verdict == "UNKNOWN" and c.mandatory]
    if failing:
        why_safe = "NOT safe to ship: " + "; ".join(
            f"{c.name}={c.detail}" for c in failing
        )
    elif unknown:
        why_safe = (
            "needs human review -- could not verify: "
            + ", ".join(c.name for c in unknown)
            + f". Rollback: {inp.rollback_strategy or 'n/a'}"
        )
    else:
        why_safe = (
            "acceptance tests pass; regression suite green; patch re-applies "
            "cleanly; scope and plan aligned; review clean. "
            f"Rollback: {inp.rollback_strategy or 'n/a'}"
        )

    return ExplainabilityTrace(
        why_file=why_file,
        why_change=why_change,
        why_test=why_test,
        why_safe=why_safe,
    )
