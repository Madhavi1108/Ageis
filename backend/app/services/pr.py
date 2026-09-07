"""Pull-request service (Phase 19, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 27, ADR-0015).

``create_pr`` always produces the PR-body artifact and a ``PullRequest`` row.
A real GitHub PR is opened only when: the repo is GITHUB, a token is
configured, the write is human-approved (protected-branch / external-PR HITL
gate), and every GitHub call succeeds. A ``PullRequest`` is marked ``CREATED``
only on an actual ``201`` with a stored URL/number -- any GitHub failure lands
as ``state=FAILED`` with a structured ``failure_reason``, never a 5xx.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.github import pr_builder
from app.github.client import GitHubClient
from app.github.errors import GitHubError, PRNotFoundError, PRNotVerifiedError, PRTaskNotFoundError
from app.ingestion.url_validator import validate_remote_url
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.repository.artifacts import ArtifactRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.pull_requests import PullRequestRepository
from app.repository.repositories import RepositoryRepository
from app.repository.tasks import TaskRepository
from app.repository.verifications import VerificationRepository
from app.schemas.github import PullRequestOut
from app.services.execution import _reconstruct_implementation

_LOCAL = "LOCAL_ARTIFACT"
_GITHUB = "GITHUB"


def _project(row) -> PullRequestOut:
    return PullRequestOut(
        id=row.id,
        task_id=row.task_id,
        mode=row.mode,
        title=row.title,
        body_artifact_id=row.body_artifact_id,
        branch=row.branch,
        commit_sha=row.commit_sha,
        github_url=row.github_url,
        github_number=row.github_number,
        state=row.state,
        failure_reason=row.failure_reason,
        created_at=row.created_at,
    )


def get_pr(db: Session, task_id: str) -> PullRequestOut:
    if TaskRepository(db).get(task_id) is None:
        raise PRTaskNotFoundError(f"task {task_id} not found")
    row = PullRequestRepository(db).get_latest_by_task(task_id)
    if row is None:
        raise PRNotFoundError(f"task {task_id} has no pull request (POST /tasks/{{id}}/pr)")
    return _project(row)


def create_pr(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    github_client: GitHubClient,
    approved: bool = False,
) -> PullRequestOut:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise PRTaskNotFoundError(f"task {task_id} not found")

    live = VerificationRepository(db).get_by_task(task_id)
    if live is None or live.verdict != "VERIFIED":
        raise PRNotVerifiedError(
            f"task {task_id} is not VERIFIED "
            f"(verdict={live.verdict if live else None}); a PR is only opened "
            f"for a verified change"
        )

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.PR.value,
        idempotency_key=f"pr:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        title = pr_builder.build_pr_title(db, task_id)
        body = pr_builder.build_pr_body(db, task_id)
        artifact = _write_body_artifact(db, settings, task_id, body)
        pull_repo = PullRequestRepository(db)
        repository = RepositoryRepository(db).get(task.repository_id)

        token_set = settings.github_token is not None
        if repository is None or repository.source_type != _GITHUB or not token_set:
            row = pull_repo.create(
                task_id=task_id,
                mode=_LOCAL,
                title=title,
                body_artifact_id=artifact.id,
                state="DRAFTED",
            )
            jobs.mark_succeeded(job.id)
            return _project(row)

        base = repository.default_branch or "main"
        head = f"{settings.git_pr_branch_prefix}task-{task_id[:8]}"

        if base in settings.github_protected_branches and not approved:
            row = pull_repo.create(
                task_id=task_id,
                mode=_GITHUB,
                title=title,
                body_artifact_id=artifact.id,
                state="DRAFTED",
                branch=head,
                failure_reason=(
                    f"REVIEW_REQUIRED: '{base}' is a protected branch -- "
                    f"re-POST with {{'approved': true}}"
                ),
            )
            jobs.mark_succeeded(job.id)
            return _project(row)

        parsed = validate_remote_url(repository.url_or_path, settings)
        try:
            row = _open_github_pr(
                db,
                settings=settings,
                client=github_client,
                task_id=task_id,
                owner=parsed.owner,
                repo=parsed.repo,
                base=base,
                head=head,
                title=title,
                body=body,
                artifact_id=artifact.id,
            )
        except GitHubError as exc:
            row = pull_repo.create(
                task_id=task_id,
                mode=_GITHUB,
                title=title,
                body_artifact_id=artifact.id,
                state="FAILED",
                branch=head,
                failure_reason=f"{exc.code}: {exc.args[0] if exc.args else ''}"[:512],
            )
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(job.id, error={"code": "PR_FAILED", "message": str(exc)})
        raise

    jobs.mark_succeeded(job.id)
    return _project(row)


# --------------------------------------------------------------------------- #


def _write_body_artifact(db: Session, settings: Settings, task_id: str, body: str):
    bodies_dir = Path(settings.artifacts_root) / "pr_bodies"
    bodies_dir.mkdir(parents=True, exist_ok=True)
    path = bodies_dir / f"{task_id}.md"
    data = body.encode("utf-8")
    path.write_bytes(data)
    return ArtifactRepository(db).create(
        kind=ArtifactKind.PR_BODY.value,
        store=ArtifactStoreKind.FS.value,
        uri=str(path),
        retention=ArtifactRetention.RETAINED.value,
        task_id=task_id,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        content_type="text/markdown",
    )


def _open_github_pr(
    db: Session,
    *,
    settings: Settings,
    client: GitHubClient,
    task_id: str,
    owner: str,
    repo: str,
    base: str,
    head: str,
    title: str,
    body: str,
    artifact_id: str,
):
    base_sha = client.get_ref(owner, repo, f"heads/{base}")
    client.create_ref(owner, repo, f"refs/heads/{head}", base_sha)

    last_commit_sha = base_sha
    for rel_path, content in _final_file_bytes(db, settings, task_id).items():
        last_commit_sha = client.put_file(
            owner,
            repo,
            rel_path,
            message=title,
            content_bytes=content,
            branch=head,
        )

    pr = client.create_pull(
        owner, repo, title=title, head=head, base=base, body=body
    )
    return PullRequestRepository(db).create(
        task_id=task_id,
        mode=_GITHUB,
        title=title,
        body_artifact_id=artifact_id,
        state="CREATED",
        branch=head,
        commit_sha=last_commit_sha,
        github_url=pr.url,
        github_number=pr.number,
    )


def _final_file_bytes(
    db: Session, settings: Settings, task_id: str
) -> dict[str, bytes]:
    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None:
        return {}
    touched = pr_builder.touched_files_for_task(db, task_id)
    if not touched:
        return {}
    source_ws = workspace_dir(impl.snapshot_id, settings)
    if not source_ws.is_dir():
        return {}  # the snapshot workspace was reaped -- push an empty branch
    ws = clone_rw(impl.snapshot_id, source_ws)
    try:
        _reconstruct_implementation(ws, impl)
        out: dict[str, bytes] = {}
        for rel in touched:
            fp = ws.path_for(rel)
            if fp.is_file():
                out[rel] = fp.read_bytes()
        return out
    finally:
        ws.cleanup()
