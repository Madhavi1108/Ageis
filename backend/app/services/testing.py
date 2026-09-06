"""Testing service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19).

* ``generate_tests`` -- synthesize tests for the latest Implementation's
  changed behaviour, statically validate + de-duplicate them, write them into
  a throwaway RW workspace, persist a new TestCase batch version.
* ``get_tests``      -- read a persisted TestGeneration (latest or a version).

Job bookkeeping mirrors app.services.implementation.generate_implementation.
State transition (``GENERATING_TESTS``) is a thin, unguarded ``set_state``
write, same latitude every prior phase took (the guarded machine is Phase 21).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.schema_guard import AIOutputInvalid
from app.core.config import Settings
from app.core.ids import new_id
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.job import JobType
from app.repository.analyses import AnalysisRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.files import FileRepository
from app.repository.implementations import ImplementationRepository
from app.models.task import TaskState
from app.repository.jobs import JobRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.schemas.testing import TestCase, TestGeneration
from app.testing import catalog as testing_catalog
from app.testing import generator as testing_generator
from app.testing.errors import (
    TestGenerationFailedError,
    TestGenerationImplementationMissingError,
    TestGenerationNotFoundError,
    TestGenerationTaskNotFoundError,
)
from app.testing.selector import select_targeted_set

#: sentinel so callers can pass provider=None explicitly (the "none" provider)
#: while an omitted argument still means "resolve from settings".
_RESOLVE_FROM_SETTINGS = object()


def _existing_test_sources(db: Session, snapshot_id: str, ws_root) -> dict[str, str]:
    test_files = [
        f for f in FileRepository(db).list_for_snapshot(snapshot_id) if f.is_test
    ]
    sources: dict[str, str] = {}
    for f in test_files:
        path = ws_root / f.path
        if path.is_file():
            sources[f.path] = path.read_text(encoding="utf-8", errors="replace")
    return sources


def _row_to_schema(row) -> TestCase:
    return TestCase(
        name=row.name,
        path=row.path,
        target_symbol=row.target_symbol,
        kind=row.kind,
        rationale=row.rationale,
        code=row.code,
        evidence=row.evidence,
        status=row.status,
        invalid_reason=row.invalid_reason,
        created_at=row.created_at,
    )


def _policy_gaps(kept_by_symbol: dict[str, set[str]], target_symbols: list[str]) -> list[str]:
    gaps: list[str] = []
    for symbol in target_symbols:
        kinds = kept_by_symbol.get(symbol, set())
        missing = {"BOUNDARY", "NEGATIVE"} - kinds
        if missing:
            gaps.append(f"{symbol}: missing {sorted(missing)} case(s)")
    return gaps


def generate_tests(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
) -> TestGeneration:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise TestGenerationTaskNotFoundError(f"task {task_id} not found")

    impl_row = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl_row is None:
        raise TestGenerationImplementationMissingError(
            f"task {task_id} needs an Implementation (POST /tasks/{{id}}/changes) "
            "before tests can be generated"
        )

    if provider is _RESOLVE_FROM_SETTINGS:
        from app.ai.provider import get_provider

        provider = get_provider(settings)
    if provider is None:
        raise TestGenerationFailedError(
            "no AI provider configured (ai_provider='none'); real tests cannot "
            "be fabricated by a deterministic fallback"
        )

    plan_row = EngineeringPlanRepository(db).get(impl_row.plan_id)
    target_symbols = list(plan_row.symbols_to_modify) if plan_row else []
    if not target_symbols:
        target_symbols = list(plan_row.files_to_modify) if plan_row else []
    problem_interpretation = plan_row.problem_interpretation if plan_row else "UNKNOWN"

    analysis = AnalysisRepository(db).get_by_snapshot(impl_row.snapshot_id)
    test_framework = analysis.test_framework if analysis else None

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.GENERATE_TESTS.value,
        idempotency_key=f"gentests:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    source_workspace = workspace_dir(impl_row.snapshot_id, settings)
    ws = clone_rw(impl_row.snapshot_id, source_workspace)
    try:
        # Reconstruct the implemented state so the case matrix reflects the
        # post-fix code, not the pre-fix snapshot.
        from app.implementation.editor import EditorError, apply_edit_op
        from app.schemas.implementation import EditOp

        for op_dict in impl_row.edit_ops:
            try:
                apply_edit_op(ws, EditOp.model_validate(op_dict))
            except EditorError:
                pass  # best-effort reconstruction; a failed op here was never applied originally

        existing_sources = _existing_test_sources(db, impl_row.snapshot_id, ws.root)
        existing_names = testing_catalog.existing_test_names(existing_sources)
        existing_paths = set(existing_sources) | {
            f.path
            for f in FileRepository(db).list_for_snapshot(impl_row.snapshot_id)
            if f.is_test
        }

        try:
            proposed = testing_generator.propose_test_cases(
                task_key=task_id,
                problem_interpretation=problem_interpretation,
                target_symbols=target_symbols,
                test_framework=test_framework,
                existing_test_paths=sorted(existing_paths),
                provider=provider,
                timeout_s=settings.ai_test_synthesis_timeout_s,
                max_tokens=settings.ai_test_synthesis_max_tokens,
            )
        except AIOutputInvalid as exc:
            jobs.mark_failed(
                job.id,
                error={"code": "TEST_GENERATION_FAILED", "message": str(exc)},
            )
            raise TestGenerationFailedError(
                f"test synthesis model output failed schema validation: {exc}"
            ) from exc

        if len(proposed) > settings.testing_max_cases:
            jobs.mark_failed(
                job.id,
                error={
                    "code": "TEST_GENERATION_FAILED",
                    "message": f"{len(proposed)} cases exceeds the configured cap",
                },
            )
            raise TestGenerationFailedError(
                f"model proposed {len(proposed)} test cases, more than the "
                f"configured cap of {settings.testing_max_cases}"
            )

        kept, dropped = testing_catalog.deduplicate(
            proposed, existing_names=existing_names, existing_paths=existing_paths
        )
        if not kept:
            jobs.mark_failed(
                job.id,
                error={
                    "code": "TEST_GENERATION_FAILED",
                    "message": "every proposed case was a duplicate",
                },
            )
            raise TestGenerationFailedError(
                f"every proposed case duplicated an existing test "
                f"({len(dropped)} dropped)"
            )

        testing_generator.write_into_workspace(ws, kept)

        rows_to_create: list[dict] = []
        kept_by_symbol: dict[str, set[str]] = {}
        for case in kept:
            error = testing_catalog.check_syntax(
                ws.path_for(case.path).read_text(encoding="utf-8")
            )
            status = "INVALID" if error else "GENERATED"
            if status == "GENERATED":
                kept_by_symbol.setdefault(case.target_symbol, set()).add(case.kind)
            rows_to_create.append(
                {
                    "name": case.name,
                    "path": case.path,
                    "target_symbol": case.target_symbol,
                    "kind": case.kind,
                    "rationale": case.rationale,
                    "code": case.code,
                    "evidence": [e.model_dump() for e in case.evidence],
                    "status": status,
                    "invalid_reason": error,
                }
            )

        rows = TestCaseRepository(db).create_version(
            task_id,
            snapshot_id=impl_row.snapshot_id,
            implementation_id=impl_row.id,
            cases=rows_to_create,
        )
        version = rows[0].version

        schemas = [_row_to_schema(r) for r in rows]
        targeted_set = select_targeted_set(schemas)
        policy_gaps = _policy_gaps(kept_by_symbol, target_symbols)

        TaskStepRepository(db).append(
            task_id=task_id, state=TaskState.GENERATING_TESTS.value, agent="testing"
        )
        TaskRepository(db).set_state(task_id, TaskState.GENERATING_TESTS.value)
        jobs.mark_succeeded(job.id)

        return TestGeneration(
            task_id=task_id,
            snapshot_id=impl_row.snapshot_id,
            implementation_id=impl_row.id,
            version=version,
            test_cases=schemas,
            targeted_set=targeted_set,
            policy_gaps=policy_gaps,
            created_at=rows[0].created_at,
        )
    finally:
        ws.cleanup()


def get_tests(
    db: Session, task_id: str, *, version: int | None = None
) -> TestGeneration:
    if TaskRepository(db).get(task_id) is None:
        raise TestGenerationTaskNotFoundError(f"task {task_id} not found")

    repo = TestCaseRepository(db)
    resolved_version = version if version is not None else repo.latest_version(task_id)
    if resolved_version is None:
        raise TestGenerationNotFoundError(f"no tests generated for task {task_id}")

    rows = repo.list_by_task_version(task_id, resolved_version)
    if not rows:
        raise TestGenerationNotFoundError(
            f"no tests for task {task_id} version {resolved_version}"
        )

    schemas = [_row_to_schema(r) for r in rows]
    targeted_set = select_targeted_set(schemas)
    return TestGeneration(
        task_id=task_id,
        snapshot_id=rows[0].snapshot_id,
        implementation_id=rows[0].implementation_id,
        version=resolved_version,
        test_cases=schemas,
        targeted_set=targeted_set,
        policy_gaps=[],
        created_at=rows[0].created_at,
    )
