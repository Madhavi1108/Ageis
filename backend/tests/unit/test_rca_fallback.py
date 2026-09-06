"""The deterministic RCA fallback never fabricates a FACT."""

from __future__ import annotations

from app.debugging.rca import analyze, build_fallback_rca
from app.schemas.failure import FailureAnalysis, FailureRecord
from app.schemas.repair import RootCauseAnalysis


def _fa():
    return FailureAnalysis(
        task_id="t",
        execution_id="e",
        failures=[
            FailureRecord(
                test_name="test_invoice.py::test_x",
                failure_type="ASSERTION",
                exception_type="AssertionError",
                message="10.0 != 50.0",
            )
        ],
        facts=["execution v1 outcome = FAIL"],
        inferences=[],
        classification={"primary_symbol_id": "invoice.py::calculate_total"},
        evidence={"code_slices": [], "diff_hunks": []},
        created_at="2026-09-06T00:00:00Z",
    )


def test_fallback_is_schema_valid_hypothesis_only():
    rca = build_fallback_rca(_fa())
    assert isinstance(rca, RootCauseAnalysis)
    assert len(rca.hypotheses) == 1
    assert rca.hypotheses[0].label == "HYPOTHESIS"  # never FACT
    assert "invoice.py::calculate_total" in rca.hypotheses[0].statement
    assert rca.confidence.value <= 0.3
    assert rca.open_questions


def test_analyze_with_no_provider_uses_fallback():
    rca = analyze(
        failure_analysis=_fa(), provider=None, settings=object(), task_key="t"
    )
    assert rca.hypotheses[0].label == "HYPOTHESIS"
