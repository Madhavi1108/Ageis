"""GitHub passthrough + issue import API (Phase 19,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27). A top-level router, like
app/api/executions.py -- these are conceptually part of ingestion / task
creation but don't hang off a single resource.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.github.client import GitHubClient
from app.github.deps import get_github_client
from app.github.provider import GitHubProvider
from app.ingestion.errors import RepositoryNotFoundError
from app.repository.repositories import RepositoryRepository
from app.schemas.github import GitHubIssueInfo, GitHubRepoInfo, IssueRef

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/repos/{owner}/{repo}", response_model=GitHubRepoInfo)
def get_github_repo(
    owner: str,
    repo: str,
    client: GitHubClient = Depends(get_github_client),
) -> GitHubRepoInfo:
    """Repository metadata from the GitHub REST API. GitHub failures surface as
    structured errors (401/403 -> 502 with a code, 404 -> 404, 429 -> 429),
    never a raw 500."""
    return GitHubProvider(client).fetch_repo(owner, repo)


@router.get(
    "/repos/{owner}/{repo}/issues/{number}", response_model=GitHubIssueInfo
)
def get_github_issue(
    owner: str,
    repo: str,
    number: int,
    client: GitHubClient = Depends(get_github_client),
) -> GitHubIssueInfo:
    """A single issue from the GitHub REST API (untrusted text -- normalize
    before it backs a task)."""
    return GitHubProvider(client).fetch_issue(owner, repo, number)


@router.post(
    "/repos/{owner}/{repo}/issues/{number}/import",
    status_code=201,
    response_model=IssueRef,
)
def import_github_issue(
    owner: str,
    repo: str,
    number: int,
    repository_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: GitHubClient = Depends(get_github_client),
) -> IssueRef:
    """Fetch issue ``number`` and persist it as an ``Issue`` for
    ``?repository_id=`` (idempotent on ``(repo, GITHUB, number)``). The body is
    normalized like every other untrusted issue text."""
    if RepositoryRepository(db).get(repository_id) is None:
        raise RepositoryNotFoundError(f"repository {repository_id} not found")
    issue = GitHubProvider(client).import_issue(
        db,
        settings=settings,
        repository_id=repository_id,
        owner=owner,
        repo=repo,
        number=number,
    )
    return IssueRef.model_validate(issue, from_attributes=True)
