"""Phase 18 unit: the aggregate verdict + resulting state + confidence
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26, step 3).
"""

from __future__ import annotations

from app.verification.agent import verify
from app.verification.aggregate import aggregate
from app.verification._criterion import CriterionOutcome
from tests.unit.test_verification_criteria import _inp


def _c(name, verdict, mandatory=True):
    return CriterionOutcome(name=name, verdict=verdict, mandatory=mandatory)


def test_all_pass_is_verified_completed():
    crits = [_c(f"m{i}", "PASS") for i in range(6)] + [_c("score_gate", "PASS", False)]
    verdict, state, conf = aggregate(crits)
    assert verdict == "VERIFIED"
    assert state == "COMPLETED"
    assert conf.value == 1.0 and conf.basis == "FACT"


def test_one_mandatory_fail_is_not_verified_failed():
    crits = [_c("m0", "FAIL")] + [_c(f"m{i}", "PASS") for i in range(1, 6)]
    crits.append(_c("score_gate", "PASS", False))
    verdict, state, conf = aggregate(crits)
    assert verdict == "NOT_VERIFIED"
    assert state == "FAILED"
    assert conf.value == 1.0 and conf.basis == "FACT"


def test_score_gate_fail_is_partial_awaiting_approval():
    crits = [_c(f"m{i}", "PASS") for i in range(6)] + [_c("score_gate", "FAIL", False)]
    verdict, state, conf = aggregate(crits)
    assert verdict == "PARTIAL"
    assert state == "AWAITING_APPROVAL"
    assert conf.basis == "INFERENCE"


def test_mandatory_unknown_is_partial():
    crits = [_c("m0", "UNKNOWN")] + [_c(f"m{i}", "PASS") for i in range(1, 6)]
    crits.append(_c("score_gate", "PASS", False))
    verdict, state, _ = aggregate(crits)
    assert verdict == "PARTIAL" and state == "AWAITING_APPROVAL"


def test_mandatory_fail_beats_unknown():
    crits = [_c("m0", "UNKNOWN"), _c("m1", "FAIL")] + [
        _c(f"m{i}", "PASS") for i in range(2, 6)
    ]
    crits.append(_c("score_gate", "UNKNOWN", False))
    verdict, state, _ = aggregate(crits)
    assert verdict == "NOT_VERIFIED" and state == "FAILED"


def test_verify_end_to_end_all_green():
    comp = verify(_inp())
    assert comp.verdict == "VERIFIED"
    assert comp.resulting_state == "COMPLETED"
    assert len(comp.criteria) == 7
    assert comp.trace["why_change"] == "cap the discount"
    assert comp.alignment["steps_total"] == 1


def test_verify_end_to_end_failing_tests_not_verified():
    comp = verify(_inp(execution_results=[{"test_id": "t1", "outcome": "FAIL"}]))
    assert comp.verdict == "NOT_VERIFIED"
    assert comp.resulting_state == "FAILED"
    assert "acceptance_tests_pass" in comp.trace["why_safe"]
