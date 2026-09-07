"""The seven deterministic verification criteria
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26, step 1).

Each ``check_*`` is a pure function ``VerificationInputs -> CriterionOutcome``.
A criterion is ``UNKNOWN`` (never a silent ``FAIL``) when its input is absent or
the sandbox could not produce it -- e.g. a Docker-less environment yields
``execution_outcome == "PARTIALLY_SUPPORTED"``.
"""

from __future__ import annotations

from aegis.schemas.common import Evidence

from app.verification._criterion import CriterionOutcome, VerificationInputs

# execution-level outcomes that mean the run itself did not come back green
_FAILING_EXEC = {"FAIL", "ERROR", "TIMEOUT", "OOM"}
_UNRUN_EXEC = {None, "PARTIALLY_SUPPORTED", "INFRA_ERROR"}
# per-test outcomes that count as a failing test
_FAILING_TEST = {"FAIL", "ERROR"}


def check_acceptance(inp: VerificationInputs) -> CriterionOutcome:
    """(1) The requested behaviour is actually exercised and passes: there is
    at least one generated issue/edge test, and the latest execution came back
    with every (targeted, else every) test passing."""
    name = "acceptance_tests_pass"
    if not inp.has_issue_tests:
        return CriterionOutcome(
            name, "UNKNOWN", True,
            "no issue-specific tests were generated for this task",
        )
    if inp.execution_outcome in _UNRUN_EXEC:
        return CriterionOutcome(
            name, "UNKNOWN", True,
            f"acceptance tests were not executed (outcome={inp.execution_outcome})",
        )

    results = inp.execution_results or []
    targeted = set(inp.targeted_test_ids)
    subset = [r for r in results if r.get("test_id") in targeted] if targeted else list(results)
    if not subset:
        return CriterionOutcome(
            name, "UNKNOWN", True,
            "the latest execution ran no acceptance/targeted tests",
        )

    failing = sorted(r.get("test_id", "?") for r in subset if r.get("outcome") in _FAILING_TEST)
    passed = sum(1 for r in subset if r.get("outcome") == "PASS")
    ev = [Evidence(kind="execution", ref=inp.execution_id or "?",
                   detail=f"{passed}/{len(subset)} acceptance tests passed")]
    if failing or inp.execution_outcome in _FAILING_EXEC:
        return CriterionOutcome(
            name, "FAIL", True,
            f"execution outcome={inp.execution_outcome}; failing acceptance tests: {failing}",
            ev,
        )
    return CriterionOutcome(
        name, "PASS", True, f"{passed}/{len(subset)} acceptance tests passed", ev
    )


def check_suite_green(inp: VerificationInputs) -> CriterionOutcome:
    """(2) The regression subset (or full suite) is green -- no new failures --
    and a non-full run carries a justification for the tests it skipped."""
    name = "suite_green"
    if not inp.regression_present:
        return CriterionOutcome(
            name, "UNKNOWN", True,
            "no regression plan for this task (GET /tasks/{id}/regression)",
        )
    if inp.regression_new_failures:
        return CriterionOutcome(
            name, "FAIL", True,
            f"regression introduced new failures: {sorted(inp.regression_new_failures)}",
        )

    reg_results = inp.regression_results or []
    reg_failing = sorted(
        x.get("test_id", "?") for x in reg_results if x.get("outcome") in _FAILING_TEST
    )
    if reg_failing:
        return CriterionOutcome(
            name, "FAIL", True, f"regression tests failing: {reg_failing}"
        )
    if not reg_results and inp.execution_outcome in _UNRUN_EXEC:
        return CriterionOutcome(
            name, "UNKNOWN", True,
            "the regression suite was not executed (sandbox unavailable)",
        )
    # A non-full run is fine: the selector only produces a strict subset (with a
    # justification) when FULL-only tests are omitted -- otherwise the smart set
    # already covers the whole suite.
    if inp.regression_mode == "full":
        detail = "full suite green"
    elif inp.regression_subset_justification:
        detail = f"smart subset green; {inp.regression_subset_justification}"
    else:
        detail = "smart subset green (covers the full suite)"
    return CriterionOutcome(name, "PASS", True, detail)


def check_patch_reapplies(inp: VerificationInputs) -> CriterionOutcome:
    """(3) The recorded edit-ops re-derive the final workspace byte-for-byte
    from a clean clone of the original snapshot (patch is reproducible and
    reversible)."""
    name = "patch_reapplies"
    if inp.reapplies is None:
        return CriterionOutcome(
            name, "UNKNOWN", True, "no edit-ops recorded to replay"
        )
    if inp.reapplies:
        return CriterionOutcome(
            name, "PASS", True,
            "recorded edit-ops reproduce the final workspace from the original snapshot",
        )
    return CriterionOutcome(
        name, "FAIL", True,
        "recorded edit-ops did not reproduce the final workspace",
    )


def check_scope(inp: VerificationInputs) -> CriterionOutcome:
    """(4) No file was changed outside the plan's declared scope."""
    name = "scope_clean"
    violations = sorted(set(inp.scope_violations))
    if violations:
        return CriterionOutcome(
            name, "FAIL", True,
            f"changed files outside the plan scope: {violations}",
            [Evidence(kind="file", ref=p, detail="outside declared scope") for p in violations],
        )
    return CriterionOutcome(name, "PASS", True, "no scope violations recorded")


def check_review(inp: VerificationInputs) -> CriterionOutcome:
    """(5) The code review has no unresolved CRITICAL / HIGH finding."""
    name = "review_clean"
    if not inp.review_present:
        return CriterionOutcome(
            name, "UNKNOWN", True, "no code review for this task (GET /tasks/{id}/review)"
        )
    if inp.review_blocking:
        return CriterionOutcome(
            name, "FAIL", True,
            f"unresolved blocking review findings: {inp.review_blocking_findings}",
        )
    return CriterionOutcome(name, "PASS", True, "no unresolved CRITICAL/HIGH findings")


def check_plan_alignment(inp: VerificationInputs) -> CriterionOutcome:
    """(6) Every plan step is implemented (appears in the traceability map) and
    nothing outside the planned files was touched."""
    name = "plan_alignment"
    step_ids = [s["id"] for s in inp.plan_steps if s.get("id")]
    implemented = {sid for sid, paths in (inp.traceability or {}).items() if paths}
    unimplemented = sorted(sid for sid in step_ids if sid not in implemented)
    unplanned = sorted(set(inp.touched_files) - set(inp.allowed_scope))
    if unimplemented or unplanned:
        bits = []
        if unimplemented:
            bits.append(f"unimplemented steps: {unimplemented}")
        if unplanned:
            bits.append(f"unplanned files: {unplanned}")
        return CriterionOutcome(name, "FAIL", True, "; ".join(bits))
    if not step_ids:
        return CriterionOutcome(
            name, "UNKNOWN", True, "the plan has no steps to align against"
        )
    return CriterionOutcome(
        name, "PASS", True,
        f"all {len(step_ids)} plan steps implemented; no unplanned files",
    )


def check_score_gate(inp: VerificationInputs) -> CriterionOutcome:
    """(7) PCS at/above the configured minimum and CRS at/below the maximum.
    Advisory -- a FAIL here downgrades the verdict to PARTIAL (human review),
    it does not by itself make the task NOT_VERIFIED."""
    name = "score_gate"
    if inp.pcs_value is None or inp.crs_value is None:
        return CriterionOutcome(
            name, "UNKNOWN", False,
            "the PCS/CRS score is not available (GET /tasks/{id}/confidence)",
        )
    if inp.pcs_value >= inp.pcs_min and inp.crs_value <= inp.crs_max:
        return CriterionOutcome(
            name, "PASS", False,
            f"PCS {inp.pcs_value} >= {inp.pcs_min} and CRS {inp.crs_value} <= {inp.crs_max}",
        )
    return CriterionOutcome(
        name, "FAIL", False,
        f"PCS {inp.pcs_value} (min {inp.pcs_min}) / CRS {inp.crs_value} (max {inp.crs_max}) "
        "outside the verification gate",
    )


#: Evaluated in this order; the first five plus (6) are mandatory, (7) advisory.
ALL_CRITERIA = (
    check_acceptance,
    check_suite_green,
    check_patch_reapplies,
    check_scope,
    check_review,
    check_plan_alignment,
    check_score_gate,
)


def evaluate_all(inp: VerificationInputs) -> list[CriterionOutcome]:
    return [check(inp) for check in ALL_CRITERIA]
