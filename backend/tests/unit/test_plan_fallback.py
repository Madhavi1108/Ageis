"""The deterministic rule-based fallback plan."""

from __future__ import annotations

from app.agents.planning import build_fallback_plan
from app.schemas.plan import EngineeringPlanAI


def test_fallback_is_schema_valid_and_low_confidence():
    plan = build_fallback_plan(
        candidate_files=["invoice.py", "utils.py"],
        candidate_symbols=["invoice.py::calculate_total"],
    )
    assert isinstance(plan, EngineeringPlanAI)
    assert plan.source == "RULE_BASED_FALLBACK"
    assert plan.confidence.value <= 0.3
    assert plan.confidence.basis == "UNKNOWN"
    assert plan.files_to_modify == ["invoice.py"]
    assert plan.symbols_to_modify == ["invoice.py::calculate_total"]
    assert plan.steps and plan.steps[0].test_intent.strip()
    assert plan.rollback_strategy.strip()


def test_fallback_with_no_candidates_has_empty_modify_set():
    plan = build_fallback_plan(candidate_files=[], candidate_symbols=[])
    assert plan.files_to_modify == []
    # still schema-valid + still has a step and a rollback
    assert plan.steps and plan.rollback_strategy
