"""The SAFE_STOP payload carries the fields a human needs to take over."""

from __future__ import annotations

from aegis.schemas.common import Confidence, Evidence
from app.debugging.repair_loop import RunEval, run_repair
from app.schemas.execution import TestExecutionRun, TestOutcome
from app.schemas.failure import FailureAnalysis
from app.schemas.repair import (
    Hypothesis,
    RepairProposal,
    RootCauseAnalysis,
    SafeStop,
)


class _Settings:
    repair_max_iterations = 2
    repair_wall_clock_s = 999
    repair_min_improvement = 1
    ai_repair_timeout_s = 30.0
    ai_repair_max_tokens = 4000


class _Provider:
    name = "fake"

    def complete(self, *, template, **_kw):
        return RepairProposal(
            target_hypothesis="h",
            edit_ops=[
                {
                    "path": "mod.py",
                    "op": "replace",
                    "anchor": "x",
                    "new": "y",
                    "plan_step_id": "repair",
                    "rationale": "r",
                    "evidence": [],
                }
            ],
            expected_effect="e",
            risk_notes=[],
            confidence=Confidence(value=0.5, basis="INFERENCE"),
        )


def test_safe_stop_payload_shape():
    fa = FailureAnalysis(
        task_id="t",
        execution_id="e",
        failures=[],
        facts=["f"],
        inferences=[],
        classification={
            "primary_test": "test_x",
            "primary_symbol_id": "mod.py::f",
            "primary_frame": {"file": "mod.py", "lineno": 1},
        },
        evidence={"code_slices": [], "diff_hunks": ["diff --git a/mod.py b/mod.py"]},
        created_at="2026-09-06T00:00:00Z",
    )
    rca = RootCauseAnalysis(
        hypotheses=[
            Hypothesis(
                statement="h",
                label="HYPOTHESIS",
                evidence=[Evidence(kind="test", ref="t", detail="d")],
            )
        ],
        most_likely_index=0,
        open_questions=["is it the cap?"],
        confidence=Confidence(value=0.3, basis="UNKNOWN"),
    )
    run = TestExecutionRun(
        command="pytest",
        exit_code=1,
        outcome="FAIL",
        results=[TestOutcome(test_id="t0", outcome="FAIL")],
    )
    res = run_repair(
        provider=_Provider(),
        settings=_Settings(),
        failure_analysis=fa,
        initial_run=run,
        runner=lambda _ops: RunEval(run=run),  # never improves -> budget exhausted
        allowed_files=["mod.py"],
        task_key="t",
        rca=rca,
    )
    assert res.outcome == "SAFE_STOP"
    ss = res.safe_stop
    assert isinstance(ss, SafeStop)
    assert ss.reason
    assert ss.failure_summary
    assert isinstance(ss.evidence, dict) and "diff_hunks" in ss.evidence
    assert ss.remaining_uncertainty == ["is it the cap?"]
    assert ss.recommended_human_action
    assert isinstance(ss.attempted_fixes, list)
