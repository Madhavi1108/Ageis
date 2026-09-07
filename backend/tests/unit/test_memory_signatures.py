"""Phase 20 unit: the pure failure-signature + fix-summary derivation."""

from __future__ import annotations

from types import SimpleNamespace

from app.memory.signatures import failure_signatures, fix_summary


def test_failure_signatures_from_investigation_and_frames():
    inv = SimpleNamespace(
        classification={
            "primary_test": "test_invoice.py::test_clamp",
            "primary_symbol_id": "invoice.py::calculate_total",
        }
    )
    failures = [
        {
            "failure_type": "ASSERTION",
            "frames": [
                {"file": "invoice.py", "symbol_id": "invoice.py::calculate_total", "in_diff": True}
            ],
        }
    ]
    sigs = failure_signatures(inv, failures, None)
    assert "test_invoice.py::test_clamp@invoice.py::calculate_total" in sigs
    assert "ASSERTION@invoice.py::calculate_total" in sigs


def test_failure_signatures_empty_inputs():
    assert failure_signatures(None, [], None) == []


def test_failure_signatures_includes_safe_stop_summary():
    sigs = failure_signatures(
        None, [], {"outcome": "SAFE_STOP", "safe_stop": {"failure_summary": "t -> s"}}
    )
    assert sigs == ["t -> s"]


def test_fix_summary_verified_uses_plan_and_trace():
    plan = SimpleNamespace(problem_interpretation="cap discount at 0.5")
    verification = SimpleNamespace(trace={"why_change": "clamp before applying"})
    out = fix_summary(plan, verification, None, "VERIFIED")
    assert "cap discount at 0.5" in out
    assert "clamp before applying" in out


def test_fix_summary_safe_stop_uses_reason_and_action():
    plan = SimpleNamespace(problem_interpretation="round halves up")
    repair = {
        "outcome": "SAFE_STOP",
        "safe_stop": {
            "reason": "no-progress: repeated failure signature",
            "recommended_human_action": "inspect round_half_up manually",
        },
    }
    out = fix_summary(plan, None, repair, "SAFE_STOP")
    assert "Safe-stopped: no-progress" in out
    assert "inspect round_half_up manually" in out


def test_fix_summary_falls_back_when_nothing_available():
    assert fix_summary(None, None, None, "VERIFIED") == "(verified, no summary)"
