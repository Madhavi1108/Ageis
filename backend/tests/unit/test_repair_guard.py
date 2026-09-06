"""Repair-loop guards: budgets, no-progress, scoring."""

from __future__ import annotations

import time

from app.debugging.guard import (
    LoopBudget,
    failure_signature,
    no_progress,
    score,
)
from app.schemas.execution import TestExecutionRun, TestOutcome


def _run(ids, outcome="FAIL"):
    return TestExecutionRun(
        command="pytest",
        exit_code=0 if outcome == "PASS" else 1,
        outcome=outcome,
        results=[TestOutcome(test_id=i, outcome="FAIL") for i in ids],
    )


def test_iteration_budget():
    b = LoopBudget.start(max_iterations=3, wall_clock_s=999)
    assert b.iteration_exhausted(4) is True
    assert b.iteration_exhausted(3) is False


def test_wall_clock_budget():
    b = LoopBudget(max_iterations=3, wall_clock_s=10, started_at=time.monotonic())
    assert b.wall_clock_exhausted(now=b.started_at + 11) is True
    assert b.wall_clock_exhausted(now=b.started_at + 5) is False


def test_failure_signature_is_order_independent():
    a = failure_signature(_run(["t1", "t2"]))
    b = failure_signature(_run(["t2", "t1"]))
    assert a == b
    assert failure_signature(_run(["t1"])) != a


def test_no_progress_on_repeat():
    assert no_progress(["x"]) is False
    assert no_progress(["x", "y"]) is False
    assert no_progress(["x", "y", "y"]) is True


def test_score_is_lexicographic():
    better = score(_run(["t1"]), regression_failures=0, diff_size=100)
    worse = score(_run(["t1", "t2"]), regression_failures=0, diff_size=1)
    assert better < worse
    # tie on failing count -> regression failures break it
    assert score(_run(["t1"]), regression_failures=0, diff_size=5) < score(
        _run(["t1"]), regression_failures=1, diff_size=5
    )
