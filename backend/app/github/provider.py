"""Higher-level GitHub operations over ``GitHubClient`` (ADR-0015).

Turns raw REST payloads into AEGIS schemas and persists an imported issue as
an ``Issue`` row (dedup by ``(repository, GITHUB, number)``; body run through
the same ``normalize_text`` as every other untrusted issue text).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.github.client import GitHubClient
from app.models.issue import Issue, IssueSource
from app.repository.issues import IssueRepository
from app.schemas.github import GitHubIssueInfo, GitHubRepoInfo
from app.services.tasks import normalize_text


class GitHubProvider:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def fetch_repo(self, owner: str, repo: str) -> GitHubRepoInfo:
        d = self._client.get_repo(owner, repo)
        return GitHubRepoInfo(
            full_name=d["full_name"],
            default_branch=d.get("default_branch", "main"),
            private=bool(d.get("private", False)),
            html_url=d["html_url"],
            description=d.get("description"),
        )

    def fetch_issue(self, owner: str, repo: str, number: int) -> GitHubIssueInfo:
        d = self._client.get_issue(owner, repo, number)
        return GitHubIssueInfo(
            number=int(d["number"]),
            title=d.get("title") or "",
            body=d.get("body") or "",
            state=d.get("state", "open"),
            html_url=d["html_url"],
        )

    def import_issue(
        self,
        db: Session,
        *,
        settings: Settings,
        repository_id: str,
        owner: str,
        repo: str,
        number: int,
    ) -> Issue:
        info = self.fetch_issue(owner, repo, number)
        repo_issues = IssueRepository(db)
        existing = repo_issues.get_by_external_ref(
            repository_id, IssueSource.GITHUB.value, str(number)
        )
        if existing is not None:
            return existing

        title = normalize_text(
            info.title, max_bytes=settings.task_max_description_bytes
        ).text
        body = normalize_text(
            info.body, max_bytes=settings.task_max_description_bytes
        ).text
        return repo_issues.create(
            repository_id=repository_id,
            source=IssueSource.GITHUB.value,
            title=title or f"issue #{number}",
            body_sanitized=body,
            external_ref=str(number),
        )
