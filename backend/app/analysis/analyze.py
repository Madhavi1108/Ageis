"""Analysis orchestration entrypoint. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12.

Runs synchronously inside the request handler (same precedent as app/ingestion/ingest.py's
ingest_repository -- no async worker exists yet); still creates/transitions a real
Job(type=ANALYZE) row. Phase sequence: validate snapshot readiness -> idempotency check ->
project metadata -> per-file AST pass (symbols + imports, parse_status update on failure)
-> entrypoints -> test detection -> persist RepositoryAnalysis -> Job bookkeeping.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from aegis.schemas.common import Confidence, Evidence
from app.analysis.entrypoints import detect_entrypoints
from app.analysis.errors import SnapshotNotReadyError
from app.analysis.graph.builder import build_graph
from app.analysis.graph.store import serialize_graph
from app.analysis.imports import imports_from_walk
from app.analysis.project_meta import load_pyproject, parse_project_metadata
from app.analysis.python_ast import RawWalk, parse_and_walk
from app.analysis.symbols import symbols_from_walk
from app.analysis.testdetect import detect_test_setup
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.models.repository_file import ParseStatus, RepositoryFile
from app.models.snapshot import RepositorySnapshot, SnapshotStatus
from app.repository.analyses import AnalysisRepository
from app.repository.artifacts import ArtifactRepository
from app.repository.dependencies import DependencyRepository
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.jobs import JobRepository
from app.repository.symbols import SymbolRepository
from app.schemas.analysis import EntryPointRef, RepositoryAnalysisResult


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


def _build_and_persist_graph(
    session: Session,
    *,
    snapshot: RepositorySnapshot,
    settings: Settings,
    walks: list[RawWalk],
    all_symbols: list,
    all_deps: list,
    py_files: list[RepositoryFile],
) -> str | None:
    """Phase 5 (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13): build the code
    graph from this same analysis pass's facts (no re-parsing), persist it,
    and write a GRAPH-kind Artifact holding the serialized graph. Returns the
    new artifact id, or None if there is nothing to graph (e.g. no Python
    files) -- never raises, a graph-build problem must not fail analysis
    itself.
    """
    result = build_graph(walks=walks, symbols=all_symbols, dependencies=all_deps, files=py_files)
    if not result.nodes:
        return None

    graph_repo = GraphRepository(session)
    node_rows, edge_rows = graph_repo.replace_for_snapshot(
        snapshot.id, result.nodes, result.edges
    )

    payload = json.dumps(serialize_graph(node_rows, edge_rows), indent=2)
    payload_bytes = payload.encode("utf-8")
    graphs_dir = Path(settings.artifacts_root) / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)
    graph_path = graphs_dir / f"{snapshot.id}.json"
    graph_path.write_text(payload, encoding="utf-8")

    artifact = ArtifactRepository(session).create(
        kind=ArtifactKind.GRAPH.value,
        store=ArtifactStoreKind.FS.value,
        uri=str(graph_path),
        retention=ArtifactRetention.RETAINED.value,
        snapshot_id=snapshot.id,
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
        size_bytes=len(payload_bytes),
        content_type="application/json",
    )
    return artifact.id


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

        # Phase 5 (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13): build the code
        # graph from this same pass's facts -- no re-parsing.
        graph_artifact_id = _build_and_persist_graph(
            session,
            snapshot=snapshot,
            settings=settings,
            walks=walks,
            all_symbols=all_symbols,
            all_deps=all_deps,
            py_files=py_files,
        )

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
        if graph_artifact_id is not None:
            analysis = analyses_repo.set_graph_artifact_id(snapshot.id, graph_artifact_id) or analysis

        jobs.mark_succeeded(job.id)
        return build_analysis_result(analysis, job.id)
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise
