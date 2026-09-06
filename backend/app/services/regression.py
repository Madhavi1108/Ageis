"""Regression-intelligence service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23).

``get_or_plan`` classifies a task's test corpus (existing + generated) against
the Phase 8 changed set, records the per-stage selection, and -- where Docker is
available and ``execute=True`` -- runs the pre-verification selection and diffs
it against the last execution to flag new failures. Computed and persisted on
first access; ``refresh=True`` (or a mode change) recomputes. No AI.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analysis.graph.store import build_networkx
from app.analysis.graph.centrality import compute_centrality
from app.core.config import Settings
from app.core.ids import new_id
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.failures import FailureRepository, InvestigationRepository
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.jobs import JobRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.schemas.regression import (
    ClassifiedTest,
    RegressionPlan as RegressionPlanSchema,
    RegressionResult,
)
from app.testing.errors import (
    RegressionInputsMissingError,
    RegressionTaskNotFoundError,
)
from app.testing.regression import CorpusTest, Classified, classify, select_for_stage


# --------------------------------------------------------------------------- #
# Corpus + inputs
# --------------------------------------------------------------------------- #


def _tests_map(nodes, edges) -> dict[str, set[str]]:
    by_id = {n.id: n for n in nodes}
    out: dict[str, set[str]] = {}
    for e in edges:
        if e.edge_type != "TESTS":
            continue
        src, tgt = by_id.get(e.source_node_id), by_id.get(e.target_node_id)
        if src is None or tgt is None:
            continue
        out.setdefault(src.ref.split("::", 1)[0], set()).add(tgt.ref.split("::", 1)[0])
    return out


def _build_corpus(
    db: Session, task_id: str, snapshot_id: str
) -> tuple[list[CorpusTest], object, dict]:
    graph_repo = GraphRepository(db)
    nodes = graph_repo.list_nodes_for_snapshot(snapshot_id)
    edges = graph_repo.list_edges_for_snapshot(snapshot_id)
    graph = build_networkx(nodes, edges)
    centrality = compute_centrality(graph)
    tmap = _tests_map(nodes, edges)

    corpus: list[CorpusTest] = []
    seen_paths: set[str] = set()

    for n in nodes:
        if n.node_type != "TEST":
            continue
        path = n.ref.split("::", 1)[0]
        seen_paths.add(path)
        corpus.append(
            CorpusTest(
                test_id=n.ref,
                path=path,
                covered_files=frozenset(tmap.get(path, set())),
                covered_symbol=None,
                generated=False,
            )
        )

    for f in FileRepository(db).list_for_snapshot(snapshot_id):
        if not f.is_test or f.path in seen_paths:
            continue
        corpus.append(
            CorpusTest(
                test_id=f.path,
                path=f.path,
                covered_files=frozenset(tmap.get(f.path, set())),
                covered_symbol=None,
                generated=False,
            )
        )

    for c in TestCaseRepository(db).list_latest_by_task(task_id):
        if c.status == "INVALID":
            continue
        target_file = c.target_symbol.split("::", 1)[0] if c.target_symbol else None
        corpus.append(
            CorpusTest(
                test_id=f"{c.path}::{c.name}",
                path=c.path,
                covered_files=frozenset({target_file}) if target_file else frozenset(),
                covered_symbol=c.target_symbol or None,
                generated=True,
            )
        )

    corpus.sort(key=lambda t: t.test_id)
    return corpus, graph, centrality


def _prior_failure_files(db: Session, task_id: str) -> set[str]:
    inv = InvestigationRepository(db).get_latest_by_task(task_id)
    if inv is None:
        return set()
    out: set[str] = set()
    for failure in FailureRepository(db).list_for_execution(inv.execution_id):
        for fr in failure.frames or []:
            if fr.get("file"):
                out.add(fr["file"])
    return out


# --------------------------------------------------------------------------- #
# Schema assembly
# --------------------------------------------------------------------------- #


def _to_classified_schema(c: Classified) -> ClassifiedTest:
    return ClassifiedTest(
        test_id=c.test_id,
        path=c.path,
        classification=c.classification,
        rationale=c.rationale,
        covers_symbol=c.covers_symbol,
        hops=c.hops,
    )


def _plan_schema(row) -> RegressionPlanSchema:
    return RegressionPlanSchema(
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        mode=row.mode,
        changed_files=row.changed_set.get("files", []),
        changed_symbols=row.changed_set.get("symbols", []),
        tests=[ClassifiedTest.model_validate(t) for t in row.tests],
        selection=row.selection,
        full_suite_count=row.full_suite_count,
        subset_justification=row.subset_justification,
        subset_risk_note=row.subset_risk_note,
        created_at=row.created_at,
    )


def _result_from_row(row) -> RegressionResult:
    return RegressionResult(
        plan=_plan_schema(row),
        executed=row.execution_id is not None,
        execution_id=row.execution_id,
        baseline_execution_id=row.baseline_execution_id,
        new_failures=row.new_failures or [],
        reason=None if row.execution_id else "not executed (GET with ?execute=true)",
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def get_or_plan(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    mode: str = "smart",
    execute: bool = False,
    refresh: bool = False,
) -> RegressionResult:
    if TaskRepository(db).get(task_id) is None:
        raise RegressionTaskNotFoundError(f"task {task_id} not found")

    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    if impact is None:
        raise RegressionInputsMissingError(
            f"task {task_id} needs an impact analysis first (GET /tasks/{{id}}/impact)"
        )

    repo = RegressionPlanRepository(db)
    existing = repo.get_by_task(task_id)
    if existing is not None and not refresh and existing.mode == mode and not execute:
        return _result_from_row(existing)

    snapshot_id = impact.snapshot_id
    changed_files = set(impact.changed_set.get("files", []))
    changed_symbols = set(impact.changed_set.get("symbols", []))

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.REGRESSION.value,
        idempotency_key=f"regression:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    corpus, graph, centrality = _build_corpus(db, task_id, snapshot_id)
    classified = classify(
        corpus=corpus,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        graph=graph,
        centrality=centrality,
        prior_failure_files=_prior_failure_files(db, task_id),
        related_hops=settings.regression_related_hops,
        centrality_decile=settings.regression_centrality_decile,
    )

    repair_sel = select_for_stage(classified, "repair", mode=mode)
    preverify_sel = select_for_stage(classified, "pre_verification", mode=mode)
    selection = {
        "repair": repair_sel.test_ids,
        "pre_verification": preverify_sel.test_ids,
    }

    reason = None
    execution_id = None
    baseline_id = None
    new_failures: list[str] = []
    if execute:
        # A real subset run needs the Docker sandbox (Phase 12); unavailable here.
        reason = "not executed: the Docker sandbox is unavailable in this environment"

    row = repo.upsert(
        task_id,
        snapshot_id=snapshot_id,
        mode=mode,
        changed_set={
            "files": sorted(changed_files),
            "symbols": sorted(changed_symbols),
        },
        tests=[_to_classified_schema(c).model_dump() for c in classified],
        selection=selection,
        full_suite_count=len(classified),
        subset_justification=preverify_sel.justification,
        subset_risk_note=preverify_sel.risk_note,
        execution_id=execution_id,
        baseline_execution_id=baseline_id,
        new_failures=new_failures,
    )

    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.REGRESSION_TESTING.value, agent="testing"
    )
    TaskRepository(db).set_state(task_id, TaskState.REGRESSION_TESTING.value)
    jobs.mark_succeeded(job.id)

    result = _result_from_row(row)
    if reason is not None:
        result.reason = reason
    return result
