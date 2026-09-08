"""Headless benchmark runner: drive the real ``app/`` pipeline over one task and
capture its raw signals (docs/EVAL_HARNESS.md Section 5).

Deterministic with ``MockProvider`` + ``sandbox_mode="fake"``. The canned model
answers are synthesized from the task's compact ``mock`` block so the YAML stays
readable.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.models.base import Base
from app.models.task import TaskState
from app.orchestration import orchestrator
from app.repository.code_mappings import CodeMappingRepository
from app.repository.implementations import ImplementationRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.repositories import RepositoryRepository
from app.repository.reviews import ReviewRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.repository.verifications import VerificationRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import tasks as tasks_service
from app.services import verification as verification_service

from benchmarks import dataset as dataset_mod
from benchmarks.agents.base import ReferenceAgent
from benchmarks.schema import (
    AICall,
    BenchmarkResult,
    BenchmarkTask,
    EditSpec,
    FileSpec,
    TaskRun,
    TestEval,
)

_CONF = {"value": 0.85, "basis": "FACT"}


# --------------------------------------------------------------------------- #
# Counting MockProvider (metric #13 cost inputs)
# --------------------------------------------------------------------------- #


def _approx_tokens(obj: object) -> int:
    try:
        text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    except TypeError:
        text = str(obj)
    return max(1, len(text) // 4)


class CountingMockProvider(MockProvider):
    """A MockProvider that records an approximate token count per call so the
    runner can price it against ``pricing-table v1.0.0`` (metric #13)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[AICall] = []

    def complete(self, *, template, variables, schema, tier="frontier", **kw):  # type: ignore[override]
        result = super().complete(
            template=template, variables=variables, schema=schema, tier=tier, **kw
        )
        self.calls.append(
            AICall(
                template=template,
                tier=tier,
                input_tokens=_approx_tokens(variables),
                output_tokens=_approx_tokens(result.model_dump()),
            )
        )
        return result


# --------------------------------------------------------------------------- #
# Canned-answer synthesis
# --------------------------------------------------------------------------- #


def _edit_op(spec: EditSpec, step_id: str) -> dict:
    if spec.op == "create":
        return {
            "path": spec.file,
            "op": "create",
            "anchor": None,
            "new": spec.replace or "",
            "plan_step_id": step_id,
            "rationale": "benchmark canned create",
            "evidence": [],
        }
    new = (spec.prepend or "") + (spec.replace or "")
    return {
        "path": spec.file,
        "op": spec.op,
        "anchor": spec.find,
        "old": spec.find,
        "new": new,
        "plan_step_id": step_id,
        "rationale": "benchmark canned edit",
        "evidence": [],
    }


def _create_op(fs: FileSpec, step_id: str) -> dict:
    return {
        "path": fs.path,
        "op": "create",
        "anchor": None,
        "new": fs.content,
        "plan_step_id": step_id,
        "rationale": "benchmark canned new file",
        "evidence": [],
    }


def _has_primary(task: BenchmarkTask) -> bool:
    return bool(task.mock.fix or task.mock.incomplete_fix)


def _has_secondary(task: BenchmarkTask) -> bool:
    return bool(task.mock.create or task.mock.extra_edits)


def _secondary_step_id(task: BenchmarkTask) -> str:
    return "s2" if (_has_primary(task) and _has_secondary(task)) else "s1"


def _plan_dict(task: BenchmarkTask) -> dict:
    steps = [
        {
            "id": "s1",
            "description": "apply the fix" if _has_primary(task) else "create and wire in the new module",
            "test_intent": "the failing behaviour now passes",
            "evidence_refs": list(task.symbols_to_modify),
        }
    ]
    if _has_primary(task) and _has_secondary(task):
        steps.append(
            {
                "id": "s2",
                "description": "wire in / create supporting code",
                "test_intent": "the new behaviour is exercised",
                "evidence_refs": [],
            }
        )
    return {
        "problem_interpretation": task.problem_statement.strip()[:280] or task.id,
        "assumptions": ["inputs are within documented ranges"],
        "files_to_inspect": list(task.effective_files_to_modify),
        "files_to_modify": list(task.effective_files_to_modify),
        "symbols_to_modify": list(task.symbols_to_modify),
        "dependencies": [],
        "steps": steps,
        "test_strategy": {"approach": "targeted test on the changed behaviour"},
        "expected_behavior": "the fail_to_pass tests pass, pass_to_pass stay green",
        "regression_risks": ["callers of the changed symbol"],
        "rollback_strategy": "revert the snapshot",
        "source": "AI",
        "confidence": _CONF,
        "evidence": [],
    }


def _impl_dict(task: BenchmarkTask) -> dict:
    ops: list[dict] = []
    m = task.mock
    sec = _secondary_step_id(task)
    first = m.incomplete_fix or m.fix
    if first is not None:
        ops.append(_edit_op(first, "s1"))
    for fs in m.create:
        ops.append(_create_op(fs, sec))
    for e in m.extra_edits:
        ops.append(_edit_op(e, sec))
    if m.defect is not None:
        ops.append(_edit_op(m.defect, "s1"))
    if not ops:
        raise ValueError(f"task {task.id}: mock produces no implementation edit-ops")
    return {"edit_ops": ops}


def _tests_dict(task: BenchmarkTask) -> dict:
    target = task.symbols_to_modify[0] if task.symbols_to_modify else (
        (task.gold_files[0] if task.gold_files else "mod.py") + "::target"
    )
    cases = [
        {
            "name": fs.path.replace("/", "_").replace(".py", ""),
            "path": fs.path,
            "target_symbol": target,
            "kind": "BOUNDARY",
            "rationale": "benchmark generated test",
            "code": fs.content,
            "evidence": [],
        }
        for fs in task.mock.generated_tests
    ]
    if not cases:
        # a minimal always-valid smoke test so the generate/execute stages run
        mod = (task.gold_files[0] if task.gold_files else "mod.py")[:-3]
        cases = [
            {
                "name": "test_smoke_import",
                "path": "test_benchmark_smoke.py",
                "target_symbol": target,
                "kind": "BOUNDARY",
                "rationale": "smoke",
                "code": f"import {mod}\n\n\ndef test_smoke_import():\n    assert {mod} is not None\n",
                "evidence": [],
            }
        ]
    return {"test_cases": cases}


def _rca_dict(task: BenchmarkTask) -> dict:
    sym = task.symbols_to_modify[0] if task.symbols_to_modify else task.id
    return {
        "hypotheses": [
            {
                "statement": f"{sym} does not yet implement the required behaviour",
                "label": "HYPOTHESIS",
                "evidence": [],
                "rank": 0,
            }
        ],
        "most_likely_index": 0,
        "open_questions": [],
        "confidence": {"value": 0.7, "basis": "INFERENCE"},
        "evidence": [],
    }


def _repair_dict(task: BenchmarkTask) -> dict | None:
    m = task.mock
    spec = m.dead_repair or (m.fix if m.incomplete_fix else None)
    if spec is None:
        return None
    return {
        "target_hypothesis": "apply the correct fix",
        "edit_ops": [_edit_op(spec, "repair")],
        "expected_effect": "targeted tests pass",
        "risk_notes": [],
        "confidence": _CONF if not m.dead_repair else {"value": 0.2, "basis": "UNKNOWN"},
        "evidence": [],
    }


def _register(provider: MockProvider, task: BenchmarkTask, task_id: str) -> None:
    provider.register("planning", task_id, _plan_dict(task))
    provider.register("implementation", task_id, _impl_dict(task))
    provider.register("test_synthesis", task_id, _tests_dict(task))
    provider.register("rca", task_id, _rca_dict(task))
    rp = _repair_dict(task)
    if rp is not None:
        provider.register("repair", task_id, rp)


# --------------------------------------------------------------------------- #
# fail_to_pass / pass_to_pass evaluation
# --------------------------------------------------------------------------- #

_NON_COUNTING_EXEC = {"PARTIALLY_SUPPORTED", "INFRA_ERROR"}


def _reconstruct_final_workspace(db, settings: Settings, task_id: str, dest: Path) -> Path | None:
    from app.implementation.editor import EditorError, apply_edit_op
    from app.implementation.workspace_rw import clone_rw
    from app.ingestion.workspace import workspace_dir
    from app.schemas.implementation import EditOp

    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None:
        return None
    source = workspace_dir(impl.snapshot_id, settings)
    ws = clone_rw(impl.snapshot_id, source)
    for op in impl.edit_ops:
        try:
            apply_edit_op(ws, EditOp.model_validate(op))
        except EditorError:
            pass
    # copy the reconstructed tree to a stable dir we control the lifetime of
    import shutil

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ws.root, dest)
    ws.cleanup()
    return dest


def _pytest_ids(root: Path, ids: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for tid in ids:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", tid],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out[tid] = proc.returncode == 0
    return out


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def _settings(repo_parent: Path, artifacts: Path) -> Settings:
    return Settings(
        ingestion_local_roots=[str(repo_parent)],
        artifacts_root=str(artifacts),
        sandbox_mode="fake",
        memory_enabled=False,
        orchestrator_open_pr=False,
        _env_file=None,
    )


def run_task(
    task: BenchmarkTask,
    *,
    workdir: Path,
    reference_agents: list[ReferenceAgent] | None = None,
) -> TaskRun:
    run = TaskRun(
        task_id=task.id,
        dataset=task.dataset,
        task_type=task.task_type,
        gold_files=list(task.gold_files),
        is_seeded_regression=task.seeded_regression,
        seeded_defect_kind=task.seeded_defect_kind,
        verification_label=task.verification_label,
    )
    workdir = Path(workdir)
    if workdir.exists():
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    repo_root = workdir / "repo"
    dataset_mod.materialize(task.dataset, task, repo_root)
    settings = _settings(repo_root.parent, workdir / "artifacts")

    engine = create_engine(f"sqlite:///{workdir / 'bench.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        repo = RepositoryRepository(db).get_or_create(
            source_type="LOCAL", url_or_path=str(repo_root), name=f"bench-{task.id}"
        )
        ingested = ingest_repository(
            db, repository=repo, request=IngestRequest(), settings=settings
        )
        analyze_snapshot(
            db, snapshot=SnapshotRepository(db).get(ingested.snapshot_id), settings=settings
        )
        payload = TaskCreate(
            repository_id=repo.id,
            text=task.problem_statement,
            allowed_paths=task.allowed_paths,
        )
        task_id = tasks_service.create_task(db, settings=settings, payload=payload).task.id

        provider = CountingMockProvider()
        _register(provider, task, task_id)

        t0 = time.monotonic()
        result_task = orchestrator.run_task(
            db, settings=settings, task_id=task_id, provider=provider
        )
        run.wall_clock_ms = int((time.monotonic() - t0) * 1000)
        run.ai_calls = list(provider.calls)

        # the pipeline's own verdict + signals, before any benchmark-side sign-off
        _capture_signals(db, settings, task, task_id, run)
        run.pipeline_verdict = run.verification_verdict

        # ground truth: reconstruct the final workspace and run the task's
        # fail_to_pass / pass_to_pass sets against it
        final = _reconstruct_final_workspace(db, settings, task_id, workdir / "final")
        if final is not None:
            run.test_eval = TestEval(
                fail_to_pass=_pytest_ids(final, task.fail_to_pass),
                pass_to_pass=_pytest_ids(final, task.pass_to_pass),
            )

        # A human-approval-gated task is signed off here only when ground truth
        # agrees the fix actually landed -- without Docker the pipeline cannot
        # confirm targeted tests itself, so blind approval would manufacture
        # false-completes (metric #10). See docs/EVAL_HARNESS.md Section 5.
        if (
            result_task.state == TaskState.AWAITING_APPROVAL.value
            and run.test_eval.verified_fixed
        ):
            verification_service.resolve_decision(
                db,
                settings=settings,
                task_id=task_id,
                decision="APPROVE",
                reason="benchmark sign-off: ground-truth fail_to_pass/pass_to_pass green",
                actor="benchmark@aegis",
            )
            result_task = TaskRepository(db).get(task_id)
            _capture_signals(db, settings, task, task_id, run)  # refresh final verdict

        run.terminal_state = result_task.state

        if final is not None:
            if task.seeded_regression:
                run.regression_flagged = _regression_flagged(db, task_id, task, run)
            for agent in reference_agents or []:
                run.reference_outcomes[agent.name] = _run_reference_agent(
                    agent, task, workdir
                )
    except Exception as exc:  # noqa: BLE001 -- one bad task never sinks the run
        run.error = f"{type(exc).__name__}: {exc}"
    finally:
        db.close()
        engine.dispose()
    return run


def _capture_signals(db, settings, task: BenchmarkTask, task_id: str, run: TaskRun) -> None:
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    if mapping is not None:
        run.predicted_files = [c["path"] for c in (mapping.candidates or [])]

    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    run.patch_generated = impl is not None
    if impl is not None:
        run.scope_violation = bool(impl.scope_violations)
        run.changed_files = sorted({op["path"] for op in impl.edit_ops})

    verification = VerificationRepository(db).get_by_task(task_id)
    if verification is not None:
        run.verification_verdict = verification.verdict
        run.replay_fidelity = verification.replay_fidelity
        pa = verification.plan_alignment or {}
        run.plan_steps_total = int(pa.get("steps_total", 0))
        run.plan_steps_implemented = int(pa.get("steps_implemented", 0))
        run.unplanned_files = list(pa.get("unplanned_files", []) or [])
        if pa.get("files_touched"):
            run.changed_files = list(pa["files_touched"])

    from app.repository.scoring import RiskAssessmentRepository

    risk = RiskAssessmentRepository(db).get_by_task(task_id)
    if risk is not None:
        run.pcs_value = risk.pcs_value
        run.pcs_classification = risk.pcs_classification
        run.crs_value = risk.crs_value
        run.crs_classification = risk.crs_classification

    cases = TestCaseRepository(db).list_latest_by_task(task_id)
    run.tests_generated = len(cases)
    run.tests_valid = sum(1 for c in cases if c.status != "INVALID")

    execution = TestExecutionRepository(db).get_latest_by_task(task_id)
    if execution is not None:
        run.real_execution = execution.outcome not in _NON_COUNTING_EXEC
        run.test_results = [r.get("outcome", "") for r in (execution.results or [])]

    attempts = RepairAttemptRepository(db).list_for_task(task_id)
    if attempts:
        run.entered_repair = True
        summary = next((a.run_summary for a in attempts if a.run_summary), None) or {}
        run.repair_outcome = summary.get("outcome")
        run.repair_iterations = sum(1 for a in attempts if a.iteration > 0) or len(attempts)

    review = ReviewRepository(db).get_by_task(task_id)
    if review is not None:
        from app.repository.reviews import ReviewFindingRepository

        findings = ReviewFindingRepository(db).list_for_task(task_id)
        run.review_findings = [f"{f.severity}:{f.category}" for f in findings]
        if task.seeded_defect_kind:
            run.review_flagged_defect = _defect_flagged(task.seeded_defect_kind, findings)


def _defect_flagged(kind: str, findings) -> bool:
    kind = kind.lower()
    for f in findings:
        blob = " ".join(
            str(getattr(f, attr, "") or "")
            for attr in ("severity", "category", "description", "recommendation")
        ).lower()
        if kind in ("hardcoded_secret", "secret") and "secret" in blob:
            return True
        if kind in ("bare_except", "except") and ("except" in blob or "exception" in blob):
            return True
        if kind == "eval_exec" and ("eval" in blob or "exec" in blob):
            return True
        if kind == "subprocess_shell" and ("shell" in blob or "subprocess" in blob):
            return True
        if kind in blob:
            return True
    return False


def _regression_flagged(db, task_id, task: BenchmarkTask, run: TaskRun) -> bool:
    if not run.test_eval.broke_a_pass_to_pass:
        return False
    plan = RegressionPlanRepository(db).get_by_task(task_id)
    broken = [tid for tid, ok in run.test_eval.pass_to_pass.items() if not ok]
    selected = _regression_selected_ids(plan)
    if selected is None:
        return True  # no selection detail -> the pass_to_pass suite itself is the net
    return any(any(b.split("::")[0] in s or s in b for s in selected) for b in broken)


def _regression_selected_ids(plan) -> list[str] | None:
    if plan is None:
        return None
    for attr in ("selected", "selected_tests", "test_ids", "targeted_set"):
        val = getattr(plan, attr, None)
        if val:
            return list(val)
    data = getattr(plan, "plan", None) or getattr(plan, "selection", None)
    if isinstance(data, dict):
        for key in ("selected", "test_ids", "pre_verification", "smart"):
            if data.get(key):
                return list(data[key])
    return None


def _run_reference_agent(agent: ReferenceAgent, task: BenchmarkTask, workdir: Path) -> bool:
    try:
        ws = workdir / f"ref-{agent.name}"
        dataset_mod.materialize(task.dataset, task, ws)
        applied = agent.solve(task, ws)
        if not applied:
            return False
        ftp = _pytest_ids(ws, task.fail_to_pass)
        ptp = _pytest_ids(ws, task.pass_to_pass)
        return bool(ftp) and all(ftp.values()) and all(ptp.values())
    except Exception:  # noqa: BLE001
        return False


def run_dataset(
    dataset_name: str,
    *,
    workdir: Path,
    reference_agents: list[ReferenceAgent] | None = None,
) -> BenchmarkResult:
    tasks = dataset_mod.load_dataset(dataset_name)
    result = BenchmarkResult(
        dataset=dataset_name,
        dataset_digest=dataset_mod.dataset_digest(dataset_name),
        aegis_git_head=_git_head(),
    )
    for task in tasks:
        result.runs.append(
            run_task(
                task,
                workdir=Path(workdir) / task.id,
                reference_agents=reference_agents,
            )
        )
    return result


def _git_head() -> str | None:
    try:
        from benchmarks import REPO_ROOT

        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None
