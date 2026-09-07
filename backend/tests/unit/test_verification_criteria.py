"""Phase 18 unit: each verification criterion evaluator on PASS / FAIL /
UNKNOWN fixtures (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26 "Phase-wise
testing" Unit bullet).
"""

from __future__ import annotations

import dataclasses

from app.verification import criteria as crit
from app.verification._criterion import VerificationInputs


def _inp(**overrides) -> VerificationInputs:
    base = dict(
        task_id="task-1",
        implementation_version=1,
        snapshot_id="snap-1",
        expected_behavior="discount is capped at 0.5",
        problem_interpretation="cap the discount",
        rollback_strategy="revert invoice.py",
        plan_steps=[{"id": "s1", "description": "clamp", "test_intent": "90==50"}],
        traceability={"s1": ["invoice.py"]},
        scope_violations=[],
        touched_files=["invoice.py"],
        allowed_scope=["invoice.py"],
        candidate_paths=["invoice.py"],
        has_issue_tests=True,
        execution_outcome="PASS",
        execution_command="pytest -q",
        execution_id="exec-1",
        execution_results=[{"test_id": "t1", "outcome": "PASS"}],
        targeted_test_ids=["t1"],
        regression_present=True,
        regression_mode="full",
        regression_new_failures=[],
        regression_subset_justification=None,
        regression_full_suite_count=12,
        regression_results=[{"test_id": "t1", "outcome": "PASS"}],
        reapplies=True,
        review_present=True,
        review_blocking=False,
        review_blocking_findings=[],
        pcs_value=90,
        crs_value=10,
        pcs_min=70,
        crs_max=49,
    )
    base.update(overrides)
    return VerificationInputs(**base)


# --- acceptance --------------------------------------------------------------- #


def test_acceptance_pass():
    assert crit.check_acceptance(_inp()).verdict == "PASS"


def test_acceptance_fail_on_failing_test():
    inp = _inp(execution_results=[{"test_id": "t1", "outcome": "FAIL"}])
    out = crit.check_acceptance(inp)
    assert out.verdict == "FAIL" and out.mandatory


def test_acceptance_unknown_without_tests():
    assert crit.check_acceptance(_inp(has_issue_tests=False)).verdict == "UNKNOWN"


def test_acceptance_unknown_when_sandbox_unavailable():
    assert (
        crit.check_acceptance(_inp(execution_outcome="PARTIALLY_SUPPORTED")).verdict
        == "UNKNOWN"
    )


def test_acceptance_falls_back_to_all_results_without_targeted_ids():
    inp = _inp(targeted_test_ids=[], execution_results=[{"test_id": "x", "outcome": "PASS"}])
    assert crit.check_acceptance(inp).verdict == "PASS"


# --- suite ------------------------------------------------------------------- #


def test_suite_green_full_pass():
    assert crit.check_suite_green(_inp()).verdict == "PASS"


def test_suite_green_fail_on_new_failures():
    out = crit.check_suite_green(_inp(regression_new_failures=["t9"]))
    assert out.verdict == "FAIL"


def test_suite_green_unknown_without_plan():
    assert crit.check_suite_green(_inp(regression_present=False)).verdict == "UNKNOWN"


def test_suite_green_smart_without_justification_still_passes():
    # the selector only omits FULL-only tests *with* a justification; a smart
    # run with none means nothing was omitted.
    out = crit.check_suite_green(
        _inp(regression_mode="smart", regression_subset_justification=None)
    )
    assert out.verdict == "PASS"
    ok = crit.check_suite_green(
        _inp(regression_mode="smart", regression_subset_justification="FULL-only omitted")
    )
    assert ok.verdict == "PASS" and "omitted" in ok.detail


# --- reapplies ------------------------------------------------------------- #


def test_reapplies_pass_fail_unknown():
    assert crit.check_patch_reapplies(_inp(reapplies=True)).verdict == "PASS"
    assert crit.check_patch_reapplies(_inp(reapplies=False)).verdict == "FAIL"
    assert crit.check_patch_reapplies(_inp(reapplies=None)).verdict == "UNKNOWN"


# --- scope --------------------------------------------------------------- #


def test_scope_clean_and_violation():
    assert crit.check_scope(_inp()).verdict == "PASS"
    out = crit.check_scope(_inp(scope_violations=["secrets.py"]))
    assert out.verdict == "FAIL"
    assert out.evidence and out.evidence[0].ref == "secrets.py"


# --- review ------------------------------------------------------------- #


def test_review_clean_pass_fail_unknown():
    assert crit.check_review(_inp()).verdict == "PASS"
    assert crit.check_review(_inp(review_present=False)).verdict == "UNKNOWN"
    out = crit.check_review(_inp(review_blocking=True, review_blocking_findings=["CRITICAL SECURITY x"]))
    assert out.verdict == "FAIL"


# --- plan alignment ---------------------------------------------------- #


def test_plan_alignment_pass():
    assert crit.check_plan_alignment(_inp()).verdict == "PASS"


def test_plan_alignment_fail_on_unimplemented_step():
    inp = _inp(
        plan_steps=[{"id": "s1"}, {"id": "s2"}],
        traceability={"s1": ["invoice.py"]},
    )
    out = crit.check_plan_alignment(inp)
    assert out.verdict == "FAIL" and "s2" in out.detail


def test_plan_alignment_fail_on_unplanned_file():
    inp = _inp(touched_files=["invoice.py", "extra.py"])
    out = crit.check_plan_alignment(inp)
    assert out.verdict == "FAIL" and "extra.py" in out.detail


# --- score gate ------------------------------------------------------- #


def test_score_gate_pass_fail_unknown_and_is_advisory():
    p = crit.check_score_gate(_inp())
    assert p.verdict == "PASS" and p.mandatory is False
    assert crit.check_score_gate(_inp(pcs_value=50)).verdict == "FAIL"
    assert crit.check_score_gate(_inp(crs_value=80)).verdict == "FAIL"
    assert crit.check_score_gate(_inp(pcs_value=None)).verdict == "UNKNOWN"


def test_evaluate_all_returns_seven_in_order():
    outs = crit.evaluate_all(_inp())
    assert [o.name for o in outs] == [
        "acceptance_tests_pass",
        "suite_green",
        "patch_reapplies",
        "scope_clean",
        "review_clean",
        "plan_alignment",
        "score_gate",
    ]
    assert all(dataclasses.is_dataclass(o) for o in outs)
