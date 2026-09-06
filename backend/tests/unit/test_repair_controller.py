"""Bounded repair-loop controller: green path, revert-on-worse, no-progress,
sandbox-unavailable, and the never-exceeds-max_iterations property."""

from __future__ import annotations

import random

import pytest

from aegis.schemas.common import Confidence, Evidence
from app.debugging.repair_loop import RunEval, run_repair
from app.schemas.execution import TestExecutionRun, TestOutcome
from app.schemas.failure import FailureAnalysis
from app.schemas.repair import (
    Hypothesis,
    RepairProposal,
    RootCauseAnalysis,
)


class _Settings:
    repair_max_iterations = 4
    repair_wall_clock_s = 999
    repair_min_improvement = 1
    ai_repair_timeout_s = 30.0
    ai_repair_max_tokens = 4000


def _run(ids, outcome="FAIL"):
    return TestExecutionRun(
        command="pytest",
        exit_code=0 if outcome == "PASS" else 1,
        outcome=outcome,
        results=[TestOutcome(test_id=i, outcome="FAIL") for i in ids],
    )


_RCA = RootCauseAnalysis(
    hypotheses=[
        Hypothesis(
            statement="the defect is in mod.py::f",
            label="HYPOTHESIS",
            evidence=[Evidence(kind="symbol", ref="mod.py::f", detail="frame")],
        )
    ],
    most_likely_index=0,
    open_questions=["what change fixes it?"],
    confidence=Confidence(value=0.4, basis="INFERENCE"),
)

_PROPOSAL = RepairProposal(
    target_hypothesis="the defect is in mod.py::f",
    edit_ops=[
        {
            "path": "mod.py",
            "op": "replace",
            "anchor": "return a + b + 1",
            "new": "return a + b",
            "plan_step_id": "repair",
            "rationale": "off-by-one",
            "evidence": [],
        }
    ],
    expected_effect="tests pass",
    risk_notes=[],
    confidence=Confidence(value=0.7, basis="INFERENCE"),
)


class _FakeProvider:
    name = "fake"

    def complete(self, *, template, **_kw):
        if template == "repair":
            return _PROPOSAL
        raise AssertionError(f"unexpected template {template}")


def _fa():
    return FailureAnalysis(
        task_id="t",
        execution_id="e",
        failures=[],
        facts=["execution v1 outcome = FAIL"],
        inferences=[],
        classification={
            "primary_test": "test_x",
            "primary_symbol_id": "mod.py::f",
            "primary_frame": {"file": "mod.py", "lineno": 3},
        },
        evidence={
            "code_slices": [],
            "diff_hunks": [],
            "related_tests": [],
            "recent_commits": [],
        },
        created_at="2026-09-06T00:00:00Z",
    )


def _scripted(script):
    box = {"i": 0}

    def runner(_ops):
        idx = min(box["i"], len(script) - 1)
        box["i"] += 1
        return script[idx]

    return runner


def _go(script, *, initial):
    return run_repair(
        provider=_FakeProvider(),
        settings=_Settings(),
        failure_analysis=_fa(),
        initial_run=initial,
        runner=_scripted(script),
        allowed_files=["mod.py"],
        task_key="t",
        rca=_RCA,
    )


def test_reaches_green_and_records_each_attempt():
    res = _go(
        [
            RunEval(run=_run(["t0", "t1"])),
            RunEval(run=_run(["t0"])),
            RunEval(run=_run([], "PASS")),
        ],
        initial=_run(["t0", "t1", "t2"]),
    )
    assert res.outcome == "REPAIRED"
    assert [a.outcome for a in res.attempts] == ["IMPROVED", "IMPROVED", "GREEN"]
    assert res.best_iteration == 3
    assert res.final_ops


def test_worsening_attempt_auto_reverts_then_safe_stops():
    res = _go(
        [RunEval(run=_run(["t0", "t1", "t2"])), RunEval(run=_run(["t0", "t1", "t2"]))],
        initial=_run(["t0", "t1"]),
    )
    assert res.outcome == "SAFE_STOP"
    assert res.best_iteration is None  # never improved on the original
    assert res.final_ops == []
    assert all(a.outcome == "WORSENED" for a in res.attempts)


def test_no_progress_aborts():
    res = _go(
        [RunEval(run=_run(["t0", "t1"])), RunEval(run=_run(["t0", "t1"]))],
        initial=_run(["t0", "t1"]),
    )
    assert res.outcome == "SAFE_STOP"
    assert "no progress" in res.safe_stop.reason
    assert len(res.attempts) == 1


def test_sandbox_unavailable_is_immediate_safe_stop():
    res = _go(
        [RunEval(run=_run([], "PARTIALLY_SUPPORTED"))], initial=_run(["t0", "t1"])
    )
    assert res.outcome == "SAFE_STOP"
    assert res.safe_stop.reason == "sandbox unavailable"
    assert res.attempts == []


def test_provider_none_uses_fallbacks_without_crashing():
    res = run_repair(
        provider=None,
        settings=_Settings(),
        failure_analysis=_fa(),
        initial_run=_run(["t0", "t1"]),
        runner=_scripted([RunEval(run=_run(["t0", "t1"]))]),
        allowed_files=["mod.py"],
        task_key="t",
    )
    # no code slice -> fallback proposal is None -> clean SAFE_STOP
    assert res.outcome == "SAFE_STOP"
    assert res.safe_stop.reason == "no usable repair proposal"


@pytest.mark.parametrize("seed", range(25))
def test_never_exceeds_max_iterations(seed):
    rng = random.Random(seed)
    script = [
        RunEval(
            run=_run(
                [f"t{i}" for i in range(rng.randint(0, 4))],
                rng.choice(["FAIL", "FAIL", "PASS"]),
            )
        )
        for _ in range(rng.randint(1, 12))
    ]
    res = _go(script, initial=_run(["t0", "t1", "t2"]))
    assert len(res.attempts) <= _Settings.repair_max_iterations
    assert res.outcome in ("REPAIRED", "SAFE_STOP")
