"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 22): the repair ledger
reads like the Specification's example (Attempt 1 failed ... Attempt N passed)
and is deterministic across two runs.
"""

from __future__ import annotations

from aegis.schemas.common import Confidence, Evidence
from app.debugging.repair_loop import RunEval, run_repair
from app.schemas.execution import TestExecutionRun, TestOutcome
from app.schemas.failure import FailureAnalysis
from app.schemas.repair import Hypothesis, RepairProposal, RootCauseAnalysis


class _Settings:
    repair_max_iterations = 4
    repair_wall_clock_s = 999
    repair_min_improvement = 1
    ai_repair_timeout_s = 30.0
    ai_repair_max_tokens = 4000


_RCA = RootCauseAnalysis(
    hypotheses=[
        Hypothesis(
            statement="invoice.py::calculate_total does not cap the discount",
            label="INFERENCE",
            evidence=[
                Evidence(
                    kind="symbol",
                    ref="invoice.py::calculate_total",
                    detail="assertion detail",
                )
            ],
        )
    ],
    most_likely_index=0,
    open_questions=[],
    confidence=Confidence(value=0.6, basis="INFERENCE"),
)
_PROPOSAL = RepairProposal(
    target_hypothesis="cap the discount",
    edit_ops=[
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
            "plan_step_id": "repair",
            "rationale": "cap",
            "evidence": [],
        }
    ],
    expected_effect="passes",
    risk_notes=[],
    confidence=Confidence(value=0.7, basis="INFERENCE"),
)


class _Provider:
    name = "fake"

    def complete(self, *, template, **_kw):
        assert template == "repair"
        return _PROPOSAL


def _fa():
    return FailureAnalysis(
        task_id="t",
        execution_id="e",
        failures=[],
        facts=["execution v1 outcome = FAIL"],
        inferences=[],
        classification={
            "primary_test": "test_x",
            "primary_symbol_id": "invoice.py::calculate_total",
            "primary_frame": {"file": "invoice.py", "lineno": 8},
        },
        evidence={
            "code_slices": [],
            "diff_hunks": [],
            "related_tests": [],
            "recent_commits": [],
        },
        created_at="2026-09-06T00:00:00Z",
    )


def _run(ids, outcome="FAIL"):
    return TestExecutionRun(
        command="pytest",
        exit_code=0 if outcome == "PASS" else 1,
        outcome=outcome,
        results=[TestOutcome(test_id=i, outcome="FAIL") for i in ids],
    )


def _script_runner():
    script = [
        RunEval(run=_run(["t0", "t1"])),  # attempt 1: still failing (fewer)
        RunEval(run=_run(["t0"])),  # attempt 2: fewer still
        RunEval(run=_run([], "PASS")),  # attempt 3: green
    ]
    box = {"i": 0}

    def runner(_ops):
        r = script[min(box["i"], len(script) - 1)]
        box["i"] += 1
        return r

    return runner


def _go():
    return run_repair(
        provider=_Provider(),
        settings=_Settings(),
        failure_analysis=_fa(),
        initial_run=_run(["t0", "t1", "t2"]),
        runner=_script_runner(),
        allowed_files=["invoice.py"],
        task_key="t",
        rca=_RCA,
    )


def test_ledger_reads_like_the_spec_example_and_is_deterministic():
    a = _go()
    b = _go()

    assert a.outcome == "REPAIRED"
    assert [x.outcome for x in a.attempts] == ["IMPROVED", "IMPROVED", "GREEN"]
    assert a.best_iteration == 3
    assert [x.failing_after for x in a.attempts] == [2, 1, 0]

    # deterministic
    assert [x.outcome for x in a.attempts] == [x.outcome for x in b.attempts]
    assert [x.score for x in a.attempts] == [x.score for x in b.attempts]
    assert a.final_ops == b.final_ops

    # the RCA hypothesis is evidence-backed and never a bare FACT without evidence
    for h in a.rca.hypotheses:
        if h.label == "FACT":
            assert h.evidence
