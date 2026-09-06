"""Bounded autonomous-repair loop controller (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 22). Thickened from backend/aegis/debugging/repair_loop.py.

Pure of DB / HTTP: the caller (app/services/repair.py) supplies a ``runner``
callable that applies candidate edit-ops to a throwaway workspace, runs the
targeted tests, and returns a ``RunEval``. The loop owns budgets, no-progress
detection, candidate scoring, auto-revert, and the SAFE_STOP payload.

Termination is exactly one of:
  * GREEN   -> outcome REPAIRED
  * iteration budget exhausted / wall-clock exhausted
  * no progress (repeated failure signature)
  * diminishing returns (two consecutive non-improving iterations)
  * no usable repair proposal
  * sandbox unavailable
The last five all produce outcome SAFE_STOP with an evidence payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from aegis.schemas.common import Confidence
from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.ai.schema_guard import AIOutputInvalid
from app.debugging import hypotheses as hypotheses_mod
from app.debugging import rca as rca_mod
from app.debugging.guard import LoopBudget, failure_signature, no_progress, score
from app.schemas.execution import TestExecutionRun
from app.schemas.failure import FailureAnalysis
from app.schemas.implementation import EditOp
from app.schemas.repair import (
    Hypothesis,
    RepairProposal,
    RootCauseAnalysis,
    SafeStop,
)

_REPAIR_TEMPLATE = "repair"


@dataclass
class RunEval:
    """What ``runner(ops)`` returns: the sandbox result plus the derived
    diff size and any scope violations for that candidate."""

    run: TestExecutionRun
    diff_size: int = 0
    scope_violations: list[str] = field(default_factory=list)
    applied: bool = True


@dataclass
class LoopAttempt:
    iteration: int
    outcome: str
    hypothesis: str
    root_cause: dict
    proposal: dict
    edit_ops: list[dict]
    failing_before: int
    failing_after: int
    regression_failures: int
    diff_size: int
    score: tuple[int, int, int]
    run: TestExecutionRun | None


@dataclass
class RepairLoopResult:
    outcome: str  # "REPAIRED" | "SAFE_STOP"
    best_iteration: int | None
    final_ops: list[EditOp]
    attempts: list[LoopAttempt]
    safe_stop: SafeStop | None
    rca: RootCauseAnalysis


@dataclass
class _Best:
    iteration: int | None
    ops: list[EditOp]
    run: TestExecutionRun
    score: tuple[int, int, int]


Runner = Callable[[list[EditOp]], RunEval]


# --------------------------------------------------------------------------- #
# Repair proposal (AI or heuristic fallback)
# --------------------------------------------------------------------------- #


def _primary_anchor(failure_analysis: FailureAnalysis) -> str | None:
    """The source line the failure points at, extracted from the Phase 13
    code slice (``">> <lineno> | <code>"``)."""
    slices = (
        failure_analysis.evidence.get("code_slices", [])
        if isinstance(failure_analysis.evidence, dict)
        else []
    )
    for s in slices:
        for line in (s.get("slice") or "").splitlines():
            if line.startswith(">>"):
                after = line.split("|", 1)
                if len(after) == 2 and after[1].strip():
                    return after[1].strip()
    return None


def build_fallback_proposal(
    hypothesis: Hypothesis, failure_analysis: FailureAnalysis, allowed_files: list[str]
) -> RepairProposal | None:
    anchor = _primary_anchor(failure_analysis)
    primary_file = (failure_analysis.classification or {}).get("primary_frame") or {}
    path = primary_file.get("file")
    if not anchor or not path or (allowed_files and path not in allowed_files):
        return None
    return RepairProposal(
        target_hypothesis=hypothesis.statement,
        edit_ops=[
            EditOp(
                path=path,
                op="replace",
                anchor=anchor,
                new=f"{anchor}  # AEGIS: heuristic repair attempt (low confidence)",
                plan_step_id="repair",
                rationale="no repair model configured; marking the implicated line",
                evidence=[],
            )
        ],
        expected_effect="none guaranteed -- heuristic marker only",
        risk_notes=["no verified root cause; unlikely to fix the failure"],
        confidence=Confidence(value=0.15, basis="UNKNOWN"),
        evidence=[],
    )


def _propose(
    provider: AIProvider | None,
    settings,
    *,
    hypothesis: Hypothesis,
    failure_analysis: FailureAnalysis,
    allowed_files: list[str],
    task_key: str,
) -> RepairProposal | None:
    if provider is None:
        return build_fallback_proposal(hypothesis, failure_analysis, allowed_files)
    primary_frame = (failure_analysis.classification or {}).get("primary_frame") or {}
    variables = {
        "task_key": task_key,
        "hypothesis": hypothesis.statement,
        "primary_frame": f"{primary_frame.get('file')}:{primary_frame.get('lineno')}",
        "allowed_files": "\n".join(allowed_files) or "(none)",
        "code_slice": rca_mod._code_context(failure_analysis),
    }
    try:
        result = provider.complete(
            template=_REPAIR_TEMPLATE,
            variables=variables,
            schema=RepairProposal,
            tier=tier_for("implementation"),
            timeout_s=settings.ai_repair_timeout_s,
            max_tokens=settings.ai_repair_max_tokens,
        )
    except AIOutputInvalid:
        return None
    assert isinstance(result, RepairProposal)
    return result


# --------------------------------------------------------------------------- #
# Controller
# --------------------------------------------------------------------------- #


def _safe_stop(
    reason: str,
    *,
    failure_analysis: FailureAnalysis,
    rca: RootCauseAnalysis,
    attempts: list[LoopAttempt],
) -> SafeStop:
    return SafeStop(
        reason=reason,
        failure_summary=(
            failure_analysis.classification.get("primary_test", "<unknown>")
            + " -> "
            + str(failure_analysis.classification.get("primary_symbol_id"))
        ),
        evidence=(
            failure_analysis.evidence
            if isinstance(failure_analysis.evidence, dict)
            else {}
        ),
        attempted_fixes=[
            {
                "iteration": a.iteration,
                "hypothesis": a.hypothesis,
                "outcome": a.outcome,
                "edit_ops": a.edit_ops,
            }
            for a in attempts
        ],
        remaining_uncertainty=list(rca.open_questions),
        recommended_human_action=(
            "Review the failing test and the implicated symbol; the automated loop "
            f"stopped ({reason}) without a verified fix."
        ),
    )


def run_repair(
    *,
    provider: AIProvider | None,
    settings,
    failure_analysis: FailureAnalysis,
    initial_run: TestExecutionRun,
    runner: Runner,
    allowed_files: list[str],
    task_key: str,
    rca: RootCauseAnalysis | None = None,
) -> RepairLoopResult:
    budget = LoopBudget.start(
        max_iterations=settings.repair_max_iterations,
        wall_clock_s=settings.repair_wall_clock_s,
    )
    if rca is None:
        rca = rca_mod.analyze(
            failure_analysis=failure_analysis,
            provider=provider,
            settings=settings,
            task_key=task_key,
        )
    top = hypotheses_mod.most_likely(rca)
    rca_dump = rca.model_dump()

    signatures = [failure_signature(initial_run)]
    best = _Best(
        iteration=None,
        ops=[],
        run=initial_run,
        score=score(initial_run, regression_failures=0, diff_size=0),
    )
    attempts: list[LoopAttempt] = []
    stall_streak = 0

    for iteration in range(1, budget.max_iterations + 1):
        if budget.wall_clock_exhausted():
            return _terminal_stop(
                "wall-clock budget exhausted", failure_analysis, rca, attempts, best
            )
        if no_progress(signatures):
            return _terminal_stop(
                "no progress (repeated failure signature)",
                failure_analysis,
                rca,
                attempts,
                best,
            )

        proposal = _propose(
            provider,
            settings,
            hypothesis=top,
            failure_analysis=failure_analysis,
            allowed_files=allowed_files,
            task_key=task_key,
        )
        if proposal is None or not proposal.edit_ops:
            return _terminal_stop(
                "no usable repair proposal", failure_analysis, rca, attempts, best
            )

        candidate_ops = list(best.ops) + list(proposal.edit_ops)
        ev = runner(candidate_ops)

        if ev.run.outcome == "PARTIALLY_SUPPORTED":
            return _terminal_stop(
                "sandbox unavailable", failure_analysis, rca, attempts, best
            )

        failing_before = len(best.run.failed_ids())
        failing_after = len(ev.run.failed_ids())
        s = score(ev.run, regression_failures=0, diff_size=ev.diff_size)

        if not ev.applied:
            outcome = "NO_CHANGE"
        elif ev.scope_violations:
            outcome = "WORSENED"  # revert -- best unchanged
        elif ev.run.outcome == "PASS":
            outcome = "GREEN"
        elif s < best.score:
            outcome = "IMPROVED"
        elif s > best.score:
            outcome = "WORSENED"
        else:
            outcome = "NO_CHANGE"

        attempts.append(
            LoopAttempt(
                iteration=iteration,
                outcome=outcome,
                hypothesis=top.statement,
                root_cause=rca_dump,
                proposal=proposal.model_dump(),
                edit_ops=[op.model_dump() for op in proposal.edit_ops],
                failing_before=failing_before,
                failing_after=failing_after,
                regression_failures=0,
                diff_size=ev.diff_size,
                score=s,
                run=ev.run,
            )
        )
        signatures.append(failure_signature(ev.run))

        if outcome == "GREEN":
            best = _Best(iteration, candidate_ops, ev.run, s)
            return RepairLoopResult(
                outcome="REPAIRED",
                best_iteration=iteration,
                final_ops=list(candidate_ops),
                attempts=attempts,
                safe_stop=None,
                rca=rca,
            )
        if outcome == "IMPROVED":
            best = _Best(iteration, candidate_ops, ev.run, s)

        improvement = failing_before - failing_after
        if improvement < settings.repair_min_improvement:
            stall_streak += 1
        else:
            stall_streak = 0
        if stall_streak >= 2:
            return _terminal_stop(
                "diminishing returns", failure_analysis, rca, attempts, best
            )

    return _terminal_stop(
        "iteration budget exhausted", failure_analysis, rca, attempts, best
    )


def _terminal_stop(
    reason: str,
    failure_analysis: FailureAnalysis,
    rca: RootCauseAnalysis,
    attempts: list[LoopAttempt],
    best: _Best,
) -> RepairLoopResult:
    return RepairLoopResult(
        outcome="SAFE_STOP",
        best_iteration=best.iteration,
        final_ops=list(best.ops),
        attempts=attempts,
        safe_stop=_safe_stop(
            reason, failure_analysis=failure_analysis, rca=rca, attempts=attempts
        ),
        rca=rca,
    )
