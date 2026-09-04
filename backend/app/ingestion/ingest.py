"""Ingestion orchestration entrypoint. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11.

Runs synchronously inside the request handler (no async worker exists yet -- that's a
later orchestration-engine phase); still creates/transitions a real Job(type=INGEST) row
for schema-completeness and observability. Phase sequence: resolve source -> determine
commit identity -> build manifest -> idempotency check -> apply limits -> persist ->
materialize workspace -> finalize. Every failure surfaces as a distinct AppError subtype
from app.ingestion.errors, and marks the Job FAILED with {code, message} before re-raising.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import git
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.ingestion.git_client import (
    clone_shallow,
    current_branch,
    head_commit_sha,
    open_local,
)
from app.ingestion.limits import check_and_partition, limits_from_settings
from app.ingestion.manifest import ManifestFile, build_manifest
from app.ingestion.url_validator import validate_local_path, validate_remote_url
from app.ingestion.workspace import (
    make_read_only,
    materialize_from_clone,
    materialize_from_local,
    workspace_dir,
)
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.models.repository import Repository, SourceType
from app.repository.artifacts import ArtifactRepository
from app.repository.files import FileRepository
from app.repository.jobs import JobRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest, IngestResult


def synthesize_pseudo_sha(manifest: list[ManifestFile]) -> str:
    """Deterministic pseudo-sha for a local directory with no .git history, so plain
    fixture directories (test-repositories/*) can be ingested without becoming real
    git repos. Clearly prefixed so downstream code can detect and skip
    git-history-dependent features."""
    digest = hashlib.sha256()
    for f in sorted(manifest, key=lambda m: m.path):
        digest.update(f"{f.path}\0{f.sha256}\n".encode())
    return "local:" + digest.hexdigest()[:40]


def _language_histogram(files: list[ManifestFile]) -> dict[str, int]:
    histogram: dict[str, int] = {}
    for f in files:
        histogram[f.language] = histogram.get(f.language, 0) + 1
    return histogram


def _history_depth(git_repo: git.Repo, max_depth: int) -> int:
    return sum(1 for _ in zip(range(max_depth + 1), git_repo.iter_commits()))


def _result_from_existing(snapshot, job_id: str) -> IngestResult:
    return IngestResult(
        snapshot_id=snapshot.id,
        repository_id=snapshot.repository_id,
        commit_sha=snapshot.commit_sha,
        branch=snapshot.branch,
        status=snapshot.status,
        limit_reason=snapshot.limit_reason,
        file_count=snapshot.file_count,
        total_bytes=snapshot.total_bytes,
        languages=snapshot.languages or {},
        ingested_at=snapshot.ingested_at,
        job_id=job_id,
    )


def ingest_repository(
    session: Session,
    *,
    repository: Repository,
    request: IngestRequest,
    settings: Settings,
) -> IngestResult:
    jobs = JobRepository(session)
    snapshots = SnapshotRepository(session)
    files_repo = FileRepository(session)
    artifacts = ArtifactRepository(session)

    job = jobs.create(
        type=JobType.INGEST.value, idempotency_key=f"ingest:{repository.id}:{new_id()}"
    )
    jobs.mark_running(job.id)

    tmp_clone_dir: str | None = None
    git_repo: git.Repo | None
    try:
        if repository.source_type == SourceType.GITHUB.value:
            parsed = validate_remote_url(repository.url_or_path, settings)
            tmp_clone_dir = tempfile.mkdtemp(prefix="aegis-clone-")
            clone_dest = Path(tmp_clone_dir) / "repo"
            git_repo = clone_shallow(
                parsed.clone_url,
                clone_dest,
                depth=request.depth or settings.ingestion_default_clone_depth,
                branch=request.branch,
                timeout_s=settings.ingestion_clone_timeout_s,
            )
            commit_sha: str | None = head_commit_sha(git_repo)
            branch = current_branch(git_repo) or request.branch
            history_depth = _history_depth(
                git_repo, settings.ingestion_max_history_depth
            )
            source_root = clone_dest
        else:
            local_root = validate_local_path(repository.url_or_path, settings)
            git_repo = open_local(local_root)
            if git_repo is not None:
                commit_sha = head_commit_sha(git_repo)
                branch = current_branch(git_repo)
                history_depth = _history_depth(
                    git_repo, settings.ingestion_max_history_depth
                )
            else:
                commit_sha = None
                branch = None
                history_depth = 0
            source_root = local_root

        manifest = build_manifest(source_root)
        if commit_sha is None:
            commit_sha = synthesize_pseudo_sha(manifest)

        existing = snapshots.get_by_commit(repository.id, commit_sha)
        if existing is not None and not request.force:
            jobs.mark_succeeded(job.id)
            return _result_from_existing(existing, job.id)

        limits = limits_from_settings(settings)
        partitioned, breach = check_and_partition(manifest, limits)

        if existing is not None and request.force:
            snapshot = existing
            files_repo.replace_for_snapshot(snapshot.id, partitioned)
        else:
            snapshot = snapshots.create(
                repository_id=repository.id,
                commit_sha=commit_sha,
                branch=branch,
                history_depth=history_depth,
            )
            files_repo.bulk_create(snapshot.id, partitioned)

        total_bytes = sum(f.size_bytes for f in partitioned)
        languages = _language_histogram(partitioned)

        ws_path = workspace_dir(snapshot.id, settings)
        if repository.source_type == SourceType.GITHUB.value:
            materialize_from_clone(source_root, ws_path)
        else:
            materialize_from_local(source_root, ws_path)
        make_read_only(ws_path)

        artifacts.create(
            snapshot_id=snapshot.id,
            kind=ArtifactKind.WORKSPACE.value,
            store=ArtifactStoreKind.FS.value,
            uri=str(ws_path),
            retention=ArtifactRetention.EPHEMERAL.value,
            size_bytes=total_bytes,
        )

        status = "PARTIALLY_SUPPORTED" if breach else "READY"
        snapshot = snapshots.finalize(
            snapshot.id,
            status=status,
            limit_reason=breach.reason if breach else None,
            file_count=len(partitioned),
            total_bytes=total_bytes,
            languages=languages,
            ingested_at=datetime.now(timezone.utc),
        )

        jobs.mark_succeeded(job.id)
        return _result_from_existing(snapshot, job.id)
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise
    finally:
        if tmp_clone_dir is not None:
            shutil.rmtree(tmp_clone_dir, ignore_errors=True)
