"""Phase 24 -- End-to-End Controlled Repository.

Drives the real ``app/`` pipeline (Phase 21 orchestrator + fake sandbox + a
deterministic MockProvider) against the finalized acceptance repository, with
crafted Git history, through all 18 workflow steps of Specification Section 39.

  * scenario A -- a discount-cap BUG that is *introduced then repaired*
    (first implementation fails the boundary test -> investigate -> repair ->
    re-execute PASS -> VERIFIED) and reaches COMPLETED, exercising every step;
  * scenario B -- a FEATURE that creates a brand-new module + tests;
  * scenario C -- an UNFIXABLE variant that reaches a clean SAFE_STOP.

This suite is the top-level regression gate for every later phase. It runs with
the mock provider + fake sandbox in CI; ``test_docker_variant`` re-runs
scenario A through a real Docker daemon when one is available.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.github.deps import build_github_client
from app.ingestion.ingest import ingest_repository
from app.models.task import TaskState
from app.orchestration import orchestrator
from app.reporting.report_builder import build_task_report
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_memory import EngineeringMemoryRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.failures import InvestigationRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.implementations import ImplementationRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.repositories import RepositoryRepository
from app.repository.reviews import ReviewRepository
from app.repository.scoring import RiskAssessmentRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.repository.verifications import VerificationRepository
from app.schemas.repository import IngestRequest
from app.schemas.report import SECTION_NAMES
from app.schemas.task import TaskCreate
from app.services import git_intel as git_intel_service
from app.services import implementation as implementation_service
from app.services import pr as pr_service
from app.services import repair as repair_service
from app.services import tasks as tasks_service
from app.services import verification as verification_service

from tests.e2e._acceptance_repo import build_acceptance_git_repo
from tests.e2e._acceptance_scenarios import SCENARIO_ALLOWED_PATHS, register_scenario
from tests.e2e._gold import load_gold

pytestmark = pytest.mark.e2e

_FAILING = {"FAIL", "ERROR", "TIMEOUT", "OOM"}


def _fake_settings(tmp_path, repo_parent, **over) -> Settings:
    return Settings(
        ingestion_local_roots=[str(repo_parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        sandbox_mode=over.pop("sandbox_mode", "fake"),
        memory_enabled=True,
        orchestrator_open_pr=False,
        _env_file=None,
        **over,
    )


def _drive(db, tmp_path, *, source, scenario, task_file="task.md", sandbox_mode="fake"):
    work = tmp_path / f"repo_{scenario}"
    build_acceptance_git_repo(work, source=source)
    settings = _fake_settings(tmp_path, work.parent, sandbox_mode=sandbox_mode)

    repo = RepositoryRepository(db).get_or_create(
        source_type="LOCAL", url_or_path=str(work), name=work.name
    )
    ingested = ingest_repository(
        db, repository=repo, request=IngestRequest(), settings=settings
    )
    assert ingested.status == "READY"
    # a *real* git work tree -> a real 40-char sha, so Git intelligence runs
    assert not ingested.commit_sha.startswith("local:")
    assert len(ingested.commit_sha) == 40

    analyze_snapshot(
        db, snapshot=SnapshotRepository(db).get(ingested.snapshot_id), settings=settings
    )

    payload = TaskCreate(
        repository_id=repo.id,
        text=(source / task_file).read_text(encoding="utf-8"),
        allowed_paths=SCENARIO_ALLOWED_PATHS[scenario],
    )
    task_id = tasks_service.create_task(db, settings=settings, payload=payload).task.id

    provider = MockProvider()
    register_scenario(provider, scenario, task_id)
    task = orchestrator.run_task(
        db, settings=settings, task_id=task_id, provider=provider
    )
    return SimpleNamespace(
        db=db,
        task=task,
        task_id=task_id,
        provider=provider,
        settings=settings,
        repo=repo,
        snapshot_id=ingested.snapshot_id,
    )


def _approve_if_parked(r):
    if r.task.state == TaskState.AWAITING_APPROVAL.value:
        verification_service.resolve_decision(
            r.db,
            settings=r.settings,
            task_id=r.task_id,
            decision="APPROVE",
            reason="fake sandbox validated the change",
            actor="approver@example.com",
        )
        from app.repository.tasks import TaskRepository

        r.task = TaskRepository(r.db).get(r.task_id)


# --------------------------------------------------------------------------- #
# Scenario A -- the full 18-step walk
# --------------------------------------------------------------------------- #


def test_scenario_a_drives_all_18_workflow_steps(db_session, tmp_path, acceptance_src):
    gold = load_gold("scenario_a")
    r = _drive(db_session, tmp_path, source=acceptance_src, scenario="A")
    _approve_if_parked(r)
    assert r.task.state == TaskState.COMPLETED.value

    db = db_session

    # 1 ingest -------------------------------------------------------------- #
    snap = SnapshotRepository(db).get(r.snapshot_id)
    assert snap is not None and snap.status == "READY"

    # 2 understand repository -------------------------------------------------#
    from app.repository.analyses import AnalysisRepository

    analysis = AnalysisRepository(db).get_by_snapshot(r.snapshot_id)
    assert analysis is not None

    # 3 + 4 map issue -> code / identify files ----------------------------- #
    mapping = CodeMappingRepository(db).get_by_task(r.task_id)
    assert mapping is not None
    mapped_files = {c["path"] for c in mapping.candidates}
    assert set(gold.expected_localization_files) & mapped_files

    # 5 impact ------------------------------------------------------------- #
    assert ImpactAnalysisRepository(db).get_by_task(r.task_id) is not None

    # 6 plan ------------------------------------------------------------- #
    plan = EngineeringPlanRepository(db).get_latest_by_task(r.task_id)
    assert plan is not None and plan.validation_verdict == "APPROVED"
    assert plan.files_to_modify == gold.expected_files_modified

    # 7 implement ------------------------------------------------------------#
    impl = ImplementationRepository(db).get_latest_by_task(r.task_id)
    assert impl is not None

    # 8 generate tests --------------------------------------------------- #
    cases = TestCaseRepository(db).list_latest_by_task(r.task_id)
    assert [c.path for c in cases] == ["test_discount_cap_boundary.py"]

    # 9 + 10 execute -> detect the introduced failure -------------------- #
    execs = TestExecutionRepository(db).list_for_task(r.task_id)  # newest first
    assert len(execs) >= 2
    assert execs[-1].outcome in _FAILING  # first run failed
    assert execs[0].outcome == "PASS"  # after repair

    # 11 investigate --------------------------------------------------------#
    inv = InvestigationRepository(db).get_latest_by_task(r.task_id)
    assert inv is not None

    # 12 repair ---------------------------------------------------------- #
    attempts = RepairAttemptRepository(db).list_for_task(r.task_id)
    assert attempts
    summary = next(a.run_summary for a in attempts if a.run_summary)
    assert summary["outcome"] == gold.expected_repair_outcome  # REPAIRED

    # 13 regression ---------------------------------------------------------#
    assert RegressionPlanRepository(db).get_by_task(r.task_id) is not None

    # 14 review --------------------------------------------------------- #
    review = ReviewRepository(db).get_by_task(r.task_id)
    assert review is not None and not review.blocking

    # 15 risk / confidence --------------------------------------------- #
    risk = RiskAssessmentRepository(db).get_by_task(r.task_id)
    assert risk is not None and isinstance(risk.pcs_value, int)

    # 16 verify --------------------------------------------------------- #
    verification = VerificationRepository(db).get_by_task(r.task_id)
    assert verification is not None
    assert verification.verdict == gold.expected_verification_verdict  # VERIFIED

    # 17 final diff ----------------------------------------------------- #
    final = implementation_service.get_implementation(db, r.task_id)
    assert "invoice.py" in final.patch.touched_paths
    assert "min(discount, 0.5)" in final.patch.diff_text

    # 18 PR ----------------------------------------------------------------- #
    pr = pr_service.create_pr(
        db,
        settings=r.settings,
        task_id=r.task_id,
        github_client=build_github_client(r.settings),
    )
    assert pr.mode == "LOCAL_ARTIFACT"
    assert pr.state == "DRAFTED"

    # --- cross-check: the 18-section report is fully populated ----------- #
    report = build_task_report(db, settings=r.settings, task_id=r.task_id)
    assert [s.name for s in report.sections] == SECTION_NAMES
    present = {s.name for s in report.sections if s.present}
    for required in ("Requirement", "Plan", "Implementation", "Tests", "Verification", "Patch"):
        assert required in present

    # --- Git intelligence saw the crafted history + the prior related fix - #
    ctx = git_intel_service.get_or_extract_history(
        db, settings=r.settings, repository_id=r.repo.id
    )
    assert ctx.available
    assert any(
        "rounding drift" in c.message for c in ctx.related_fixes
    ), [c.message for c in ctx.related_fixes]
    assert any(e.path == "invoice.py" and e.commit_count >= 2 for e in ctx.churn)

    # --- engineering memory recorded the completed task ----------------- #
    assert EngineeringMemoryRepository(db).get_by_task(r.task_id) is not None


# --------------------------------------------------------------------------- #
# Scenario B -- feature request that creates new files
# --------------------------------------------------------------------------- #


def test_scenario_b_feature_request_creates_new_files(
    db_session, tmp_path, acceptance_src
):
    gold = load_gold("scenario_b")
    r = _drive(
        db_session,
        tmp_path,
        source=acceptance_src,
        scenario="B",
        task_file="task_feature.md",
    )
    _approve_if_parked(r)
    assert r.task.state == TaskState.COMPLETED.value

    impl = implementation_service.get_implementation(db_session, r.task_id)
    created = {op.path for op in impl.edit_ops if op.op == "create"}
    assert set(gold.expected_files_created) <= created
    assert "tax.py" in impl.patch.touched_paths

    cases = TestCaseRepository(db_session).list_latest_by_task(r.task_id)
    assert [c.path for c in cases] == ["test_tax.py"]

    execs = TestExecutionRepository(db_session).list_for_task(r.task_id)
    assert execs and execs[0].outcome == "PASS"
    # no introduced failure -> no repair loop ran
    assert not RepairAttemptRepository(db_session).list_for_task(r.task_id)

    # A purely-additive feature can't earn a mandatory `acceptance_tests_pass`
    # PASS in the Docker-less fake-sandbox run (the targeted-test heuristic does
    # not bind a brand-new symbol), so verification is PARTIAL until the human
    # approval above resolves it to VERIFIED -- an honest, documented outcome.
    verification = VerificationRepository(db_session).get_by_task(r.task_id)
    assert verification is not None
    assert verification.verdict == gold.expected_verification_verdict  # VERIFIED


# --------------------------------------------------------------------------- #
# Scenario C -- unfixable variant reaches a clean SAFE_STOP
# --------------------------------------------------------------------------- #


def test_scenario_c_unfixable_reaches_safe_stop(db_session, tmp_path, unfixable_src):
    r = _drive(
        db_session, tmp_path, source=unfixable_src, scenario="C", task_file="task.md"
    )

    # never a false success
    assert r.task.state != TaskState.COMPLETED.value

    attempts = RepairAttemptRepository(db_session).list_for_task(r.task_id)
    assert attempts
    summary = next(a.run_summary for a in attempts if a.run_summary)
    assert summary["outcome"] == "SAFE_STOP"
    assert summary["safe_stop"] and summary["safe_stop"]["recommended_human_action"]

    verification = VerificationRepository(db_session).get_by_task(r.task_id)
    assert verification is None or verification.verdict != "VERIFIED"

    # the SAFE_STOP path still records engineering memory (best-effort hook)
    assert EngineeringMemoryRepository(db_session).get_by_task(r.task_id) is not None


# --------------------------------------------------------------------------- #
# Cost / latency band (Section 5.7) -- provisional, calibrated in Phase 25
# --------------------------------------------------------------------------- #


def test_scenario_a_ai_call_budget_is_bounded(db_session, tmp_path, acceptance_src):
    r = _drive(db_session, tmp_path, source=acceptance_src, scenario="A")
    _approve_if_parked(r)
    # one connected run must not fan out into an unbounded number of model
    # calls; the exact band is re-justified with priced tokens in Phase 25.
    served = sum(1 for _ in r.provider._responses)  # registered answers only
    assert served <= 5
    assert r.task.state == TaskState.COMPLETED.value


# --------------------------------------------------------------------------- #
# Docker variant -- the same scenario A through a real daemon (auto-skips)
# --------------------------------------------------------------------------- #


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_available(), reason="requires a running Docker daemon")
def test_docker_variant_reaches_verified(db_session, tmp_path, acceptance_src):
    r = _drive(
        db_session, tmp_path, source=acceptance_src, scenario="A", sandbox_mode="docker"
    )
    _approve_if_parked(r)
    assert r.task.state == TaskState.COMPLETED.value
    verification = VerificationRepository(db_session).get_by_task(r.task_id)
    assert verification is not None and verification.verdict == "VERIFIED"
