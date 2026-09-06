"""Plan-validation rules engine (each rule in isolation)."""

from __future__ import annotations

from app.agents.planning import validate_plan
from app.schemas.plan import EngineeringPlanAI

_SNAPSHOT = {"invoice.py", "utils.py", "test_invoice.py"}
_SCOPE = {"invoice.py"}


def _plan(**over):
    base = {
        "problem_interpretation": "x",
        "assumptions": ["a"],
        "files_to_inspect": ["invoice.py"],
        "files_to_modify": ["invoice.py"],
        "symbols_to_modify": [],
        "dependencies": [],
        "steps": [
            {
                "id": "s1",
                "description": "d",
                "test_intent": "cover the cap",
                "evidence_refs": [],
            }
        ],
        "test_strategy": {"approach": "boundary test"},
        "expected_behavior": "capped",
        "regression_risks": [],
        "rollback_strategy": "revert invoice.py",
        "source": "AI",
        "confidence": {"value": 0.8, "basis": "INFERENCE"},
        "evidence": [],
    }
    base.update(over)
    return EngineeringPlanAI.model_validate(base)


def _v(plan):
    return validate_plan(plan, snapshot_paths=_SNAPSHOT, allowed_scope=_SCOPE)


def test_clean_plan_approved():
    res = _v(_plan())
    assert res.verdict == "APPROVED"
    assert set(res.checked) >= {
        "schema",
        "files_exist",
        "scope_subset",
        "steps_have_tests",
        "rollback_present",
        "assumptions_nonempty",
    }


def test_missing_file_rejected():
    res = _v(_plan(files_to_modify=["invoice.py", "ghost.py"]))
    assert res.verdict == "REJECTED"
    assert res.checked["files_exist"] is False


def test_scope_escape_rejected():
    res = _v(_plan(files_to_modify=["utils.py"]))  # exists but outside scope
    assert res.verdict == "REJECTED"
    assert res.checked["scope_subset"] is False


def test_empty_modify_set_rejected():
    res = _v(_plan(files_to_modify=[]))
    assert res.verdict == "REJECTED"
    assert any("no files to modify" in r for r in res.reasons)


def test_step_without_test_intent_revise():
    res = _v(
        _plan(
            steps=[
                {
                    "id": "s1",
                    "description": "d",
                    "test_intent": "  ",
                    "evidence_refs": [],
                }
            ]
        )
    )
    assert res.verdict == "REVISE"
    assert res.checked["steps_have_tests"] is False


def test_no_rollback_revise():
    res = _v(_plan(rollback_strategy="   "))
    assert res.verdict == "REVISE"
    assert res.checked["rollback_present"] is False


def test_empty_assumptions_is_soft_only():
    res = _v(_plan(assumptions=[]))
    assert res.verdict == "APPROVED"
    assert res.checked["assumptions_nonempty"] is False
