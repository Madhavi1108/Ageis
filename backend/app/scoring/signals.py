"""Deterministic signal collectors for PCS and CRS.

Every signal is read from data already persisted by Phases 8/10/12/14/15/16.
A signal with no data source in the current environment (per-changed-line
coverage, Git churn, sometimes cyclomatic delta) is returned with an
``unavailable_reason`` and the documented neutral prior from
``model_registry`` (docs/METRICS.md Section 2.5); the score functions then
lower ``overall_confidence`` by that signal's weight.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from aegis.schemas.common import Evidence

from app.core.config import Settings
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.failures import FailureRepository, InvestigationRepository
from app.repository.implementations import ImplementationRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.patches import PatchRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.reviews import ReviewFindingRepository, ReviewRepository
from app.repository.test_executions import TestExecutionRepository
from app.scoring._signal import Signal, clamp
from app.scoring.model_registry import (
    PCS_AI_SELFCONF_CAP,
    PCS_DEP_FIT_DIVISOR,
    PCS_DEP_FIT_FLOOR,
    PCS_REVIEW_CLEAN_CRITICAL_COEFF,
    PCS_REVIEW_CLEAN_DIVISOR,
    PCS_REVIEW_CLEAN_HIGH_COEFF,
    PCS_REVIEW_CLEAN_MEDIUM_COEFF,
    PCS_SECURITY_GATE,
    PCS_SIZE_FIT_DIVISOR,
    CRS_COMPLEXITY_DIVISOR,
    CRS_FILES_DIVISOR,
    CRS_LINES_DIVISOR,
    CRS_PRIOR_FAILURES_DIVISOR,
    UNAVAILABLE_PRIOR_GOOD,
    UNAVAILABLE_PRIOR_RISK,
)

_FAILING_OUTCOMES = {"FAIL", "ERROR", "TIMEOUT", "OOM"}
_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.BoolOp,
    ast.IfExp,
    ast.comprehension,
    ast.With,
    ast.AsyncWith,
)


@dataclass
class PatchScoringInputs:
    pcs_signals: list[Signal]
    crs_signals: list[Signal]
    security_gate: float
    security_gate_reason: str
    hard_gates: list[str]
    snapshot_id: str
    implementation_version: int
    patch_id: str | None
    impact_files: set[str]
    evidence_refs: list[Evidence] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _count_diff_lines(diff_text: str) -> int:
    changed = 0
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            changed += 1
    return changed


def _bundle_signal(
    bundle: dict, key: str, *, prior: float
) -> Signal:
    entry = (bundle or {}).get(key) or {}
    norm = entry.get("normalized")
    if norm is None:
        return Signal(
            name=key,
            raw=None,
            normalized=prior,
            basis="INFERENCE",
            unavailable_reason=entry.get("unavailable_reason")
            or f"{key} not available from the impact analysis",
        )
    return Signal(
        name=key,
        raw=entry.get("value"),
        normalized=float(norm),
        basis=entry.get("basis", "INFERENCE"),
    )


def _added_branch_count(edit_ops: list[dict]) -> tuple[int | None, str | None]:
    """Sum of (branch nodes in ``new`` - branch nodes in ``old``) across ops,
    floored at 0 per op. Returns (count, None) or (None, reason) when nothing
    parsed."""

    def branches(src: str | None) -> int | None:
        if not src:
            return 0
        try:
            tree = ast.parse(src)
        except SyntaxError:
            try:
                tree = ast.parse(src.strip())
            except SyntaxError:
                return None
        return sum(isinstance(n, _BRANCH_NODES) for n in ast.walk(tree))

    total = 0
    parsed_any = False
    for op in edit_ops:
        new_b = branches(op.get("new"))
        old_b = branches(op.get("old"))
        if new_b is None:
            continue
        parsed_any = True
        total += max(0, new_b - (old_b or 0))
    if not parsed_any:
        return None, "edit-op bodies are not parseable as Python"
    return total, None


# --------------------------------------------------------------------------- #
# collector
# --------------------------------------------------------------------------- #


def collect_patch_signals(
    db: Session, *, task_id: str, settings: Settings
) -> PatchScoringInputs:
    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    assert impl is not None  # the service checks this and 409s first
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    assert impact is not None  # ditto

    patch = PatchRepository(db).get_by_implementation(impl.id)
    from app.services.implementation import get_implementation as _get_impl

    impl_result = _get_impl(db, task_id)
    diff_text = impl_result.patch.diff_text
    lines_changed = _count_diff_lines(diff_text)
    edit_ops: list[dict] = list(impl.edit_ops or [])
    scope_violations: list[str] = list(impl.scope_violations or [])

    bundle: dict = impact.risk_signal_bundle or {}
    impact_files = set((impact.changed_set or {}).get("files", []))

    review_row = ReviewRepository(db).get_by_task(task_id)
    findings = ReviewFindingRepository(db).list_for_task(task_id)
    open_findings = [f for f in findings if f.status == "OPEN"]

    regression = RegressionPlanRepository(db).get_by_task(task_id)
    latest_exec = TestExecutionRepository(db).get_latest_by_task(task_id)
    repairs = RepairAttemptRepository(db).list_for_task(task_id)
    plan = EngineeringPlanRepository(db).get_latest_by_task(task_id)

    evidence_refs: list[Evidence] = []

    # ---- PCS: targeted_pass -------------------------------------------------- #
    targeted_ids: set[str] = set()
    if regression is not None:
        targeted_ids = {
            t["test_id"]
            for t in (regression.tests or [])
            if t.get("classification") == "TARGETED"
        }
    if latest_exec is None or latest_exec.outcome == "PARTIALLY_SUPPORTED":
        targeted_pass = Signal(
            "targeted_pass", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "no targeted test execution (sandbox unavailable or not run)",
        )
    else:
        results = latest_exec.results or []
        subset = (
            [r for r in results if r.get("test_id") in targeted_ids]
            if targeted_ids
            else list(results)
        )
        if not subset:
            targeted_pass = Signal(
                "targeted_pass", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
                "the latest execution ran no targeted tests",
            )
        else:
            passed = sum(1 for r in subset if r.get("outcome") == "PASS")
            ev = Evidence(
                kind="execution",
                ref=latest_exec.id,
                detail=f"{passed}/{len(subset)} targeted tests passed",
            )
            evidence_refs.append(ev)
            targeted_pass = Signal(
                "targeted_pass", float(passed), passed / len(subset), "FACT",
                evidence=[ev],
            )

    # ---- PCS: regression_pass --------------------------------------------- #
    reg_exec = (
        TestExecutionRepository(db).get(regression.execution_id)
        if regression is not None and regression.execution_id
        else None
    )
    if reg_exec is None:
        regression_pass = Signal(
            "regression_pass", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "the regression suite has not been executed (sandbox unavailable)",
        )
    else:
        r = reg_exec.results or []
        passed = sum(1 for x in r if x.get("outcome") == "PASS")
        regression_pass = Signal(
            "regression_pass",
            float(passed),
            (passed / len(r)) if r else 1.0,
            "FACT",
        )

    # ---- PCS: review_clean --------------------------------------------- #
    if review_row is None:
        review_clean = Signal(
            "review_clean", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "no code review has been run for this task",
        )
    else:
        crit = sum(1 for f in open_findings if f.severity == "CRITICAL")
        high = sum(1 for f in open_findings if f.severity == "HIGH")
        med = sum(1 for f in open_findings if f.severity == "MEDIUM")
        weighted = (
            PCS_REVIEW_CLEAN_CRITICAL_COEFF * crit
            + PCS_REVIEW_CLEAN_HIGH_COEFF * high
            + PCS_REVIEW_CLEAN_MEDIUM_COEFF * med
        )
        review_clean = Signal(
            "review_clean",
            weighted,
            1.0 - min(1.0, weighted / PCS_REVIEW_CLEAN_DIVISOR),
            "FACT",
        )

    # ---- PCS: coverage (no instrumentation) --------------------------- #
    coverage = Signal(
        "coverage", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
        "no executed per-line coverage is collected",
    )

    # ---- PCS: scope_clean -------------------------------------------- #
    if scope_violations:
        ev = [
            Evidence(kind="file", ref=p, detail="changed outside the plan scope")
            for p in scope_violations
        ]
        evidence_refs.extend(ev)
        scope_clean = Signal("scope_clean", 0.0, 0.0, "FACT", evidence=ev)
    else:
        scope_clean = Signal("scope_clean", 1.0, 1.0, "FACT")

    # ---- PCS: size_fit / CRS: lines_changed ------------------------- #
    size_fit = Signal(
        "size_fit",
        float(lines_changed),
        clamp(1.0 - lines_changed / PCS_SIZE_FIT_DIVISOR),
        "FACT",
    )
    lines_changed_sig = Signal(
        "lines_changed",
        float(lines_changed),
        clamp(lines_changed / CRS_LINES_DIVISOR),
        "FACT",
    )

    # ---- PCS: dep_fit -------------------------------------------- #
    direct_callers = sum(
        1
        for entry in (impact.callers or [])
        for c in entry.get("callers", [])
        if c.get("hop") == 1
    )
    dep_fit = Signal(
        "dep_fit",
        float(direct_callers),
        clamp(
            1.0 - direct_callers / PCS_DEP_FIT_DIVISOR, PCS_DEP_FIT_FLOOR, 1.0
        ),
        "FACT",
    )

    # ---- PCS: history_stable (Git churn is Phase 19) ------------- #
    history_stable = Signal(
        "history_stable", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
        "no Git history available (Phase 19)",
    )

    # ---- PCS: repair_fit ------------------------------------- #
    max_it = max(1, settings.repair_max_iterations)
    repair_fit = Signal(
        "repair_fit",
        float(len(repairs)),
        clamp(1.0 - len(repairs) / max_it),
        "FACT",
    )

    # ---- PCS: ai_selfconf ------------------------------------- #
    if plan is None:
        ai_selfconf = Signal(
            "ai_selfconf", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "no engineering plan to read a provider confidence from",
        )
    else:
        v = float((plan.confidence or {}).get("value", 0.5))
        ai_selfconf = Signal(
            "ai_selfconf", v, min(v, PCS_AI_SELFCONF_CAP), "INFERENCE"
        )

    # ---- CRS: from the impact risk_signal_bundle -------------- #
    files_changed = _bundle_signal(bundle, "files_changed", prior=UNAVAILABLE_PRIOR_RISK)
    if not files_changed.available and patch is not None:
        files_changed = Signal(
            "files_changed",
            float(len(patch.touched_paths or [])),
            clamp(len(patch.touched_paths or []) / CRS_FILES_DIVISOR),
            "FACT",
        )
    dependency_impact = _bundle_signal(
        bundle, "dependency_impact", prior=UNAVAILABLE_PRIOR_RISK
    )
    public_api_touched = _bundle_signal(
        bundle, "public_api_touched", prior=UNAVAILABLE_PRIOR_RISK
    )
    architectural_centrality = _bundle_signal(
        bundle, "architectural_centrality", prior=UNAVAILABLE_PRIOR_RISK
    )
    security_sensitivity = _bundle_signal(
        bundle, "security_sensitivity", prior=UNAVAILABLE_PRIOR_RISK
    )

    # ---- CRS: inverse_coverage / historical_churn (no source) ---- #
    inverse_coverage = Signal(
        "inverse_coverage", None, UNAVAILABLE_PRIOR_RISK, "INFERENCE",
        "no executed per-line coverage is collected",
    )
    historical_churn = Signal(
        "historical_churn", None, UNAVAILABLE_PRIOR_RISK, "INFERENCE",
        "no Git history available (Phase 19)",
    )

    # ---- CRS: prior_failures ------------------------------------ #
    inv = InvestigationRepository(db).get_latest_by_task(task_id)
    prior_files: set[str] = set()
    if inv is not None:
        for failure in FailureRepository(db).list_for_execution(inv.execution_id):
            for fr in failure.frames or []:
                if fr.get("file"):
                    prior_files.add(fr["file"])
    new_failures = list(regression.new_failures or []) if regression is not None else []
    failures_in_area = len(prior_files) + len(new_failures)
    prior_failures = Signal(
        "prior_failures",
        float(failures_in_area),
        clamp(failures_in_area / CRS_PRIOR_FAILURES_DIVISOR),
        "INFERENCE",
    )

    # ---- CRS: complexity_delta -------------------------------- #
    added, reason = _added_branch_count(edit_ops)
    if added is None:
        complexity_delta = Signal(
            "complexity_delta", None, UNAVAILABLE_PRIOR_RISK, "INFERENCE", reason
        )
    else:
        complexity_delta = Signal(
            "complexity_delta",
            float(added),
            clamp(added / CRS_COMPLEXITY_DIVISOR),
            "INFERENCE",
        )

    # ---- security_gate (PCS multiplier) ---------------------- #
    open_sec = [
        f for f in open_findings if f.category == "SECURITY"
    ]
    if any(f.severity in ("HIGH", "CRITICAL") for f in open_sec):
        security_gate, gate_reason = PCS_SECURITY_GATE["high_unresolved"], "high_unresolved"
    elif any(f.severity == "MEDIUM" for f in open_sec):
        security_gate, gate_reason = PCS_SECURITY_GATE["medium_open"], "medium_open"
    else:
        security_gate, gate_reason = PCS_SECURITY_GATE["clean"], "clean"

    # ---- hard gates (PCS override -> cap 40, BLOCKED) -------- #
    hard_gates: list[str] = []
    if any(f.severity == "CRITICAL" for f in open_findings):
        hard_gates.append("unresolved_critical_review_finding")
    if scope_violations:
        hard_gates.append("unresolved_scope_violation")
    regression_failing = bool(new_failures) or (
        reg_exec is not None
        and any(x.get("outcome") in _FAILING_OUTCOMES for x in (reg_exec.results or []))
    )
    if regression_failing:
        hard_gates.append("failing_regression_test")

    pcs_signals = [
        targeted_pass,
        regression_pass,
        review_clean,
        coverage,
        scope_clean,
        size_fit,
        dep_fit,
        history_stable,
        repair_fit,
        ai_selfconf,
    ]
    crs_signals = [
        files_changed,
        lines_changed_sig,
        dependency_impact,
        public_api_touched,
        inverse_coverage,
        historical_churn,
        prior_failures,
        architectural_centrality,
        complexity_delta,
        security_sensitivity,
    ]

    return PatchScoringInputs(
        pcs_signals=pcs_signals,
        crs_signals=crs_signals,
        security_gate=security_gate,
        security_gate_reason=gate_reason,
        hard_gates=hard_gates,
        snapshot_id=impl.snapshot_id,
        implementation_version=impl.version,
        patch_id=patch.id if patch is not None else None,
        impact_files=impact_files,
        evidence_refs=evidence_refs,
    )
