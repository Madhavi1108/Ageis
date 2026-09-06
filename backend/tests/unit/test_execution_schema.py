"""TestExecutionRun helper methods (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20)."""

from __future__ import annotations

from app.schemas.execution import TestExecutionRun, TestOutcome


def test_passed_and_failed_ids():
    run = TestExecutionRun(
        command="pytest test_a.py",
        exit_code=1,
        outcome="FAIL",
        results=[
            TestOutcome(test_id="test_a.py::test_pass", outcome="PASS"),
            TestOutcome(test_id="test_a.py::test_fail", outcome="FAIL"),
            TestOutcome(test_id="test_a.py::test_error", outcome="ERROR"),
            TestOutcome(test_id="test_a.py::test_skip", outcome="SKIPPED"),
        ],
    )
    assert run.passed_ids() == {"test_a.py::test_pass"}
    assert run.failed_ids() == {"test_a.py::test_fail", "test_a.py::test_error"}
