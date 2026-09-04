"""Analysis orchestration entrypoint. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12.

Runs synchronously inside the request handler (same precedent as app/ingestion/ingest.py's
ingest_repository -- no async worker exists yet); still creates/transitions a real
Job(type=ANALYZE) row. Phase sequence: validate snapshot readiness -> idempotency check ->
project metadata -> per-file AST pass (symbols + imports, parse_status update on failure)
-> entrypoints -> test detection -> persist RepositoryAnalysis -> Job bookkeeping.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from aegis.schemas.common import Confidence, Evidence
from app.analysis.entrypoints import detect_entrypoints
from app.analysis.errors import SnapshotNotReadyError
from app.analysis.imports import imports_from_walk
from app.analysis.project_meta import load_pyproject, parse_project_metadata
from app.analysis.python_ast import parse_and_walk
from app.analysis.symbols import symbols_from_walk
from app.analysis.testdetect import detect_test_setup
from app.core.config import Settings
from app.core.errors import AppError
from app.ingestion.workspace import workspace_dir
from app.models.job import JobType
from app.models.repository_file import ParseStatus
from app.models.snapshot import RepositorySnapshot, SnapshotStatus
from app.repository.analyses import AnalysisRepository
from app.repository.dependencies import DependencyRepository
from app.repository.files import FileRepository
from app.repository.jobs import JobRepository
from app.repository.symbols import SymbolRepository
from app.schemas.analysis import EntryPointRef, RepositoryAnalysisResult
from app.core.ids import new_id


def _derive_local_module_names(paths: list[str]) -> set[str]:
    names: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) == 1:
            names.add(Path(parts[0]).stem)
        else:
            names.add(parts[0])
    return names


def build_analysis_result(analysis, job_id: str) -> RepositoryAnalysisResult:
    entry_points = [EntryPointRef(**ep) for ep in (analysis.entry_points or [])]
    unknowns = analysis.unknowns or []
    summary = analysis.summary or {}

    if unknowns:
        confidence = Confidence(value=0.8, basis="INFERENCE")
    else:
        confidence = Confidence(value=1.0, basis="FACT")

    evidence: list[Evidence] = []
    if analysis.package_manager:
        evidence.append(
            Evidence(
                kind="file",
                ref="pyproject.toml",
                detail=f"package_manager={analysis.package_manager}",
            )
        )
    if analysis.build_backend:
        evidence.append(
            Evidence(
                kind="file",
                ref="pyproject.toml",
                detail=f"build_backend={analysis.build_backend}",
            )
        )
    if analysis.test_framework:
        evidence.append(
            Evidence(
                kind="file",
                ref=analysis.snapshot_id,
                detail=f"test_framework={analysis.test_framework}",
            )
        )

    return RepositoryAnalysisResult(
        snapshot_id=analysis.snapshot_id,
        entry_points=entry_points,
        test_framework=analysis.test_framework,
        test_command=analysis.test_command,
        package_manager=analysis.package_manager,
        build_backend=analysis.build_backend,
        symbol_count=summary.get("symbol_count", 0),
        dependency_count=summary.get("dependency_count", 0),
        unknowns=unknowns,
        analysed_at=analysis.analysed_at,
        duration_ms=analysis.duration_ms,
        confidence=confidence,
        evidence=evidence,
        error=None,
        job_id=job_id,
    )


def analyze_snapshot(
    session: Session,
    *,
    snapshot: RepositorySnapshot,
    settings: Settings,
    force: bool = False,
) -> RepositoryAnalysisResult:
    if snapshot.status not in (
        SnapshotStatus.READY.value,
        SnapshotStatus.PARTIALLY_SUPPORTED.value,
    ):
        raise SnapshotNotReadyError(
            f"snapshot {snapshot.id} is not ready for analysis (status={snapshot.status})"
        )

    jobs = JobRepository(session)
    files_repo = FileRepository(session)
    symbols_repo = SymbolRepository(session)
    deps_repo = DependencyRepository(session)
    analyses_repo = AnalysisRepository(session)

    existing = analyses_repo.get_by_snapshot(snapshot.id)
    job = jobs.create(
        type=JobType.ANALYZE.value, idempotency_key=f"analyze:{snapshot.id}:{new_id()}"
    )

    if existing is not None and not force:
        jobs.mark_succeeded(job.id)
        return build_analysis_result(existing, job.id)

    jobs.mark_running(job.id)
    started = time.monotonic()
    try:
        ws_root = workspace_dir(snapshot.id, settings)
        all_files = files_repo.list_for_snapshot(snapshot.id)
        py_files = [
            f for f in all_files if f.language == "python" and not f.is_vendored
        ]
        local_module_names = _derive_local_module_names([f.path for f in all_files])

        pyproject = load_pyproject(ws_root)
        project_meta = parse_project_metadata(ws_root)

        walks = []
        all_symbols = []
        all_deps = []
        parse_updates: list[tuple[str, str, str | None]] = []

        for f in py_files:
            walk = parse_and_walk(ws_root / f.path, f.path)
            walks.append(walk)
            if walk.parse_error is not None:
                parse_updates.append(
                    (f.id, ParseStatus.SYNTAX_ERROR.value, walk.parse_error)
                )
                continue
            all_symbols.extend(symbols_from_walk(walk, f.id))
            all_deps.extend(
                imports_from_walk(
                    walk, f.id, local_module_names, set(project_meta.dependencies)
                )
            )

        files_repo.update_parse_status(parse_updates)
        symbols_repo.replace_for_snapshot(snapshot.id, all_symbols)
        deps_repo.replace_for_snapshot(snapshot.id, all_deps)

        entry_points = detect_entrypoints(walks, project_meta)
        test_setup = detect_test_setup(ws_root, walks, pyproject)

        unknowns = list(project_meta.unknowns)
        if test_setup.framework is None:
            unknowns.append("test_framework")

        analysis = analyses_repo.upsert(
            snapshot.id,
            entry_points=[asdict(ep) for ep in entry_points],
            test_framework=test_setup.framework,
            test_command=test_setup.command,
            package_manager=project_meta.package_manager,
            build_backend=project_meta.build_backend,
            summary={
                "symbol_count": len(all_symbols),
                "dependency_count": len(all_deps),
                "file_count": len(py_files),
            },
            unknowns=unknowns,
            analysed_at=datetime.now(timezone.utc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )

        jobs.mark_succeeded(job.id)
        return build_analysis_result(analysis, job.id)
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise
