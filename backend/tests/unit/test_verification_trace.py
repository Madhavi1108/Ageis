"""Phase 18 unit: the explainability-trace generator shape
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26, step 4).
"""

from __future__ import annotations

from app.verification import criteria as crit
from app.verification.trace import build_trace
from tests.unit.test_verification_criteria import _inp


def test_trace_has_all_four_fields_on_a_clean_run():
    inp = _inp()
    t = build_trace(inp, crit.evaluate_all(inp))
    assert t.why_file == ["invoice.py"]
    assert t.why_change == "cap the discount"
    assert t.why_test == ["t1: PASS"]
    assert "acceptance tests pass" in t.why_safe
    assert "revert invoice.py" in t.why_safe


def test_trace_why_safe_names_failing_criteria():
    inp = _inp(scope_violations=["secrets.py"])
    t = build_trace(inp, crit.evaluate_all(inp))
    assert "NOT safe to ship" in t.why_safe
    assert "scope_clean" in t.why_safe


def test_trace_why_safe_flags_unknown_for_human_review():
    inp = _inp(execution_outcome="PARTIALLY_SUPPORTED", regression_present=False)
    t = build_trace(inp, crit.evaluate_all(inp))
    assert "human review" in t.why_safe


def test_trace_falls_back_to_touched_files_without_candidates():
    inp = _inp(candidate_paths=[], touched_files=["a.py", "b.py"])
    t = build_trace(inp, crit.evaluate_all(inp))
    assert t.why_file == ["a.py", "b.py"]
